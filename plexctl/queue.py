from plexctl import api
from plexctl.playback import _get_server_machine_id


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
            return result

    return {"ok": True, "playQueueID": str(queue_id), "selectedItemID": str(selected_id)}


def current_queue_id(client: dict) -> str | None:
    data = api.get("/status/sessions")
    sessions = data.get("MediaContainer", {}).get("Metadata", [])
    machine_id = client.get("machineIdentifier")
    for session in sessions:
        player = session.get("Player", {})
        if player.get("machineIdentifier") == machine_id:
            qid = session.get("playQueueID")
            return str(qid) if qid is not None else None
    return None


def show(client: dict) -> dict:
    qid = current_queue_id(client)
    if qid is None:
        return {"ok": False, "error": f"no active queue on {client.get('name', client.get('machineIdentifier'))}"}
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
    qid = current_queue_id(client)
    if qid is None:
        return {"ok": False, "error": f"no active queue on {client.get('name', client.get('machineIdentifier'))}"}
    api.put(f"/playQueues/{qid}/shuffle")
    return {"ok": True}


def unshuffle(client: dict) -> dict:
    qid = current_queue_id(client)
    if qid is None:
        return {"ok": False, "error": f"no active queue on {client.get('name', client.get('machineIdentifier'))}"}
    api.put(f"/playQueues/{qid}/unshuffle")
    return {"ok": True}


def clear(client: dict) -> dict:
    qid = current_queue_id(client)
    if qid is None:
        return {"ok": False, "error": f"no active queue on {client.get('name', client.get('machineIdentifier'))}"}
    api.delete(f"/playQueues/{qid}/items")
    return {"ok": True}


def remove_item(client: dict, item_id: str) -> dict:
    qid = current_queue_id(client)
    if qid is None:
        return {"ok": False, "error": f"no active queue on {client.get('name', client.get('machineIdentifier'))}"}
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
