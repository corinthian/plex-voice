import sys
import requests
from plexctl import config as cfg

PLEX_HEADERS = {
    "X-Plex-Product": "plexctl",
    "X-Plex-Version": "0.1.0",
    "X-Plex-Platform": "Python",
    "X-Plex-Provides": "controller",
    "Accept": "application/json",
}


def _headers(token: str, client_id: str) -> dict:
    return {
        **PLEX_HEADERS,
        "X-Plex-Token": token,
        "X-Plex-Client-Identifier": client_id,
    }


PLEX_TV = "https://plex.tv"


def plex_tv_get(path: str, params: dict | None = None, timeout: int = 10) -> dict | list:
    c = cfg.load()
    token = cfg.require("token")
    client_id = c.get("client_id", cfg.DEFAULTS["client_id"])
    url = PLEX_TV + path
    try:
        r = requests.get(url, headers=_headers(token, client_id), params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError as e:
        print(f'{{"ok": false, "error": "plex.tv connection failed: {e}"}}')
        sys.exit(1)
    except requests.exceptions.HTTPError as e:
        print(f'{{"ok": false, "error": "plex.tv HTTP {r.status_code}: {r.text[:200]}"}}')
        sys.exit(1)


def get(path: str, params: dict | None = None, timeout: int = 10) -> dict:
    c = cfg.load()
    server = c.get("server_url", cfg.DEFAULTS["server_url"])
    token = cfg.require("token")
    client_id = c.get("client_id", cfg.DEFAULTS["client_id"])
    url = server.rstrip("/") + path
    try:
        r = requests.get(url, headers=_headers(token, client_id), params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError as e:
        print(f'{{"ok": false, "error": "connection failed: {e}"}}')
        sys.exit(1)
    except requests.exceptions.HTTPError as e:
        print(f'{{"ok": false, "error": "HTTP {r.status_code}: {r.text[:200]}"}}')
        sys.exit(1)
