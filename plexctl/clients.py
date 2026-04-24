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


def _norm_name(v) -> str | None:
    return v.lower() if isinstance(v, str) and v else None


def list_clients() -> list[dict]:
    active = _active_clients()
    active_by_name: dict[str, dict] = {}
    duplicate_names: set[str] = set()
    for c in active:
        k = _norm_name(c.get("name"))
        if not k:
            continue
        if k in active_by_name:
            duplicate_names.add(k)
            continue
        active_by_name[k] = c

    registered = _registered_devices()
    out = []
    for d in registered:
        k = _norm_name(d.get("name"))
        ac = active_by_name.get(k) if k else None
        out.append({
            "name": d.get("name"),
            "product": d.get("product"),
            "version": d.get("version"),
            "lastSeen": d.get("lastSeenAt"),
            "active": ac is not None,
            "machineIdentifier": ac["machineIdentifier"] if ac else None,
            "baseurl": f"http://{ac['host']}:{ac['port']}" if ac else None,
            "ambiguous": k in duplicate_names if k else False,
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

    def _bail_ambiguous(c: dict) -> None:
        print(json.dumps({
            "ok": False,
            "error": f"ambiguous client name '{c.get('name')}' — multiple active devices share this name; specify by machineIdentifier",
        }))
        sys.exit(1)

    for c in clients:
        if c.get("name") == target or c.get("machineIdentifier") == target:
            if c.get("ambiguous") and c.get("machineIdentifier") != target:
                _bail_ambiguous(c)
            if not c["active"]:
                print(json.dumps({"ok": False, "error": f"'{target}' is registered but not active — open the Plex app"}))
                sys.exit(1)
            return c
    target_lower = target.lower() if isinstance(target, str) else ""
    for c in clients:
        cname = c.get("name")
        if isinstance(cname, str) and cname.lower() == target_lower:
            if c.get("ambiguous"):
                _bail_ambiguous(c)
            if not c["active"]:
                print(json.dumps({"ok": False, "error": f"'{target}' is registered but not active — open the Plex app"}))
                sys.exit(1)
            return c

    print(json.dumps({"ok": False, "error": f"client not found: {target}"}))
    sys.exit(1)
