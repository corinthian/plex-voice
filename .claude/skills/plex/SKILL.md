---
name: plex
description: >
  Plex Media Server control via plexctl CLI. TRIGGER when: user wants to
  control playback, search the library, manage queues, check history,
  rate or mark items, or says "/plex". Parses voice/text intent into
  plexctl commands and formats output as tables where applicable.
  Default client: Apple TV.
argument-hint: "[voice phrase | command | query]"
allowed-tools:
  - "Bash(plexctl:*)"
---

# Plex Skill

Parse the user's intent and run the appropriate `plexctl` command.
Format all structured output as Markdown tables. Include year for movies: **Title (Year)**.

---

## Debug Mode

Debug mode is triggered when `$ARGUMENTS` contains either:
- a leading `debug` token (e.g. `debug search Dune`), OR
- `--debug` anywhere in the string (e.g. `search Dune --debug`)

Strip the trigger word/flag before parsing intent, then set `debug_mode = true` for the response.

In debug mode:
1. Echo the exact shell command(s) run in a fenced code block **before** the formatted output.
2. Restore all technical columns to tables (see per-command specs below).

Default mode (no trigger): hide all internal IDs, show row numbers instead.

---

## Row-Number Pattern

For any list that contains `ratingKey` or `playQueueItemID`, always render a leading `#` column (`1, 2, 3, ...`). Keep the `ratingKey`/`playQueueItemID`→`#` mapping in your conversation context so follow-ups like "play #2" or "remove #3" resolve to the correct ID without displaying it to the user.

In debug mode, append the ID column to the right of the existing columns.

---

## Clients

| Client | Controllable | Notes |
|---|---|---|
| Apple TV | Yes (default) | Omit `--client` |
| iPad | No | No Companion HTTP endpoint |
| Plex for Mac | No | Not supported |
| Plex Web | No | Not supported |

Use `plexctl clients` if the user asks what's available or if a client is unclear.

---

## Command Reference

### Transport

| Intent | Command |
|---|---|
| pause / pause it | `plexctl pause` |
| play / resume / unpause | `plexctl play` |
| stop | `plexctl stop` |
| next / skip / skip forward / next episode | `plexctl next` |
| previous / go back / back | `plexctl prev` |

Default output: one-line confirmation ("Paused.", "Playing.", "Stopped.", etc.).
Debug output: confirmation line + echoed command.

### Volume

Volume is absolute only (0–100). No relative API exists.

| Intent | Command |
|---|---|
| "set volume to N" / "volume N" | `plexctl volume N` |
| "volume up" / "louder" | ask for absolute level, or current + 10 if known |
| "volume down" / "quieter" | ask for absolute level, or current − 10 if known |

Default output: "Volume set to N." Debug output: same + echoed command.

### Seek

| Intent | Command |
|---|---|
| "seek to 1:30" / "go to 1 minute 30" | `plexctl seek 1:30` |
| "skip ahead 30 seconds" | `plexctl seek +30s` |
| "go back 10 seconds" / "rewind 10" | `plexctl seek -10s` |

Parse natural language: "two minutes" → `2:00`, "a minute thirty" → `1:30`.
Default output: "Seeked to mm:ss." Debug output: same + echoed command.

### Library Search

```
plexctl search --json "QUERY" [--type show|movie|episode]
```

Always use `--json` so `summary` is available for the Description column. Do not pass `--json` visibly to the user — it's an implementation detail.

**Default table:**

| # | Title | Year | Type | Description |
|---|---|---|---|---|
| 1 | Dune (2021) | 2021 | movie | A noble family becomes embroiled in a war for control over the galaxy's most valuable asset. |

- Description: first sentence of `summary`, capped at 120 chars with `…` if needed. Omit column entirely if all results lack a summary.
- Row numbers map to `ratingKey` in your context.

**Debug table:** same columns plus `ratingKey` on the far right.

If user says "what's it about?" / "tell me more about #N" / "full description" / "longer description" — return the full untruncated `summary` (and `tagline` if present). No additional commentary.

