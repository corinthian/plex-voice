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

Tests: 75/75 passing (`pipx run pytest tests/`)

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
| iPad | untested | Likely works same as Apple TV when app is open |

Plex Web and Plex for Mac use a WebSocket-based control mechanism that requires a
persistent subscriber session. There is no simple HTTP path for external scripts.

---

## Remaining / future work

- `plexctl seek +Xs` relative seeks require active playback session (expected)
- Volume on Apple TV: tvOS may not honor Plex volume commands vs system volume (untested)
- End-to-end iPad → macOS Claude → plexctl voice relay not yet exercised
- iPad client controllability unverified (expected to work like Apple TV)
- No `now-playing` command (`what's playing` maps to `clients` as proxy)
