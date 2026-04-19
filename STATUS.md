# plexctl — Project Status

Last updated: 2026-04-19

---

## Outstanding bugs

### Raw `POST /playQueues` bypassing `queue.create()` — skill/orchestration concern

When creating a play queue via `api.post('/playQueues', ...)` directly (bypassing
`queue.create()`), a subsequent `GET /playQueues/{id}` returns an empty `Metadata`
list and `playQueueSelectedItemID: None`. The queue ID is valid but unusable for
`playMedia` because the Apple TV requires a non-null `playQueueSelectedItemID`.

**Root cause:** The URI passed to `POST /playQueues` must use the fully-qualified
server URI format `server://{machineIdentifier}/com.plexapp.plugins.library/library/metadata/{ratingKey}`.
Skipping `_get_server_machine_id()` and constructing the URI without the correct
machine identifier produces a queue that PMS accepts (200 OK, returns a queue ID) but
cannot populate.

**Fix:** No plexctl code change needed — `queue.create()` (`plexctl/queue.py:5`) is
correct. Fix is in the skill/orchestrator: always shell out to `plexctl queue <keys...>`,
never bypass it with raw curl or api.post calls against `/playQueues`.

Observed: 2026-04-18

---

### Audio language codes absent from bulk section listing

`GET /library/sections/{id}/all` does not include stream-level metadata. Audio
language codes (`languageCode` on `Stream` objects with `streamType=2`) are only
available via `GET /library/metadata/{ratingKey}` inside `Media[].Part[].Stream[]`.

**Impact:** Language filtering requires N+1 requests — one `plexctl library list`
call plus one `plexctl metadata <ratingKey>` per item. For 21 movies this is
acceptable; for large libraries it would be slow.

**Fix:** No Plex API fix available. Skill-side workaround: call `library list` once,
then `plexctl metadata <ratingKey>` per item and filter on `streamType=2` /
`languageCode`. `plexctl metadata` command is now available for this purpose.

Observed: 2026-04-18

---

### `seek` while paused — 1s resume heuristic may not be sufficient

`plexctl seek` now auto-resumes → seeks → re-pauses when the Apple TV is paused.
The 1-second sleep between `play` and `seekTo` is a heuristic. If the Apple TV
is slow to enter playing state, the seek may still drop silently.

**Workaround:** Use `plexctl seek --no-unpause` to disable auto-resume and manage
play/pause manually.

Observed: 2026-04-18

---

## Future work

- Volume on Apple TV: tvOS may not honor Plex volume commands vs system volume (untested)
- End-to-end iPad → macOS Claude → plexctl voice relay not yet exercised
- Skill grammar update needed: document `plexctl metadata`, `plexctl library sections/list`,
  and the N+1 pattern for language-filtered requests

---

## Working commands

Tests: 111/111 passing (`pipx run pytest tests/`)

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
| `plexctl library sections` | Done |
| `plexctl library list --section ID [--unwatched] [--sort]` | Done |
| `plexctl metadata <ratingKey>` | Done (full stream info for language filtering) |

---

## Resolved bugs

| Bug | Fixed in | Notes |
|---|---|---|
| `plexctl search ""` crashes | commit `07ef785` | Empty-query guard in `cli.py:109` |
| `play-latest` no `--key-only` mode | commit `07ef785` | Flag in `cli.py:127` |
| `post/put/delete` crash on empty body | commit `1ce7c2d` | `api.py:70,88,106` |
| Hand-built JSON f-strings in api.py | commit `1ce7c2d` | All 10 sites use `json.dumps` |
| `str(None)` coercion in queue.create | commit `1ce7c2d` | `queue.py:33` None guard |
| Dead `active_by_id` in clients.py | commit `1ce7c2d` | Deleted |
| TOML escaping in config.save | commit `1ce7c2d` | `config.py:26` |
| `config.require()` raw f-string | commit `f9f4eb9`+ | `config.py:37` uses `json.dumps` |
| `current_queue_id()` polls PMS | commit `f9f4eb9`+ | Now polls `/player/timeline/poll` on Apple TV |
| No library browsing / unwatched list | commit `f9f4eb9`+ | `plexctl library sections/list` added |
| No per-item metadata command | commit `f9f4eb9`+ | `plexctl metadata <ratingKey>` added |
| `seek` ignored while paused | commit `f9f4eb9`+ | Auto-resume workaround in `playback.py` |

---

## Architecture

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

## Client compatibility

| Client | Controllable | Notes |
|---|---|---|
| Apple TV | ✅ | Direct HTTP → 172.16.1.53:32500 |
| Plex Web (Safari/funtime.local) | ❌ | WebSocket pub/sub only — no HTTP endpoint |
| Plex for Mac (slab.maximillian) | ❌ | Does not register as Companion client with remote PMS |
| iPad | ❌ | Streams fine (appears in sessions) but port=null — no Companion endpoint |

Plex Web and Plex for Mac use a WebSocket-based control mechanism that requires a
persistent subscriber session. There is no simple HTTP path for external scripts.

---

## Key discoveries

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
