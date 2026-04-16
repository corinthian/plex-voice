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
    """Plex Media Server voice-control CLI."""


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
@click.option("--client", "-c", default=None)
def pause(client):
    """Pause playback."""
    _out(playback.pause(_resolve(client)))


@cli.command()
@click.option("--client", "-c", default=None)
def stop(client):
    """Stop playback."""
    _out(playback.stop(_resolve(client)))


@cli.command()
@click.option("--client", "-c", default=None)
def next(client):
    """Step forward (next chapter / skip)."""
    _out(playback.step_forward(_resolve(client)))


@cli.command()
@click.option("--client", "-c", default=None)
def prev(client):
    """Step back."""
    _out(playback.step_back(_resolve(client)))


@cli.command(context_settings={"ignore_unknown_options": True, "allow_extra_args": True})
@click.argument("position", nargs=-1, type=click.UNPROCESSED)
@click.option("--client", "-c", default=None)
def seek(position, client):
    """Seek to position. Formats: mm:ss  +30s  -1m"""
    if not position:
        raise click.UsageError("POSITION required")
    _out(playback.seek(_resolve(client), " ".join(position)))


@cli.command()
@click.argument("level", type=click.IntRange(0, 100))
@click.option("--client", "-c", default=None)
def volume(level, client):
    """Set volume (0–100)."""
    _out(playback.set_volume(_resolve(client), level))


# --- library ---

@cli.command()
@click.argument("query")
@click.option("--type", "media_type", type=click.Choice(["show", "movie", "episode"]), default=None)
@click.option("--json", "as_json", is_flag=True, default=False, help="Emit full metadata JSON")
def search(query, media_type, as_json):
    """Search the library."""
    results = library.search(query, media_type)
    if as_json:
        print(json.dumps({"ok": True, "results": results}))
        return
    if not results:
        print(json.dumps({"ok": True, "results": [], "note": "no matches"}))
        return
    summary = [{"title": r.get("title"), "type": r.get("type"), "ratingKey": r.get("ratingKey"), "year": r.get("year")} for r in results]
    print(json.dumps({"ok": True, "results": summary}))


@cli.command("play-latest")
@click.argument("query")
@click.option("--client", "-c", default=None)
@click.option("--unwatched", is_flag=True, default=False, help="Force next unwatched episode")
def play_latest(query, client, unwatched):
    """Play the latest/next unwatched episode of a show, or a movie if no show found."""
    item = library.latest_unwatched_episode(query)
    if not item:
        # Fall back to movie search
        movies = library.search(query, media_type="movie")
        if not movies:
            _out({"ok": False, "error": f"nothing found for: {query!r}"})
            return
        item = movies[0]
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
    """Play a specific item by ratingKey."""
    _out(playback.play_media(_resolve(client), rating_key))


@cli.command("queue")
@click.argument("rating_keys", nargs=-1, required=True)
@click.option("--client", "-c", default=None)
@click.option("--shuffle", is_flag=True, default=False)
@click.option("--repeat", is_flag=True, default=False)
def queue_cmd(rating_keys, client, shuffle, repeat):
    """Create a play queue and start playing immediately."""
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
@click.option("--client", "-c", default=None)
def queue_show(client):
    """Show current play queue."""
    _out(_queue_mod.show(_resolve(client)))


@cli.command("queue-shuffle")
@click.option("--client", "-c", default=None)
def queue_shuffle(client):
    """Shuffle the current play queue."""
    _out(_queue_mod.shuffle(_resolve(client)))


@cli.command("queue-unshuffle")
@click.option("--client", "-c", default=None)
def queue_unshuffle(client):
    """Turn off shuffle on the current play queue."""
    _out(_queue_mod.unshuffle(_resolve(client)))


@cli.command("queue-clear")
@click.option("--client", "-c", default=None)
def queue_clear(client):
    """Remove all items from the current play queue."""
    _out(_queue_mod.clear(_resolve(client)))


@cli.command("queue-remove")
@click.argument("item_id")
@click.option("--client", "-c", default=None)
def queue_remove(item_id, client):
    """Remove a specific item from the current play queue by playQueueItemID."""
    _out(_queue_mod.remove_item(_resolve(client), item_id))


@cli.command("now-playing")
@click.option("--client", "-c", default=None)
def now_playing(client):
    """Show what's currently playing."""
    _out(_sessions_mod.now_playing(_resolve(client)))


@cli.command("watched")
@click.argument("rating_key", required=False)
@click.option("--client", "-c", default=None)
def watched(rating_key, client):
    """Mark an item watched. Omit RATING_KEY to target currently playing."""
    target = _resolve(client)
    key = rating_key or _sessions_mod.current_rating_key(target)
    if not key:
        _out({"ok": False, "error": "nothing playing — provide a ratingKey"})
        return
    _out(library.scrobble(key))


@cli.command("unwatched")
@click.argument("rating_key", required=False)
@click.option("--client", "-c", default=None)
def unwatched(rating_key, client):
    """Mark an item unwatched. Omit RATING_KEY to target currently playing."""
    target = _resolve(client)
    key = rating_key or _sessions_mod.current_rating_key(target)
    if not key:
        _out({"ok": False, "error": "nothing playing — provide a ratingKey"})
        return
    _out(library.unscrobble(key))


@cli.command("rate")
@click.argument("rating", type=click.IntRange(0, 10))
@click.argument("rating_key", required=False)
@click.option("--client", "-c", default=None)
def rate_cmd(rating, rating_key, client):
    """Rate an item 0–10. Omit RATING_KEY to target currently playing."""
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
