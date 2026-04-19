from plexctl import api

_TYPE_MAP = {"show": 2, "movie": 1, "episode": 4}


def _extract_metadata(hub_response: dict, type_filter: str | None = None) -> list[dict]:
    hubs = hub_response.get("MediaContainer", {}).get("Hub", [])
    results = []
    for hub in hubs:
        if type_filter and hub.get("type") != type_filter:
            continue
        results.extend(hub.get("Metadata", []))
    return results


def search(query: str, media_type: str | None = None) -> list[dict]:
    try:
        resp = api.get("/hubs/search/voice", params={"query": query})
        results = _extract_metadata(resp, media_type)
        if results:
            return results
    except SystemExit:
        pass

    params: dict = {"query": query, "limit": 10}
    if media_type and media_type in _TYPE_MAP:
        params["type"] = _TYPE_MAP[media_type]
    resp = api.get("/hubs/search", params=params)
    return _extract_metadata(resp, media_type)


def latest_unwatched_episode(show_query: str) -> dict | None:
    hits = search(show_query, media_type="show")
    if not hits:
        return None

    show_key = hits[0]["ratingKey"]
    resp = api.get(f"/library/metadata/{show_key}/allLeaves")
    episodes: list[dict] = resp.get("MediaContainer", {}).get("Metadata", [])
    if not episodes:
        return None

    episodes.sort(key=lambda e: (e.get("parentIndex", 0), e.get("index", 0)))

    unwatched = [e for e in episodes if not e.get("viewCount", 0)]
    if unwatched:
        return unwatched[0]

    return max(episodes, key=lambda e: e.get("originallyAvailableAt", ""))


_SECTION_TYPE_MAP = {"show": 2, "movie": 1}


def sections() -> list[dict]:
    resp = api.get("/library/sections")
    dirs = resp.get("MediaContainer", {}).get("Directory", []) or []
    return [{"key": d.get("key"), "title": d.get("title"), "type": d.get("type")} for d in dirs]


def list_section(section_id: str, media_type: str | None = None,
                 unwatched: bool = False, sort: str | None = None) -> list[dict]:
    params: dict = {}
    if media_type and media_type in _SECTION_TYPE_MAP:
        params["type"] = _SECTION_TYPE_MAP[media_type]
    if unwatched:
        params["unwatched"] = 1
    if sort:
        params["sort"] = sort
    resp = api.get(f"/library/sections/{section_id}/all", params=params)
    items = resp.get("MediaContainer", {}).get("Metadata", []) or []
    return [
        {
            "ratingKey": i.get("ratingKey"),
            "title": i.get("title"),
            "type": i.get("type"),
            "year": i.get("year"),
            "viewCount": i.get("viewCount", 0),
            "addedAt": i.get("addedAt"),
        }
        for i in items
    ]


def metadata(rating_key: str) -> dict:
    resp = api.get(f"/library/metadata/{rating_key}")
    items = resp.get("MediaContainer", {}).get("Metadata", []) or []
    return items[0] if items else {}


def scrobble(rating_key: str) -> dict:
    api.get("/:/scrobble", params={"key": rating_key, "identifier": "com.plexapp.plugins.library"})
    return {"ok": True}


def unscrobble(rating_key: str) -> dict:
    api.get("/:/unscrobble", params={"key": rating_key, "identifier": "com.plexapp.plugins.library"})
    return {"ok": True}


def rate(rating_key: str, rating: int) -> dict:
    api.get("/:/rate", params={"key": rating_key, "identifier": "com.plexapp.plugins.library", "rating": rating})
    return {"ok": True}
