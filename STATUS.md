# plexctl — Project Status

Last updated: 2026-04-16

---

## Complete

All commands implemented and verified against live Apple TV.

### Working commands

| Command | Status |
|---|---|
| `plexctl auth login` | Done |
| `plexctl clients` | Done |
| `plexctl play` | Done |
| `plexctl pause` | Done |
| `plexctl stop` | Done |
| `plexctl seek <mm:ss\|+Xs\|-Xs>` | Done |
| `plexctl next` | Done |
| `plexctl prev` | Done |
| `plexctl volume <0-100>` | Done |
| `plexctl search <query> [--type]` | Done |
| `plexctl play-latest <query>` | Done (shows + movie fallback) |
| `plexctl play-media <ratingKey>` | Done |
| `plexctl queue <ratingKey> [...]` | Done |
| `plexctl queue-show` | Done |
| `plexctl queue-shuffle` | Done |
| `plexctl queue-unshuffle` | Done |
| `plexctl queue-clear` | Done |
| `plexctl queue-remove <itemId>` | Done |
| `plexctl now-playing` | Done |
| `plexctl watched [ratingKey]` | Done (auto-targets playing item) |
| `plexctl unwatched [ratingKey]` | Done (auto-targets playing item) |
| `plexctl rate RATING [ratingKey]` | Done (auto-targets playing item) |
| `plexctl continue-watching` | Done |
| `plexctl history [--limit N]` | Done |

Tests: 108/108 passing (`pipx run pytest tests/`)

### Play queue (added 2026-04-16)

`plexctl queue <ratingKey> [ratingKey ...]  [--client NAME] [--shuffle] [--repeat]`

Creates a Plex play queue from one or more ratingKeys and starts playback immediately.
Episodes autoplay in sequence. Fix required: Apple TV demands `key=/playQueues/{id}`
even when `playQueueID` is also present.

---

## Key discoveries during build

### `X-Plex-Provides: controller` is required
Without this header, PMS returns an empty `/clients` response. Modern clients
(Apple TV, iOS, etc.) only appear when the requester declares itself a controller.

### Direct-to-client HTTP is required
PMS proxy (`GET /player/playback/*` with `X-Plex-Target-Client-Identifier`) times out
for Apple TV. Commands must go directly to the Apple TV's Companion server at its
local IP/port (`172.16.1.53:32500`). The Apple TV still requires `X-Plex-Target-Client-Identifier`
in the direct request headers.

### `type=video` is required on all player commands
Without it, seek, next, prev, and volume silently time out.

### commandID must be monotonically increasing across CLI invocations
The Apple TV tracks the last commandID it processed. A module-level counter that resets
to 0 on each process start causes silent drops. commandID is now seeded from
`int(time.time())` at module load.

### `playMedia` requires `address` and `port` params
The Apple TV needs to know the PMS address to fetch the media. Without these,
`playMedia` returns 400 "Parameter 'address' not found".

### `play-latest` falls back to movies
If no TV show episodes are found, `play-latest` searches movies and plays the top
result. Allows "play Dune" to work without knowing the ratingKey.

---

## Architecture (final)

```
Voice (iPad) → macOS Claude Code → plexctl CLI
                                        │
                            ┌───────────┴──────────────┐
                            │                          │
                    PMS (funtime.local:32400)   Apple TV direct
                    library/search/sessions      172.16.1.53:32500
                    X-Plex-Provides: controller  /player/playback/*
```

---

## Files

```
/Users/rlarsen/Projects/plex-voice/
├── pyproject.toml
├── README.md
├── CLAUDE.md              ← intent grammar for Claude sessions
├── STATUS.md
├── plexctl/
│   ├── __init__.py
│   ├── __main__.py
│   ├── config.py
│   ├── auth.py
│   ├── api.py
│   ├── clients.py
│   ├── library.py
│   ├── playback.py
│   ├── sessions.py
│   └── cli.py
└── tests/
    └── test_intent_examples.py
```

Config: `~/.config/plexctl/config.toml` (chmod 600)
Install: `pipx install -e /Users/rlarsen/Projects/plex-voice`

---

## Client compatibility (final)

| Client | Controllable | Notes |
|---|---|---|
| Apple TV | ✅ | Direct HTTP → 172.16.1.53:32500 |
| Plex Web (Safari/funtime.local) | ❌ | WebSocket pub/sub only — no HTTP endpoint |
| Plex for Mac (slab.maximillian) | ❌ | Does not register as Companion client with remote PMS |
| iPad | ❌ | Streams fine (appears in sessions) but port=null — no Companion endpoint |

Plex Web and Plex for Mac use a WebSocket-based control mechanism that requires a
persistent subscriber session. There is no simple HTTP path for external scripts.

---

## Known bugs

### `plexctl search` rejects empty query

PMS `/library/search?query=` returns HTTP 400 on an empty string. `plexctl search`
passes the query through verbatim so `plexctl search ""` always fails. A non-empty
query is required. There is no browse/list-all path through this command.

**Workaround:** Use a meaningful query term, or hit `/library/sections/{id}/all`
directly with `sort=addedAt:desc` for browse-style access.

