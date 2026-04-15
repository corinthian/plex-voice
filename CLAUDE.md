# plexctl Intent Parser — Instructions for Claude Code

## Session Setup

This macOS Claude Code session should be named **plex** (use `/rename plex` if not already set).
The iPad connects to it via `/remote-control`. Voice input arrives as relayed messages from the iPad Claude session.

You receive voice transcripts relayed from an iPad. Your job is to parse each phrase into a `plexctl` shell command and either execute it or confirm with the user.

## Supported Clients

Only the following clients can be controlled:

| Client | Status |
|---|---|
| Apple TV | ✅ Default target |
| iPad | ✅ Likely works — Plex app must be open |
| Plex for Mac | ❌ Not controllable |
| Plex Web (browser) | ❌ Not controllable |

If the user asks to control the Mac or browser player, tell them it is not supported
and suggest switching to Apple TV or iPad.

## Default Client

Unless the user specifies a client, always target `Apple TV`. Do not add `--client` if the target is Apple TV — it is the default in config.

If the user says "on the [device]" or "on [name]", add `--client "Name"` matching what `plexctl clients` reports. Only attempt supported clients.

## Intent Grammar

### Transport

| Speech | Command |
|---|---|
| "pause", "pause it", "pause the TV" | `plexctl pause` |
| "play", "resume", "unpause" | `plexctl play` |
| "stop" | `plexctl stop` |
| "next", "skip", "skip forward", "next episode" | `plexctl next` |
| "previous", "go back", "last episode", "back" | `plexctl prev` |

### Volume

plexctl only accepts absolute values (0–100). There is no relative volume API.

| Speech | Command |
|---|---|
| "set volume to N", "volume N" | `plexctl volume N` |
| "volume up", "louder" | Ask: "What volume level?" or default to current + 10 if current is known |
| "volume down", "quieter" | Ask: "What volume level?" or default to current - 10 if current is known |

If current volume is unknown, ask the user for an absolute level. Do not guess blindly.

### Seek

| Speech | Command |
|---|---|
| "seek to 1:30", "go to 1 minute 30" | `plexctl seek 1:30` |
| "skip ahead 30 seconds" | `plexctl seek +30s` |
| "go back 10 seconds", "rewind 10" | `plexctl seek -10s` |

Parse natural time expressions: "two minutes" → `2:00`, "a minute and a half" → `1:30`.

### Show Playback

| Speech | Command |
|---|---|
| "play [show name]" | `plexctl play-latest "[show name]"` |
| "play the latest [show]" | `plexctl play-latest "[show]"` |
| "play next episode of [show]" | `plexctl play-latest "[show]" --unwatched` |
| "play the next unwatched [show]" | `plexctl play-latest "[show]" --unwatched` |
| "play it on [client]" (after search) | add `--client "[client]"` |

### Search / Query

| Speech | Command |
|---|---|
| "search for [query]" | `plexctl search "[query]"` |
| "find [show or movie]" | `plexctl search "[query]"` |
| "what's playing", "what's on" | `plexctl clients` (note: full session info not yet implemented; use as proxy) |

### Client List

| Speech | Command |
|---|---|
| "list clients", "what clients are available" | `plexctl clients` |

---

## Example Mappings

| Voice Input | plexctl Command |
|---|---|
| "pause the Apple TV" | `plexctl pause` |
| "resume" | `plexctl play` |
| "stop playback" | `plexctl stop` |
| "skip forward" | `plexctl next` |
| "go back" | `plexctl prev` |
| "set volume to 40" | `plexctl volume 40` |
| "seek to 2:15" | `plexctl seek 2:15` |
| "skip ahead 30 seconds" | `plexctl seek +30s` |
| "go back 10 seconds" | `plexctl seek -10s` |
| "play Strange New Worlds" | `plexctl play-latest "Strange New Worlds"` |
| "play the latest Strange New Worlds on the TV" | `plexctl play-latest "Strange New Worlds" --client "Apple TV"` |
| "play the next unwatched episode of The Bear" | `plexctl play-latest "The Bear" --unwatched` |
| "search for Dune" | `plexctl search "Dune"` |
| "what's playing" | `plexctl clients` |
| "list available clients" | `plexctl clients` |

---

## Ambiguity Rules

**Client not specified:** Default to Apple TV. Do not add `--client`.

**Show name unclear:** Run `plexctl search "<heard text>"` and show results. Confirm the correct title before running `play-latest`.

**Volume relative ("louder", "quieter", "turn it up"):** Ask for an absolute level, or estimate current ± 10 if you have context. Do not silently pick an arbitrary value.

**Ambiguous command ("play it"):** If context (recent search or session) makes the target clear, proceed. Otherwise ask.

**Multiple matching clients:** Run `plexctl clients` and ask which one.

---

## Execution

Once intent is clear and unambiguous, run the command directly without asking for confirmation. Only pause for confirmation when the action is destructive (stop) or the target is genuinely unclear.
