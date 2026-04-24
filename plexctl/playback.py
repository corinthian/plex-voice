import re
import time
import requests
from plexctl import config as cfg

# Seed from epoch seconds so commandID is always increasing across invocations
_command_id = int(time.time())


def _next_command_id() -> int:
    global _command_id
    _command_id += 1
    return _command_id


def _player_cmd(client: dict, path: str, extra_params: dict | None = None) -> dict:
    c = cfg.load()
    token = cfg.require("token")
    client_id = c.get("client_id", cfg.DEFAULTS["client_id"])

    headers = {
        "X-Plex-Product": "plexctl",
        "X-Plex-Version": "1.0.0",
        "X-Plex-Platform": "Python",
        "X-Plex-Provides": "controller",
        "Accept": "application/json",
        "X-Plex-Token": token,
        "X-Plex-Client-Identifier": client_id,
        "X-Plex-Target-Client-Identifier": client["machineIdentifier"],
    }

    params = {"commandID": _next_command_id(), "type": "video"}
    if extra_params:
        params.update(extra_params)

    url = client["baseurl"].rstrip("/") + path
    try:
        r = requests.get(url, headers=headers, params=params, timeout=10)
        r.raise_for_status()
        return {"ok": True}
    except requests.exceptions.ConnectionError as e:
        return {"ok": False, "error": f"connection failed: {e}"}
    except requests.exceptions.HTTPError as e:
        return {"ok": False, "error": f"HTTP {r.status_code}: {r.text[:200]}"}
    except requests.exceptions.RequestException as e:
        return {"ok": False, "error": str(e)}


class CompanionTransportError(Exception):
    """Raised when a Companion-endpoint request fails (network, HTTP, or decode)."""


def _player_get(client: dict, path: str, extra_params: dict | None = None) -> dict:
    """GET from the client's Companion endpoint; returns parsed JSON (possibly {}).

    Raises CompanionTransportError on any transport, HTTP, or JSON-decode failure so
    callers can distinguish "unreachable client" from "empty response body".
    """
    c = cfg.load()
    token = cfg.require("token")
    client_id = c.get("client_id", cfg.DEFAULTS["client_id"])
    headers = {
        "X-Plex-Product": "plexctl",
        "X-Plex-Version": "1.0.0",
        "X-Plex-Platform": "Python",
        "X-Plex-Provides": "controller",
        "Accept": "application/json",
        "X-Plex-Token": token,
        "X-Plex-Client-Identifier": client_id,
        "X-Plex-Target-Client-Identifier": client["machineIdentifier"],
    }
    params = {"commandID": _next_command_id()}
    if extra_params:
        params.update(extra_params)
    url = client["baseurl"].rstrip("/") + path
    try:
        r = requests.get(url, headers=headers, params=params, timeout=10)
        r.raise_for_status()
        return r.json() if r.text.strip() else {}
    except requests.exceptions.RequestException as e:
        raise CompanionTransportError(str(e)) from e


def _get_session_state(client: dict) -> str | None:
    from plexctl import api
    machine_id = client.get("machineIdentifier")
    try:
        data = api.get("/status/sessions")
    except SystemExit:
        return None
    for s in data.get("MediaContainer", {}).get("Metadata", []) or []:
        player = s.get("Player", {})
        if player.get("machineIdentifier") == machine_id:
            return player.get("state")
    return None


def _get_view_offset(client: dict) -> int | None:
    from plexctl import api
    machine_id = client.get("machineIdentifier")
    try:
        data = api.get("/status/sessions")
    except SystemExit:
        return None
    sessions = data.get("MediaContainer", {}).get("Metadata", []) or []
    for s in sessions:
        player = s.get("Player", {})
        if player.get("machineIdentifier") == machine_id:
            raw = s.get("viewOffset", 0)
            if raw is None:
                return None
            try:
                return int(raw)
            except (TypeError, ValueError):
                return None
    return None


