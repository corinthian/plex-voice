# plexctl

Control your Plex server from the command line — or by talking to Claude Code.

`plexctl` is a small Python CLI that drives Plex playback on LAN clients and emits JSON on every call, so it plays nicely with scripts, automation, and LLMs. It ships with a `/plex` Claude Code skill that turns phrases like *"play the next unwatched episode of The Bear"* into the right `plexctl` invocation.

## Why

Plex's own apps are great for watching, not so great for bulk work or talking to. With `plexctl` + Claude Code you can drive your library with sentences instead of clicks.

A few concrete workflows this opens up:

- *"Go through every foreign-language film in my library and turn on English subtitles by default."* Claude walks the relevant section, pulls each movie's metadata, finds the English subtitle stream, and flips it to the default — one request instead of clicking through each movie's audio/subtitle panel.
- *"Queue the next three unwatched episodes of Severance on the Apple TV."* The skill resolves ratingKeys, builds the play queue, and starts playback in one shot.
- *"Rate the current movie 9/10."* The skill auto-targets whatever's on screen; no ratingKey hunt, no remote.
- *"What haven't I watched from my sci-fi shelf this year?"* List + filter + format, all from one prompt.

The voice-from-the-couch workflow works too, but the bulk-library work is where this actually earns its keep.

## What works right now

| Client | Controllable? |
|---|---|
| Apple TV | Yes — the default, well-tested target |
| iPad / iPhone | No — iOS Plex has no Companion HTTP endpoint |
| Plex for Mac | No — it is a WebSocket client, not HTTP |
| Plex Web (browser) | No — same story |

The Plex app must be open and active on the target device.

## Install

```
pipx install -e /path/to/plex-voice
plexctl auth login
```

`auth login` prompts for plex.tv credentials, exchanges them for a token, and writes it to `~/.config/plexctl/config.toml` (chmod 600). Your password never touches disk.

## Using it

The CLI is self-describing:

```
plexctl --help
```

Most commands accept `--client NAME`. Omit it and Apple TV is assumed.

Quick tour:

```
plexctl pause
plexctl seek +30s
plexctl volume 40
plexctl play-latest "Strange New Worlds" --unwatched
plexctl queue-show
plexctl now-playing
plexctl history --limit 5
```

Every command prints exactly one JSON object to stdout. `{"ok": true, ...}` on success, `{"ok": false, "error": "..."}` + exit code 1 on failure. That is the whole contract.

## Voice control via Claude Code

This repo ships a Claude Code skill at `.claude/skills/plex/SKILL.md`. Invoke `/plex` inside Claude Code and it maps spoken intent onto `plexctl` commands:

```
/plex pause the Apple TV
/plex what's playing
/plex play the next unwatched Severance
/plex shuffle the queue
/plex debug search Dune           # echo command + show ratingKey columns
```

The skill handles row-number mapping (*"play #2"*, *"remove #3"*), movie-year formatting, and sane defaults when intent is ambiguous.

## Commands at a glance

- **Auth / setup** — `auth login`, `clients`
- **Transport** — `play`, `pause`, `stop`, `next`, `prev`, `seek`, `volume`
- **Library** — `search`, `library sections`, `library list`, `metadata`
- **Targeted playback** — `play-latest`, `play-media`, `queue`
- **Queue control** — `queue-show`, `queue-shuffle`, `queue-unshuffle`, `queue-clear`, `queue-remove`
- **Status** — `now-playing`, `continue-watching`, `history`
- **Watch state** — `watched`, `unwatched`, `rate`

Full reference, architecture, and internals in [DOCS.md](DOCS.md). Rolling bug / future-work list in [STATUS.md](STATUS.md).

## Requirements

- Python 3.11+
- pipx (or any venv — `pip install -e .` works fine)
- A Plex Media Server reachable on the LAN
- A Plex account