**Fix:** Validate query length in the CLI and return `{"ok": false, "error": "query
cannot be empty"}` before making the HTTP request.

Observed: 2026-04-17

---

### `play-latest` starts playback immediately — no ratingKey-only mode

`play-latest` both resolves and plays in one step. When an orchestrator needs the
ratingKey for two shows before building a queue (e.g. "queue Body Cam then Stranger
Things"), calling `play-latest` twice causes both to start playing independently,
overwriting each other on the Apple TV.

**Workaround:** Use `plexctl search <show> --type show` to get ratingKeys, then call
`plexctl queue <k1> <k2>` manually.

**Fix:** Add a `--key-only` flag to `play-latest` (and `play-media`) that prints the
resolved ratingKey as JSON without sending a play command.

Observed: 2026-04-16

---

### `queue.current_queue_id()` always returns None during active playback

PMS `/status/sessions` does not populate `playQueueID` on session metadata, even when
the Apple TV is actively playing from a play queue. `queue.current_queue_id()` reads
that field and always gets `None`, causing `queue-show`, `queue-shuffle`,
`queue-unshuffle`, `queue-clear`, and `queue-remove` to fail with "no active queue"
even when one exists.

**Workaround:** Track the `playQueueID` returned by `queue.create()` or `plexctl queue`
and pass it directly to `queue.add()` or the API if further manipulation is needed in
the same session.

**Fix:** Poll the Apple TV's Companion endpoint (`GET /player/timeline/poll` on
`172.16.1.53:32500`) to retrieve the active `playQueueID` from the client side rather
than from PMS sessions. PMS does not reliably propagate the queue ID to the session
record.

Observed: 2026-04-18

---

### Raw `POST /playQueues` produces a queue with no `Metadata` or `playQueueSelectedItemID`

When creating a play queue via `api.post('/playQueues', ...)` directly (bypassing
`queue.create()`), a subsequent `GET /playQueues/{id}` returns an empty `Metadata`
list and `playQueueSelectedItemID: None`. The queue ID is valid but unusable for
`playMedia` because the Apple TV requires a non-null `playQueueSelectedItemID`.

**Root cause:** The URI passed to `POST /playQueues` must use the fully-qualified
server URI format `server://{machineIdentifier}/com.plexapp.plugins.library/library/metadata/{ratingKey}`.
Skipping `_get_server_machine_id()` and constructing the URI without the correct
machine identifier produces a queue that PMS accepts (200 OK, returns a queue ID) but
cannot populate.

**Workaround:** Always use `queue.create()` (`plexctl/queue.py:5`) which calls
`_get_server_machine_id()` to build the URI correctly.

**Fix:** No code fix needed — the existing `queue.create()` function is correct. Do not
bypass it.

Observed: 2026-04-18

---

### Audio language codes absent from bulk section listing

`GET /library/sections/{id}/all` does not include stream-level metadata in its
response. Audio language codes (`languageCode` on `Stream` objects with
`streamType=2`) are only available by fetching each item individually via
`GET /library/metadata/{ratingKey}`, inside `Media[].Part[].Stream[]`.

**Impact:** Language filtering on a bulk library query requires N+1 requests —
one list call plus one per item. For 21 movies this is acceptable; for large
libraries it would be slow.

**Workaround:** Fetch `/library/metadata/{ratingKey}` per item and inspect
`Media[].Part[].Stream[]` for `streamType=2` entries. Treat missing/`und` codes
as English for practical purposes.

**Fix:** No Plex API fix available. A `plexctl library list --lang en` command
would need to do the same N+1 fetch internally, or cache stream metadata locally.

Observed: 2026-04-18

---

### No CLI command for library browsing / unwatched listing

`plexctl search` requires a non-empty query and returns hub-search results — it
cannot enumerate all items in a section or filter by watch status. There is no
`plexctl list` or `plexctl unwatched` command.

**Impact:** Requests like "show me my unplayed movies" cannot be satisfied by the
CLI. A direct Plex API call is required:
`GET /library/sections/{id}/all?type=1&unwatched=1` with the configured token.

**Fix:** Add `plexctl library list [--section SECTION] [--unwatched] [--sort FIELD]`
that wraps `/library/sections/{id}/all` with optional type/watch-status filtering.
Section IDs would need to be discovered first via `GET /library/sections`.

Observed: 2026-04-18

---

### `seek` is ignored by Apple TV while paused

Sending `seekTo` while the Apple TV is in a paused state has no effect — the
`viewOffset` does not change. The command returns `{"ok": true}` but the seek
is silently dropped.

**Workaround:** Resume playback first (`plexctl play`), wait ~1 second for the
client to enter playing state, then seek, then pause again if needed.

Observed: 2026-04-18

---

## Remaining / future work

- `plexctl seek +Xs` relative seeks require active playback session (expected)
- Volume on Apple TV: tvOS may not honor Plex volume commands vs system volume (untested)
- End-to-end iPad → macOS Claude → plexctl voice relay not yet exercised
- iPad client controllability unverified (expected to work like Apple TV)