### Play Latest / Next Episode

```
plexctl play-latest "SHOW" [--unwatched] [--key-only] [--client "Name"]
```

- Default: plays the next unwatched episode (or most recently aired if all watched).
- `--unwatched`: force next unwatched only, fail if none.
- `--key-only`: resolve without starting playback — useful when gathering keys for a queue. Always show the ratingKey in this mode regardless of debug state.
- Falls back to movie search if no show match found.

After a successful play, make one follow-up call `plexctl metadata <ratingKey>` to get `summary`.

**Default output:**

```
Now playing: S02E05 — Episode Title
Description: First sentence of summary here.
```

Or for a movie:
```
Now playing: Dune (2021)
Description: First sentence of summary here.
```

**Debug output:** same block + `ratingKey:` line + echoed command(s).

### Play by ratingKey

```
plexctl play-media RATING_KEY [--client "Name"]
```

Use when you already have a ratingKey. After playing, fetch `plexctl metadata <ratingKey>` and display Description line.
Default output: same block as play-latest. Debug: + ratingKey + echoed commands.

### Queue

```
plexctl queue KEY1 KEY2 ... [--shuffle] [--repeat] [--client "Name"]
```

To queue multiple episodes: search or use `play-latest --key-only` to gather keys first.
Default output: "Queue created — N items." Debug: + `playQueueID` + `selectedItemID` + echoed command.

### Queue Management

| Intent | Command |
|---|---|
| show the queue / what's in the queue | `plexctl queue-show` |
| shuffle the queue | `plexctl queue-shuffle` |
| stop shuffling / unshuffle | `plexctl queue-unshuffle` |
| clear the queue | `plexctl queue-clear` |
| remove item N from the queue | `plexctl queue-remove ITEM_ID` |

**Default queue-show table:**

| # | Title | Type | Selected |
|---|---|---|---|
| 1 | Episode Title | episode | ✓ |

Row numbers map to `playQueueItemID` in your context. Debug: add `playQueueItemID` column on the right.

For shuffle/unshuffle/clear/remove — default: one-line confirmation. Debug: + echoed command.

### Now Playing

```
plexctl now-playing [--client "Name"]
```

After getting the ratingKey from the result, make one follow-up call `plexctl metadata <ratingKey>` for `summary`.

**Default output block:**
```
State:       Playing
Title:       Episode Title  (or  Movie Title (Year))
Show:        Show Name  (TV only)
Progress:    mm:ss / mm:ss
Description: First sentence of summary here.
```

Omit `Description:` line if `summary` is missing. Omit `Show:` line for movies.

**Debug:** same block + `ratingKey:` line + echoed command(s).

### Watch Status & Rating

RATING_KEY is optional — omit to auto-target currently playing item.

| Intent | Command |
|---|---|
| "mark this watched" | `plexctl watched [RATING_KEY]` |
| "mark as unwatched" | `plexctl unwatched [RATING_KEY]` |
| "rate this 8" | `plexctl rate 8 [RATING_KEY]` |

Rating scale is 0–10.
Default output: "Marked watched.", "Marked unwatched.", "Rated 8/10." Debug: + echoed command.

### History

```
plexctl history [--limit N]
```

Default: 10 entries. No per-item metadata fetch (too slow).

**Default table:**

| # | Title | Show | Type | Viewed |
|---|---|---|---|---|
| 1 | Episode Name | Show Title | episode | 2026-04-18 |
| 2 | Movie Name (2021) | — | movie | 2026-04-17 |

Row numbers map to `ratingKey`. Debug: add `ratingKey` column on the right.

### Continue Watching

```
plexctl continue-watching
```

No per-item metadata fetch.

**Default table:**

| # | Title | Show | S/E | Progress |
|---|---|---|---|---|
| 1 | Episode Title | Show Name | S02E04 | 32:10 / 48:00 |

Row numbers map to `ratingKey`. Debug: add `ratingKey` column on the right.

### Clients

```
plexctl clients
```

**Default table:**

