from plexctl import api
from plexctl.playback import CompanionTransportError, _get_server_machine_id


def _rollback_queue(queue_id: str) -> None:
    """Best-effort deletion of a partially-built play queue. Never raises."""
    try:
        api.delete(f"/playQueues/{queue_id}")
    except SystemExit:
        pass


def create(rating_keys: list[str], shuffle: bool = False, repeat: bool = False) -> dict:
    server_id = _get_server_machine_id()
    if not server_id:
        return {"ok": False, "error": "could not retrieve server machineIdentifier"}

    first_key = rating_keys[0]
    uri = f"server://{server_id}/com.plexapp.plugins.library/library/metadata/{first_key}"

    data = api.post("/playQueues", params={
        "type": "video",
        "uri": uri,
        "shuffle": 1 if shuffle else 0,
        "repeat": 1 if repeat else 0,
        "continuous": 1,
    })

    mc = data.get("MediaContainer", {})
    queue_id = mc.get("playQueueID")
    selected_id = mc.get("playQueueSelectedItemID")

    if not queue_id:
        return {"ok": False, "error": "playQueue creation returned no playQueueID"}

    for rk in rating_keys[1:]:
        result = add(str(queue_id), rk)
        if not result.get("ok"):
            _rollback_queue(str(queue_id))
            result["partialQueueID"] = str(queue_id)
            result["rollbackAttempted"] = True
            return result

    if selected_id is None:
        return {"ok": False, "error": "playQueue created but PMS returned no playQueueSelectedItemID"}
    return {"ok": True, "playQueueID": str(queue_id), "selectedItemID": str(selected_id)}


def current_queue_id(client: dict) -> str | None:
    """Return the active playQueueID for `client`, or None if no queue is present.

    Raises CompanionTransportError if the client is unreachable — callers should
    translate that into a transport-specific error rather than an empty-state message.
    """
    from plexctl.playback import _player_get
    data = _player_get(client, "/player/timeline/poll", {"wait": 0})
    timelines = data.get("MediaContainer", {}).get("Timeline", []) or []
    for t in timelines:
        if t.get("type") == "video":
            qid = t.get("playQueueID")
            if qid is not None:
                return str(qid)
    return None


def _client_label(client: dict) -> str:
    return client.get("name") or client.get("machineIdentifier") or "client"


def _transport_error(client: dict, e: CompanionTransportError) -> dict:
    return {"ok": False, "error": f"transport error contacting {_client_label(client)}: {e}"}


def _resolve_queue_id(client: dict) -> tuple[str | None, dict | None]:
    """Return (queue_id, error_dict). Exactly one is non-None."""
    try:
        qid = current_queue_id(client)
    except CompanionTransportError as e:
        return None, _transport_error(client, e)
    if qid is None:
        return None, {"ok": False, "error": f"no active queue on {_client_label(client)}"}
    return qid, None


def show(client: dict) -> dict:
    qid, err = _resolve_queue_id(client)
    if err:
        return err
    data = api.get(f"/playQueues/{qid}")
    mc = data.get("MediaContainer", {})
    selected_id = mc.get("playQueueSelectedItemID")
    raw_items = mc.get("Metadata", [])
    items = [
        {
            "playQueueItemID": item.get("playQueueItemID"),
            "title": item.get("title"),
            "type": item.get("type"),
            "selected": item.get("playQueueItemID") == selected_id,
        }
        for item in raw_items
    ]
    return {"ok": True, "playQueueID": qid, "selectedItemID": selected_id, "items": items}


def shuffle(client: dict) -> dict:
    qid, err = _resolve_queue_id(client)
    if err:
        return err
    api.put(f"/playQueues/{qid}/shuffle")
    return {"ok": True}


def unshuffle(client: dict) -> dict:
    qid, err = _resolve_queue_id(client)
    if err:
        return err
    api.put(f"/playQueues/{qid}/unshuffle")
    return {"ok": True}


def clear(client: dict) -> dict:
    qid, err = _resolve_queue_id(client)
    if err:
        return err
    api.delete(f"/playQueues/{qid}/items")
    return {"ok": True}


def remove_item(client: dict, item_id: str) -> dict:
    qid, err = _resolve_queue_id(client)
    if err:
        return err
    api.delete(f"/playQueues/{qid}/items/{item_id}")
    return {"ok": True}


def add(queue_id: str, rating_key: str) -> dict:
    server_id = _get_server_machine_id()
    if not server_id:
        return {"ok": False, "error": "could not retrieve server machineIdentifier"}

    uri = f"server://{server_id}/com.plexapp.plugins.library/library/metadata/{rating_key}"
    data = api.put(f"/playQueues/{queue_id}", params={"uri": uri})
    mc = data.get("MediaContainer", {})
    if mc.get("playQueueID"):
        return {"ok": True}
    return {"ok": False, "error": "add to queue returned unexpected response"}
