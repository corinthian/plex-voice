# plexctl

A command-line tool for controlling Plex Media Server playback on LAN clients. Designed for voice-driven use via dictation or scripting.

## Prerequisites

- Python 3.11+
- pipx
- Plex Media Server running on your LAN
- Plex account (for authentication token)

## Install

```
pipx install -e /Users/rlarsen/Projects/plex-voice
```

## Setup

```
plexctl auth login
```

Walks through token acquisition and writes `~/.config/plexctl/config.toml`.

## Security

Token stored in `~/.config/plexctl/config.toml` as plaintext. File is chmod 600. Acceptable for a home LAN; do not expose on a shared or public network.

## Client Availability

The Plex app must be open and active on the target device for `plexctl` to control it. Clients that are idle, asleep, or closed will not appear in `plexctl clients`.

## Command Reference

### Auth

```
plexctl auth login
```

Authenticate and store token.

---

### Clients

```
plexctl clients
```

List active Plex clients visible on the LAN.

---

### Playback Transport

```
plexctl play   [--client NAME]
plexctl pause  [--client NAME]
plexctl stop   [--client NAME]
plexctl next   [--client NAME]
plexctl prev   [--client NAME]
```

---

### Seek

```
plexctl seek <mm:ss|+30s|-10s> [--client NAME]
```

Absolute (`1:30`) or relative (`+30s`, `-10s`).

---

### Volume

```
plexctl volume <0-100> [--client NAME]
```

Note: Volume control via the Plex protocol on Apple TV (tvOS) is untested and may not work. The Plex client on tvOS may not expose a volume endpoint. Use native Apple TV remote for volume if this fails.

---

### Search

```
plexctl search <query> [--type show|movie|episode] [--json]
```

Returns matching media from your Plex library. `--json` for machine-readable output.

---

### Play Latest Episode

```
plexctl play-latest <show query> [--client NAME] [--unwatched]
```

Finds the show and plays the most recent episode. With `--unwatched`, plays the next unwatched episode.

---

### Play by Rating Key

```
plexctl play-media <ratingKey> [--client NAME]
```

Plays a specific media item by its Plex rating key (numeric ID from search output).

---

## Apple TV Notes

| Command | Apple TV |
|---|---|
| play / pause / stop | Works |
| next / prev | Works |
| seek | Works |
| play-latest | Works |
| play-media | Works |
| search | Works (library query, not playback) |
| volume | Untested — may not work on tvOS |
