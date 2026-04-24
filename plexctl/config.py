import json
import os
import sys
import tomllib
from pathlib import Path

CONFIG_PATH = Path.home() / ".config" / "plexctl" / "config.toml"

DEFAULTS = {
    "server_url": "http://plex.local:32400",
    "default_client": "Apple TV",
    "client_id": "plexctl-default",
}


def load() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    try:
        with open(CONFIG_PATH, "rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        print(json.dumps({
            "ok": False,
            "error": f"invalid config at {CONFIG_PATH}: {e} — run plexctl auth login",
        }))
        sys.exit(1)


def save(data: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for k, v in data.items():
        escaped = str(v).replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'{k} = "{escaped}"')
    CONFIG_PATH.write_text("\n".join(lines) + "\n")
    CONFIG_PATH.chmod(0o600)


def require(key: str) -> str:
    cfg = load()
    val = cfg.get(key)
    if not val:
        print(json.dumps({"ok": False, "error": f"missing config key: {key} — run plexctl auth login"}))
        sys.exit(1)
    return val
