# plexctl

Command-line Plex remote control designed for voice-driven use via dictation or scripting. Controls playback on LAN clients — Apple TV tested and working.

## Requirements

- Python 3.11+
- pipx
- Plex Media Server on your LAN
- Plex account

## Install

```
pipx install -e /path/to/plex-voice
```

## Setup

```
plexctl auth login
```

Prompts for credentials, writes token to `~/.config/plexctl/config.toml` (chmod 600).

---

## Client Compatibility

| Client | Controllable |
|---|---|
| Apple TV | Yes — default target |
| iPad / iPhone | No — iOS Plex app does not expose a Companion HTTP endpoint |
| Plex for Mac | No — does not register as a Companion client |
| Plex Web | No — WebSocket only |

The Plex app must be open and active on the target device. Default client is Apple TV; override with `--client "Name"`.

---

## Commands

### Auth

```
plexctl auth login
```

### Clients

```
plexctl clients
```

Lists all registered devices and which are currently controllable.

### Transport

```
plexctl play    [--client NAME]
plexctl pause   [--client NAME]
plexctl stop    [--client NAME]
plexctl next    [--client NAME]
plexctl prev    [--client NAME]
```

### Seek

```
plexctl seek <position> [--client NAME]
```

Formats: `1:30` (absolute), `+30s`, `-10s`, `+2m`.

### Volume

```
plexctl volume <0-100> [--client NAME]
```

### Search

```
plexctl search <query> [--type show|movie|episode] [--json]
```

### Play Latest / Next Unwatched

```
plexctl play-latest <query> [--client NAME] [--unwatched]
```

Plays the most recent episode of a show, or next unwatched with `--unwatched`. Falls back to movie search if no show is found.

### Play by Rating Key

```
plexctl play-media <ratingKey> [--client NAME]
```

### Play Queue

```
plexctl queue <ratingKey> [ratingKey ...] [--client NAME] [--shuffle] [--repeat]
```

Creates a play queue from one or more rating keys and starts playback immediately. Episodes autoplay in sequence.

### Queue Management

```
plexctl queue-show      [--client NAME]   # list items in current queue
plexctl queue-shuffle   [--client NAME]   # shuffle on
plexctl queue-unshuffle [--client NAME]   # shuffle off
plexctl queue-clear     [--client NAME]   # remove all items
plexctl queue-remove <playQueueItemID> [--client NAME]
```

Queue ID is resolved at runtime from the active session — no local state.

### Now Playing

```
plexctl now-playing [--client NAME]
```

Returns current title, type, show/season/episode, position, duration, and player state.

### Watched / Unwatched / Rating

```
plexctl watched   [ratingKey] [--client NAME]
plexctl unwatched [ratingKey] [--client NAME]
plexctl rate <0-10> [ratingKey] [--client NAME]
```

Omit `ratingKey` to target the currently playing item.

### Continue Watching

```
plexctl continue-watching
```

### History

```
plexctl history [--limit N]
```

---

## Output

All commands print a single JSON object to stdout.

```json
{"ok": true, ...}
{"ok": false, "error": "..."}
```

Exit code is 0 on success, 1 on error.

---

## Architecture

```
Voice (iPad dictation) → macOS Claude Code session → plexctl
                                                          │
                                              ┌───────────┴──────────────┐
                                              │                          │
                                      PMS (funtime.local:32400)   Apple TV direct
                                      library / search / sessions   172.16.1.53:32500
                                      X-Plex-Provides: controller   /player/playback/*
```

Commands that query media (search, library, sessions, history) go through PMS. Transport commands go directly to the client's Companion HTTP server.

## Technical Notes

- `X-Plex-Provides: controller` is required on all PMS requests or `/clients` returns empty
- All player commands require `type=video` or they silently time out on Apple TV
- `commandID` is seeded from `int(time.time())` to stay monotonically increasing across CLI invocations — Apple TV tracks the last-seen ID and drops stale commands
- `playMedia` and `play_queue` require `address` and `port` params so the Apple TV knows which PMS to fetch from