def _get_server_machine_id() -> str | None:
    from plexctl import api
    try:
        data = api.get("/")
    except SystemExit:
        return None
    return data.get("MediaContainer", {}).get("machineIdentifier")


def play(client: dict) -> dict:
    return _player_cmd(client, "/player/playback/play")


def pause(client: dict) -> dict:
    return _player_cmd(client, "/player/playback/pause")


def stop(client: dict) -> dict:
    return _player_cmd(client, "/player/playback/stop")


def step_forward(client: dict) -> dict:
    return _player_cmd(client, "/player/playback/stepForward")


def step_back(client: dict) -> dict:
    return _player_cmd(client, "/player/playback/stepBack")


def set_volume(client: dict, level: int) -> dict:
    return _player_cmd(client, "/player/playback/setParameters", {"volume": level})


def seek(client: dict, position: str, unpause: bool = True) -> dict:
    position = position.strip()

    def _do_seek(offset_ms: int) -> dict:
        was_paused = unpause and _get_session_state(client) == "paused"
        if was_paused:
            pre = _player_cmd(client, "/player/playback/play")
            if not pre.get("ok"):
                return {"ok": False, "error": f"could not resume before seek: {pre.get('error')}"}
            time.sleep(1.0)
        result = _player_cmd(client, "/player/playback/seekTo", {"offset": offset_ms})
        if was_paused and result.get("ok"):
            post = _player_cmd(client, "/player/playback/pause")
            if not post.get("ok"):
                return {"ok": False, "error": f"seeked but failed to restore pause state: {post.get('error')}"}
        return result

    rel = re.fullmatch(r"([+-])(\d+(?:\.\d+)?)([sm])", position)
    if rel:
        sign, val, unit = rel.groups()
        delta_ms = int(float(val) * (60000 if unit == "m" else 1000))
        offset = _get_view_offset(client)
        if offset is None:
            return {"ok": False, "error": "could not determine current playback position"}
        return _do_seek(max(0, offset + (delta_ms if sign == "+" else -delta_ms)))

    ts = re.fullmatch(r"(?:(\d+):)?(\d{1,2}):(\d{2})", position)
    if ts:
        h, m, s = ts.groups()
        total_ms = (int(h) * 3600 + int(m) * 60 + int(s)) * 1000 if h else (int(m) * 60 + int(s)) * 1000
        return _do_seek(total_ms)

    return {"ok": False, "error": f"unrecognised position format: {position!r}"}


def play_queue(client: dict, queue_id: str, selected_item_id: str) -> dict:
    server_id = _get_server_machine_id()
    if not server_id:
        return {"ok": False, "error": "could not retrieve server machineIdentifier"}
    c = cfg.load()
    server_url = c.get("server_url", cfg.DEFAULTS["server_url"])
    from urllib.parse import urlparse
    parsed = urlparse(server_url)
    address = parsed.hostname
    port = parsed.port or 32400
    return _player_cmd(client, "/player/playback/playMedia", {
        "key": f"/playQueues/{queue_id}",
        "playQueueID": queue_id,
        "playQueueSelectedItemID": selected_item_id,
        "machineIdentifier": server_id,
        "address": address,
        "port": port,
        "offset": 0,
    })


def play_media(client: dict, rating_key: str) -> dict:
    server_id = _get_server_machine_id()
    if not server_id:
        return {"ok": False, "error": "could not retrieve server machineIdentifier"}
    c = cfg.load()
    server_url = c.get("server_url", cfg.DEFAULTS["server_url"])
    # Parse host and port from server_url (http://host:port)
    from urllib.parse import urlparse
    parsed = urlparse(server_url)
    address = parsed.hostname
    port = parsed.port or 32400
    key = f"/library/metadata/{rating_key}"
    return _player_cmd(client, "/player/playback/playMedia", {
        "key": key,
        "machineIdentifier": server_id,
        "address": address,
        "port": port,
        "offset": 0,
        "containerKey": key,
    })
