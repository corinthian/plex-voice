import sys
import uuid
import json
import requests
from plexctl import config as cfg

PLEX_TV_SIGNIN = "https://plex.tv/users/sign_in.json"
PLEX_HEADERS = {
    "X-Plex-Product": "plexctl",
    "X-Plex-Version": "0.1.0",
    "X-Plex-Platform": "Python",
    "Accept": "application/json",
}


def login() -> None:
    print("Plex.tv credentials (never stored — only the token is saved)")
    username = input("  Username or email: ").strip()
    password = input("  Password: ").strip()

    server_url = input(f"  PMS URL [{cfg.DEFAULTS['server_url']}]: ").strip()
    if not server_url:
        server_url = cfg.DEFAULTS["server_url"]

    default_client = input(f"  Default client [{cfg.DEFAULTS['default_client']}]: ").strip()
    if not default_client:
        default_client = cfg.DEFAULTS["default_client"]

    client_id = cfg.load().get("client_id") or f"plexctl-{uuid.uuid4().hex[:8]}"

    headers = {**PLEX_HEADERS, "X-Plex-Client-Identifier": client_id}

    try:
        r = requests.post(PLEX_TV_SIGNIN, auth=(username, password), headers=headers, timeout=15)
        r.raise_for_status()
    except requests.exceptions.HTTPError:
        print(json.dumps({"ok": False, "error": f"auth failed: HTTP {r.status_code}"}))
        sys.exit(1)
    except requests.exceptions.ConnectionError as e:
        print(json.dumps({"ok": False, "error": f"connection failed: {e}"}))
        sys.exit(1)
    except requests.exceptions.Timeout as e:
        print(json.dumps({"ok": False, "error": f"auth request timed out: {e}"}))
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(json.dumps({"ok": False, "error": f"auth request failed: {e}"}))
        sys.exit(1)

    try:
        payload = r.json()
        token = payload["user"]["authToken"]
    except requests.exceptions.JSONDecodeError as e:
        print(json.dumps({"ok": False, "error": f"plex.tv returned non-JSON response: {e}"}))
        sys.exit(1)
    except (KeyError, TypeError):
        print(json.dumps({"ok": False, "error": "unexpected auth response shape from plex.tv"}))
        sys.exit(1)

    # Verify PMS is reachable before writing config
    try:
        verify = requests.get(
            server_url.rstrip("/") + "/",
            headers={**headers, "X-Plex-Token": token},
            timeout=10,
        )
        verify.raise_for_status()
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"PMS unreachable at {server_url}: {e}"}))
        sys.exit(1)

    cfg.save({
        "server_url": server_url,
        "token": token,
        "default_client": default_client,
        "client_id": client_id,
    })

    print(json.dumps({"ok": True, "message": f"token saved to {cfg.CONFIG_PATH}"}))
