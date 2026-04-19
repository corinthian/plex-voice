import json
import sys
from plexctl import api

_EXCLUDE = {"Plex Media Server", "plexctl"}


def _active_clients() -> list[dict]:
    """Clients currently registered with PMS via Companion protocol."""
    data = api.get("/clients")
    raw = data.get("MediaContainer", {}).get("Server", [])
    if not isinstance(raw, list):
        raw = [raw]
    return raw


def _registered_devices() -> list[dict]:
    """All devices ever seen, from plex.tv account."""
    devices = api.plex_tv_get("/devices.json")
    return [d for d in devices if d.get("product") not in _EXCLUDE]


def list_clients() -> list[dict]:
    active = _active_clients()
    active_by_name = {c["name"].lower(): c for c in active}

    registered = _registered_devices()
    out = []
    for d in registered:
        ac = active_by_name.get(d["name"].lower())
        out.append({
            "name": d.get("name"),
            "product": d.get("product"),
            "version": d.get("version"),
            "lastSeen": d.get("lastSeenAt"),
            "active": ac is not None,
            "machineIdentifier": ac["machineIdentifier"] if ac else None,
            "baseurl": f"http://{ac['host']}:{ac['port']}" if ac else None,
        })
    return out


def print_clients() -> None:
    clients = list_clients()
    active = [c for c in clients if c["active"]]
    print(json.dumps({
        "ok": True,
        "clients": clients,
        "note": f"{len(active)}/{len(clients)} clients currently controllable (app must be open)",
    }))


def resolve(name: str | None) -> dict:
    """Return active client dict {machineIdentifier, baseurl, name} or exit."""
    from plexctl import config as cfg
    target = name or cfg.require("default_client")
    clients = list_clients()

    for c in clients:
        if c.get("name") == target or c.get("machineIdentifier") == target:
            if not c["active"]:
                print(json.dumps({"ok": False, "error": f"'{target}' is registered but not active — open the Plex app"}))
                sys.exit(1)
            return c
    for c in clients:
        if c.get("name", "").lower() == target.lower():
            if not c["active"]:
                print(json.dumps({"ok": False, "error": f"'{target}' is registered but not active — open the Plex app"}))
                sys.exit(1)
            return c

    print(json.dumps({"ok": False, "error": f"client not found: {target}"}))
    sys.exit(1)
