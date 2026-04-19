import json
import sys
import click
from plexctl import playback, library, queue as _queue_mod
from plexctl import clients as _clients_mod
from plexctl import auth as _auth_mod
from plexctl import sessions as _sessions_mod


def _resolve(client_name):
    return _clients_mod.resolve(client_name)


def _out(result: dict):
    print(json.dumps(result))
    if not result.get("ok"):
        sys.exit(1)


@click.group()
def cli():
    """Plex Media Server control CLI — output is JSON, designed for LLM consumption.

    All commands emit a JSON object with an "ok" boolean. On failure, "error"
    contains a human-readable message. Exit code is 1 on failure.
    """


# --- auth ---

@cli.group()
def auth():
    """Authentication commands."""


@auth.command("login")
def auth_login():
    """One-time login — saves token to ~/.config/plexctl/config.toml."""
    _auth_mod.login()


# --- clients ---

@cli.command()
def clients():
    """List all registered clients; shows which are currently controllable."""
    _clients_mod.print_clients()


# --- transport ---

@cli.command()
@click.option("--client", "-c", default=None, help="Target client name (default: Apple TV)")
def play(client):
    """Resume playback."""
    _out(playback.play(_resolve(client)))


@cli.command()
@click.option("--client", "-c", default=None, help="Target client name (default: Apple TV)")
def pause(client):
    """Pause playback."""
    _out(playback.pause(_resolve(client)))


@cli.command()
@click.option("--client", "-c", default=None, help="Target client name (default: Apple TV)")
def stop(client):
    """Stop playback."""
    _out(playback.stop(_resolve(client)))


@cli.command()
@click.option("--client", "-c", default=None, help="Target client name (default: Apple TV)")
def next(client):
    """Step forward (next chapter / skip)."""
    _out(playback.step_forward(_resolve(client)))


@cli.command()
@click.option("--client", "-c", default=None, help="Target client name (default: Apple TV)")
def prev(client):
    """Step back."""
    _out(playback.step_back(_resolve(client)))


@cli.command(context_settings={"ignore_unknown_options": True, "allow_extra_args": True})
@click.argument("position", nargs=-1, type=click.UNPROCESSED)
@click.option("--client", "-c", default=None, help="Target client name (default: Apple TV)")
@click.option("--no-unpause", is_flag=True, default=False, help="Do not auto-resume when seeking while paused")
def seek(position, client, no_unpause):
    """Seek to POSITION in the current media.

    POSITION formats: absolute mm:ss (e.g. 1:30), relative +Ns or -Ns (e.g. +30s, -1m).
    """
    if not position:
        raise click.UsageError("POSITION required")
    _out(playback.seek(_resolve(client), " ".join(position), unpause=not no_unpause))


@cli.command()
@click.argument("level", type=click.IntRange(0, 100))
@click.option("--client", "-c", default=None, help="Target client name (default: Apple TV)")
def volume(level, client):
    """Set volume to LEVEL (integer 0–100)."""
    _out(playback.set_volume(_resolve(client), level))


# --- library ---

@cli.command()
@click.argument("query")
@click.option("--type", "media_type", type=click.Choice(["show", "movie", "episode"]), default=None)
@click.option("--json", "as_json", is_flag=True, default=False, help="Emit full metadata JSON")
def search(query, media_type, as_json):
    """Search the library for QUERY. Returns ratingKey, title, type, and year per result.

    Use --type to restrict to show, movie, or episode. Use --json for full metadata.
    """
    if not query or not query.strip():
        _out({"ok": False, "error": "query cannot be empty"})
        return
    results = library.search(query, media_type)
    if as_json:
        print(json.dumps({"ok": True, "results": results}))
        return
    if not results:
        print(json.dumps({"ok": True, "results": [], "note": "no matches"}))
        return
    summary = [{"title": r.get("title"), "type": r.get("type"), "ratingKey": r.get("ratingKey"), "year": r.get("year")} for r in results]
    print(json.dumps({"ok": True, "results": summary}))


@cli.group("library")
def library_group():
    """Library browsing commands."""


@library_group.command("sections")
def library_sections():
    """List library sections with their section IDs."""
    _out({"ok": True, "sections": library.sections()})


@library_group.command("list")
@click.option("--section", "-s", required=True, help="Section ID (see `plexctl library sections`)")
@click.option("--type", "media_type", type=click.Choice(["show", "movie"]), default=None)
@click.option("--unwatched", is_flag=True, default=False)
@click.option("--sort", default=None, help="e.g. addedAt:desc, titleSort:asc")
def library_list(section, media_type, unwatched, sort):
    """List items in a section, optionally filtered by type or watch status."""
    items = library.list_section(section, media_type=media_type, unwatched=unwatched, sort=sort)
    _out({"ok": True, "count": len(items), "items": items})


@cli.command("metadata")
@click.argument("rating_key")
def metadata_cmd(rating_key):
    """Fetch full metadata for RATING_KEY (includes streams, chapters, ratings)."""
    item = library.metadata(rating_key)
    if not item:
        _out({"ok": False, "error": f"no metadata found for ratingKey: {rating_key}"})
        return
    _out({"ok": True, "metadata": item})