| Name | Product | Active | Last Seen |
|---|---|---|---|
| Apple TV | Plex for Apple TV | Yes | 2026-04-18 |

**Debug table:** same + `machineIdentifier`, `baseurl`, `clientIdentifier` columns appended.

### Library Browsing

```
plexctl library sections
plexctl library list --section ID [--type show|movie] [--unwatched] [--sort FIELD:dir]
```

**Default sections table:**

| # | Title | Type |
|---|---|---|
| 1 | Movies | movie |

Row `#` maps to section `key` (used in `library list --section`). Debug: add `key` column.

**Default library list table:**

| # | Title | Year | Type | Watched |
|---|---|---|---|---|
| 1 | Dune (2021) | 2021 | movie | Yes |

Row `#` maps to `ratingKey`. `Watched` = viewCount > 0. Debug: add `ratingKey` column.

### Metadata

```
plexctl metadata RATING_KEY
```

Returns full stream info. Used internally for summaries and language filtering. When surfaced directly to the user, present key fields:
- Title, Year, Type, Rating, Studio
- Audio streams (language, codec, channels)
- Subtitle streams
- Full `summary` (untruncated)
- No raw GUIDs, `key`, `thumb`, `art` unless debug mode.

---

## Formatting Rules

1. **Tables**: Use for any list output (search results, history, queue, clients, continue-watching, library).
2. **Movie titles**: Always append year when available — **Title (Year)**.
3. **TV episodes**: Show as "S01E04 — Episode Title" in tables, plain "Episode Title" in now-playing.
4. **Progress**: Convert ms to `mm:ss`. Formula: `ms // 1000 // 60`:`(ms // 1000) % 60`.
5. **Dates**: Format `viewedAt`/`lastSeen`/`addedAt` (Unix timestamp) as `YYYY-MM-DD`.
6. **Errors**: Show the `error` field from the JSON response verbatim. Do not paraphrase.
7. **Descriptions**: Render Plex's `summary` verbatim — first sentence, ≤120 chars, in default mode. Do not paraphrase, add commentary, or editorialize. If the user asks for more detail, show the full untruncated `summary` (and `tagline` if present). Never volunteer plot commentary, reception notes, or spoiler-adjacent information Plex did not supply.

---

## Ambiguity Rules

- **Client not specified**: default to Apple TV, omit `--client`.
- **Show name unclear**: run `plexctl search --json "QUERY"` first, present results table, confirm before playing.
- **Volume relative**: ask for absolute level, or estimate current ± 10 if known from `now-playing`.
- **"Play it" with no context**: ask what to play.
- **Multiple show matches**: show results table, ask user to confirm which one.
- **"play #N" / "remove #N"**: resolve `N` against the most recent list's row-map in context. If no list is in context, ask the user to search first.

---

## Pre-Action State Check

Before any playback-changing command (`play`, `pause`, `stop`, `next`, `prev`, `seek`, `play-latest`, `play-media`, `queue`), run `plexctl now-playing` and `plexctl continue-watching` first.

Use the results to:
- Avoid interrupting active playback unintentionally.
- Resolve ambiguous "play it" / "resume" / "keep watching" intents against the existing watch-next context.
- Surface relevant state to the user when the requested action conflicts with what's already playing.

Skip the check for pure info queries: `search`, `history`, `clients`, `library` (sections/list), `metadata`, `now-playing` itself, `continue-watching` itself, `queue-show`.

---

## Execution Policy

Once intent is unambiguous, run the command immediately without asking.
Only pause for confirmation when:
- Action is destructive (`stop`, `queue-clear`)
- Target client is genuinely unclear

---

## Invocation

User invoked `/plex $ARGUMENTS`

1. Check for `debug` leading token or `--debug` flag — set `debug_mode`, strip the trigger.
2. If remaining `$ARGUMENTS` is empty → run `plexctl now-playing` and show result.
3. Otherwise → parse remaining text as voice/text intent, map to command(s), run them.
4. Format output per the specs above, applying debug columns and command echo if `debug_mode` is true.
