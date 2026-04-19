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
| iPad | ❌ Not controllable — no Companion HTTP endpoint (port=null) |
| Plex for Mac | ❌ Not controllable |
| Plex Web (browser) | ❌ Not controllable |

If the user asks to control the Mac or browser player, tell them it is not supported
and suggest switching to Apple TV.

## Default Client

Unless the user specifies a client, always target `Apple TV`. Do not add `--client` if the target is Apple TV — it is the default in config.

If the user says "on the [device]" or "on [name]", add `--client "Name"` matching what `plexctl clients` reports. Only attempt supported clients.

---

## Debug Mode

Debug mode is triggered when input contains either:
- a leading `debug` token (e.g. "debug search Dune"), OR
- `--debug` anywhere in the string

Strip the trigger, set `debug_mode = true`, then parse the remaining text as intent.

In debug mode:
1. Echo the exact `plexctl` command(s) run in a fenced code block **before** output.
2. Restore all technical columns to tables (ratingKey, playQueueItemID, machineIdentifier, etc.).

---

## Output Format

### Row Numbers

For any list output that contains `ratingKey` or `playQueueItemID`, render a leading `#` column and drop the ID column. Keep the row→ID mapping in context so follow-ups like "play #2" or "remove #3" resolve correctly. In debug mode, append the ID column on the right.

### Descriptions

For search results, `play-latest`, `play-media`, and `now-playing`:
- Include a one-line description from Plex's `summary` field.
- Use the first sentence, capped at 120 chars with `…` if needed.
- Render verbatim — no paraphrasing, no commentary, no plot spoilers.
- If the user asks "what's it about?" or "tell me more", return the full untruncated `summary` (and `tagline` if present). Still no added commentary.
- Omit silently if `summary` is missing.

Search must use `plexctl search --json "QUERY"` (not the default summary mode) so `summary` is available inline. For `play-latest`/`play-media`/`now-playing`, make one follow-up call `plexctl metadata <ratingKey>` after the primary command.

### Transport confirmations

Default: one-line confirmation ("Paused.", "Playing.", "Seeked to 2:15.", etc.).
Debug: same line + echoed command.

---

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
| "queue up the next 3 episodes of [show]" | gather ratingKeys with `play-latest --key-only`, then `plexctl queue <k1> <k2> <k3>` |
| "shuffle [show]" | gather episode keys, then `plexctl queue <keys...> --shuffle` |

### Search / Query

| Speech | Command |
|---|---|
| "search for [query]" | `plexctl search --json "[query]"` |
| "find [show or movie]" | `plexctl search --json "[query]"` |
| "what's playing", "what's on" | `plexctl now-playing` |

Search output — default table:

| # | Title | Year | Type | Description |
|---|---|---|---|---|
| 1 | Dune (2021) | 2021 | movie | A noble family becomes embroiled in a war… |

### Status & History

| Speech | Command |
|---|---|
| "continue watching", "what can I continue" | `plexctl continue-watching` |
| "what did I watch", "show history" | `plexctl history [--limit N]` |

History default table: `# | Title | Show | Type | Viewed`
Continue-watching default table: `# | Title | Show | S/E | Progress`
(No per-item description fetch — too slow for bulk lists.)

### Library Browsing

| Speech | Command |
|---|---|
| "list my libraries", "what sections do I have" | `plexctl library sections` |
| "list movies", "show all shows" | `plexctl library list --section ID [--type show\|movie] [--unwatched]` |
| "get metadata for [item]" | `plexctl metadata <ratingKey>` |

Use `library sections` to discover section IDs before `library list`. Row `#` in sections output maps to section key.

### Rating & Watched Status

RATING_KEY is optional — omit to auto-target the currently playing item.

| Speech | Command |
|---|---|
| "mark this watched" | `plexctl watched [RATING_KEY]` |
| "mark as unwatched" | `plexctl unwatched [RATING_KEY]` |
| "rate this 8" | `plexctl rate 8 [RATING_KEY]` |

### Client List

| Speech | Command |
|---|---|
| "list clients", "what clients are available" | `plexctl clients` |

### Queue Management

| Speech | Command |
|---|---|
| "show the queue", "what's in the queue" | `plexctl queue-show` |
| "shuffle the queue" | `plexctl queue-shuffle` |
| "stop shuffling", "unshuffle" | `plexctl queue-unshuffle` |
| "clear the queue" | `plexctl queue-clear` |
| "remove item [N] from the queue" | `plexctl queue-remove <playQueueItemID>` — resolve N from row map |

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
| "search for Dune" | `plexctl search --json "Dune"` |
| "what's playing" | `plexctl now-playing` |
| "list available clients" | `plexctl clients` |
| "debug search Dune" | debug mode: echo command, show ratingKey column |
| "search Dune --debug" | same as above |

---

## Ambiguity Rules

**Client not specified:** Default to Apple TV. Do not add `--client`.

**Show name unclear:** Run `plexctl search --json "<heard text>"` and show results table. Confirm the correct title before running `play-latest`.

**Volume relative ("louder", "quieter", "turn it up"):** Ask for an absolute level, or estimate current ± 10 if you have context. Do not silently pick an arbitrary value.

**Ambiguous command ("play it"):** If context (recent search or session) makes the target clear, proceed. Otherwise ask.

**Multiple matching clients:** Run `plexctl clients` and ask which one.

**"play #N" / "remove #N":** Resolve N against the most recent list's row-map in context. If no list is in context, ask the user to search first.

---

## Execution

Once intent is clear and unambiguous, run the command directly without asking for confirmation. Only pause for confirmation when the action is destructive (`stop`, `queue-clear`) or the target is genuinely unclear.