@cli.command("play-latest")
@click.argument("query")
@click.option("--client", "-c", default=None)
@click.option("--unwatched", is_flag=True, default=False, help="Force next unwatched episode")
@click.option("--key-only", is_flag=True, default=False, help="Resolve ratingKey without starting playback")
def play_latest(query, client, unwatched, key_only):
    """Play the next unwatched episode of a show matching QUERY, or a movie if no show found.

    Use --unwatched to force the next unwatched episode even if in-progress exists.
    Use --key-only to resolve the ratingKey without starting playback.
    """
    item = library.latest_unwatched_episode(query)
    if not item:
        # Fall back to movie search
        movies = library.search(query, media_type="movie")
        if not movies:
            _out({"ok": False, "error": f"nothing found for: {query!r}"})
            return
        item = movies[0]
    if key_only:
        _out({
            "ok": True,
            "ratingKey": item.get("ratingKey"),
            "title": item.get("title"),
            "type": item.get("type"),
            "season": item.get("parentIndex"),
            "episode": item.get("index"),
            "year": item.get("year"),
        })
        return
    target = _resolve(client)
    result = playback.play_media(target, item["ratingKey"])
    if result.get("ok"):
        result["playing"] = {
            "title": item.get("title"),
            "type": item.get("type"),
            "season": item.get("parentIndex"),
            "episode": item.get("index"),
            "year": item.get("year"),
            "ratingKey": item.get("ratingKey"),
        }
    _out(result)


@cli.command("play-media")
@click.argument("rating_key")
@click.option("--client", "-c", default=None)
def play_media(rating_key, client):
    """Play a specific item by RATING_KEY. Use `search` or `metadata` to find ratingKeys."""
    _out(playback.play_media(_resolve(client), rating_key))


@cli.command("queue")
@click.argument("rating_keys", nargs=-1, required=True)
@click.option("--client", "-c", default=None, help="Target client name (default: Apple TV)")
@click.option("--shuffle", is_flag=True, default=False, help="Shuffle the queue before playing")
@click.option("--repeat", is_flag=True, default=False, help="Repeat the queue when finished")
def queue_cmd(rating_keys, client, shuffle, repeat):
    """Create a play queue from one or more RATING_KEYS and start playing immediately."""
    q = _queue_mod.create(list(rating_keys), shuffle=shuffle, repeat=repeat)
    if not q.get("ok"):
        _out(q)
        return
    target = _resolve(client)
    result = playback.play_queue(target, q["playQueueID"], q["selectedItemID"])
    if result.get("ok"):
        result["playQueueID"] = q["playQueueID"]
        result["selectedItemID"] = q["selectedItemID"]
    _out(result)


@cli.command("queue-show")
@click.option("--client", "-c", default=None, help="Target client name (default: Apple TV)")
def queue_show(client):
    """Show current play queue. Returns items with playQueueItemID, title, and type."""
    _out(_queue_mod.show(_resolve(client)))


@cli.command("queue-shuffle")
@click.option("--client", "-c", default=None, help="Target client name (default: Apple TV)")
def queue_shuffle(client):
    """Shuffle the current play queue."""
    _out(_queue_mod.shuffle(_resolve(client)))


@cli.command("queue-unshuffle")
@click.option("--client", "-c", default=None, help="Target client name (default: Apple TV)")
def queue_unshuffle(client):
    """Turn off shuffle on the current play queue."""
    _out(_queue_mod.unshuffle(_resolve(client)))


@cli.command("queue-clear")
@click.option("--client", "-c", default=None, help="Target client name (default: Apple TV)")
def queue_clear(client):
    """Remove all items from the current play queue."""
    _out(_queue_mod.clear(_resolve(client)))


@cli.command("queue-remove")
@click.argument("item_id")
@click.option("--client", "-c", default=None)
def queue_remove(item_id, client):
    """Remove ITEM_ID from the current play queue. ITEM_ID is playQueueItemID from queue-show."""
    _out(_queue_mod.remove_item(_resolve(client), item_id))


@cli.command("now-playing")
@click.option("--client", "-c", default=None, help="Target client name (default: Apple TV)")
def now_playing(client):
    """Show what's currently playing. Returns title, type, progress, duration, and ratingKey."""
    _out(_sessions_mod.now_playing(_resolve(client)))


@cli.command("watched")
@click.argument("rating_key", required=False)
@click.option("--client", "-c", default=None, help="Target client name (default: Apple TV)")
def watched(rating_key, client):
    """Mark RATING_KEY as watched. Omit to target the currently playing item."""
    target = _resolve(client)
    key = rating_key or _sessions_mod.current_rating_key(target)
    if not key:
        _out({"ok": False, "error": "nothing playing — provide a ratingKey"})
        return
    _out(library.scrobble(key))


@cli.command("unwatched")
@click.argument("rating_key", required=False)
@click.option("--client", "-c", default=None, help="Target client name (default: Apple TV)")
def unwatched(rating_key, client):
    """Mark RATING_KEY as unwatched. Omit to target the currently playing item."""
    target = _resolve(client)
    key = rating_key or _sessions_mod.current_rating_key(target)
    if not key:
        _out({"ok": False, "error": "nothing playing — provide a ratingKey"})
        return
    _out(library.unscrobble(key))


@cli.command("rate")
@click.argument("rating", type=click.IntRange(0, 10))
@click.argument("rating_key", required=False)
@click.option("--client", "-c", default=None, help="Target client name (default: Apple TV)")
def rate_cmd(rating, rating_key, client):
    """Rate an item RATING (0–10). Omit RATING_KEY to target the currently playing item."""
    target = _resolve(client)
    key = rating_key or _sessions_mod.current_rating_key(target)
    if not key:
        _out({"ok": False, "error": "nothing playing — provide a ratingKey"})
        return
    _out(library.rate(key, rating))


@cli.command("continue-watching")
def continue_watching():
    """List the continue-watching shelf."""
    _out(_sessions_mod.continue_watching())


@cli.command("history")
@click.option("--limit", "-n", default=10, type=int, help="Number of entries to return")
def history(limit):
    """Show recent watch history."""
    _out(_sessions_mod.history(limit))
