from plexctl import api


def now_playing(client: dict) -> dict:
    """Return compact now-playing info for the given client, or ok=False if nothing playing."""
    machine_id = client.get("machineIdentifier")
    data = api.get("/status/sessions")
    sessions = data.get("MediaContainer", {}).get("Metadata", []) or []
    for s in sessions:
        player = s.get("Player", {})
        if player.get("machineIdentifier") == machine_id:
            return {
                "ok": True,
                "state": player.get("state"),
                "title": s.get("title"),
                "type": s.get("type"),
                "show": s.get("grandparentTitle"),      # TV show name, None for movies
                "season": s.get("parentIndex"),          # season number
                "episode": s.get("index"),               # episode number
                "year": s.get("year"),                   # movie year
                "viewOffset": s.get("viewOffset"),       # ms elapsed
                "duration": s.get("duration"),           # ms total
                "ratingKey": s.get("ratingKey"),
            }
    return {"ok": False, "error": f"nothing playing on {client.get('name', machine_id)}"}


def current_rating_key(client: dict) -> str | None:
    """Return ratingKey of the item currently playing on client, or None."""
    result = now_playing(client)
    if result.get("ok"):
        return result.get("ratingKey")
    return None


def history(limit: int = 10) -> dict:
    data = api.get("/status/sessions/history/all", params={"X-Plex-Container-Size": limit, "sort": "viewedAt:desc"})
    entries = data.get("MediaContainer", {}).get("Metadata", []) or []
    return {
        "ok": True,
        "history": [
            {
                "title": e.get("title"),
                "type": e.get("type"),
                "show": e.get("grandparentTitle"),
                "viewedAt": e.get("viewedAt"),
                "ratingKey": e.get("ratingKey"),
            }
            for e in entries
        ],
    }


def continue_watching() -> dict:
    data = api.get("/hubs/continueWatching")
    hubs = data.get("MediaContainer", {}).get("Hub", []) or []
    items = []
    for hub in hubs:
        items.extend(hub.get("Metadata", []) or [])
    return {
        "ok": True,
        "items": [
            {
                "title": i.get("title"),
                "type": i.get("type"),
                "show": i.get("grandparentTitle"),
                "season": i.get("parentIndex"),
                "episode": i.get("index"),
                "viewOffset": i.get("viewOffset"),
                "duration": i.get("duration"),
                "ratingKey": i.get("ratingKey"),
            }
            for i in items
        ],
    }
