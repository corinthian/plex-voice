# plexctl — Technical Documentation

Reference for hacking on `plexctl` or integrating it into another tool.

Intro and install live in [README.md](README.md); rolling bug / future-work list lives in [STATUS.md](STATUS.md).

---

## Architecture

```
Voice (iPad dictation) → macOS Claude Code session → plexctl CLI
                                                         │
                                             ┌───────────┴───────────┐
                                             │                       │
                                     Plex Media Server        Apple TV (direct)
                                     (X-Plex-Provides:         Companion HTTP
                                      controller)               :32500
                                                                /player/playback/*
```

Two surfaces, one binary:

- **Library-side commands** (`search`, `library`, `history`, `continue-watching`, `now-playing`, `metadata`, `watched`, `unwatched`, `rate`) hit PMS.
- **Player-side commands** (`play`, `pause`, `stop`, `next`, `prev`, `seek`, `volume`, `play-media`, `play-queue`) talk directly to the Apple TV's Companion HTTP server, bypassing PMS proxying (which silently times out on tvOS).
- **Queue management** (`queue-show`, `queue-shuffle`, `queue-unshuffle`, `queue-clear`, `queue-remove`) uses both — timeline polling on the client to find the active queue, then PMS `/playQueues/*` to mutate it.

---

## Module layout

| Module | Purpose |
|---|---|
| `plexctl.cli` | Click entry points — argument parsing, JSON output, exit-code discipline |
| `plexctl.config` | TOML config load/save at `~/.config/plexctl/config.toml` |
| `plexctl.auth` | One-time `plex.tv/users/sign_in.json` exchange + PMS reachability check |
| `plexctl.api` | HTTP wrappers for PMS (`get`, `post`, `put`, `delete`) and plex.tv (`plex_tv_get`) |
| `plexctl.clients` | Client discovery — merges PMS `/clients` with plex.tv `/devices.json`; resolves targets |
| `plexctl.playback` | Direct-to-client Companion commands and seek/volume helpers |
| `plexctl.sessions` | `/status/sessions`, `/status/sessions/history/all`, `/hubs/continueWatching` |
| `plexctl.library` | `/hubs/search`, `/library/sections/*`, metadata, scrobble, rate |
| `plexctl.queue` | `/playQueues/*` — create, show, mutate, remove, rollback |

Everything downstream of `cli.py` returns plain dicts; `_out()` in `cli.py` is the single place that converts to JSON and sets the exit code.

---

## JSON output contract

Every CLI invocation writes exactly one line of JSON to stdout and nothing else. Shape:

```json
{"ok": true, "…command-specific keys…": "…"}
```

or

```json
{"ok": false, "error": "human-readable message"}
```

Exit code: `0` on success, `1` on failure. Error strings are intended to be shown verbatim to the user — the `/plex` skill does this.

---

## Command reference

All commands accept `--client / -c NAME` unless noted; omitted `--client` uses `default_client` from the config.

### Auth

| Command | Args / flags | Returns |
|---|---|---|
| `auth login` | (interactive) | `{ok, message}` on success; writes config file |

### Clients

| Command | Args / flags | Returns |
|---|---|---|
| `clients` | — | `{ok, clients: [...], note}` |

Each client entry: `name`, `product`, `version`, `lastSeen`, `active`, `machineIdentifier`, `baseurl`, `ambiguous`.

### Transport

| Command | Returns |
|---|---|
| `play` | `{ok}` |
| `pause` | `{ok}` |
| `stop` | `{ok}` |
| `next` | `{ok}` |
| `prev` | `{ok}` |
| `seek POSITION [--no-unpause]` | `{ok}` or `{ok: false, error}` |
| `volume LEVEL` | `{ok}` (LEVEL is IntRange 0–100) |

`POSITION` accepts `mm:ss`, `h:mm:ss`, `+Ns` / `-Ns` (seconds), `+Nm` / `-Nm` (minutes).

### Library

| Command | Args / flags | Returns |
|---|---|---|
| `search QUERY` | `--type {show,movie,episode}` `--json` | `{ok, results: [...]}` |
| `library sections` | — | `{ok, sections: [...]}` |
| `library list --section ID` | `--type {show,movie}` `--unwatched` `--sort FIELD:dir` | `{ok, count, items: [...]}` |
| `metadata RATING_KEY` | — | `{ok, metadata: {...}}` |

### Targeted playback

| Command | Args / flags | Returns |
|---|---|---|
| `play-latest QUERY` | `--unwatched` `--key-only` | `{ok, playing: {...}}` or keys-only dict |
| `play-media RATING_KEY` | — | `{ok}` |
| `queue KEY1 [KEY2 ...]` | `--shuffle` `--repeat` | `{ok, playQueueID, selectedItemID}` |

`play-latest` semantics:

- Default: first unwatched episode in season order, falling back to most-recently-aired if all are watched, falling back to movie search if no show matches.
- `--unwatched`: same search but returns `{ok: false, "no unwatched episodes for: QUERY"}` when nothing is strictly unwatched. Does not fall through to movies.
- `--key-only`: resolve the ratingKey without starting playback; useful when gathering keys for a multi-episode queue.

### Queue control

| Command | Args / flags | Returns |
|---|---|---|
| `queue-show` | — | `{ok, playQueueID, selectedItemID, items: [...]}` |
| `queue-shuffle` | — | `{ok}` |
| `queue-unshuffle` | — | `{ok}` |
| `queue-clear` | — | `{ok}` |
| `queue-remove ITEM_ID` | — | `{ok}` |

All resolve the active queue ID by polling the client's `/player/timeline/poll?wait=0`; no local queue state.

### Status

| Command | Args / flags | Returns |
|---|---|---|
| `now-playing` | — | `{ok, state, title, show, season, episode, year, viewOffset, duration, ratingKey}` |
| `continue-watching` | — | `{ok, items: [...]}` |
| `history` | `--limit N` (default 10) | `{ok, history: [...]}` |

### Watch state

All three accept an optional `RATING_KEY`; omit to auto-target the currently playing item.

| Command | Args | Returns |
|---|---|---|
| `watched [RATING_KEY]` | — | `{ok}` |
| `unwatched [RATING_KEY]` | — | `{ok}` |
| `rate RATING [RATING_KEY]` | `RATING` is IntRange 0–10 | `{ok}` |

---

## Authentication

`plexctl auth login`:

1. Prompts for plex.tv username / password.
2. Prompts for PMS URL and default client (both with sensible defaults).
3. POSTs to `https://plex.tv/users/sign_in.json` with HTTP Basic auth; response carries `user.authToken`.
4. Issues a GET to the PMS URL with the token to verify reachability.
5. Writes `{server_url, token, default_client, client_id}` to `~/.config/plexctl/config.toml` with mode 0600.

`client_id` is generated once (`plexctl-<8 hex chars>`) and persisted so PMS sees a stable `X-Plex-Client-Identifier` across invocations.

Failure modes all emit the standard JSON error and exit 1 — connection failure, HTTP non-2xx, timeout, JSON-decode, and unexpected-response-shape are each caught with a specific message.

---

## Client resolution

`clients.list_clients()` merges two sources:

- Active clients — `GET /clients` on PMS. Only appears when the requester sends `X-Plex-Provides: controller`.
- Registered devices — `GET https://plex.tv/devices.json` using the account token.

They are joined on lowercased `name`:

- Entries whose `name` is missing or not a string are skipped (they cannot be addressed by name anyway).
- Duplicate lowercased names are flagged with `ambiguous: true` on every matching output entry; they can still be targeted by `machineIdentifier`.
- `clients.resolve()` errors with an explicit ambiguity message when a name-based target matches more than one active device, so the caller is forced to disambiguate.

Default target is `default_client` from config (set to `"Apple TV"` by default).

---

## Plex API quirks worth knowing

These are the non-obvious things you only learn by breaking them.

- **`X-Plex-Provides: controller`** must be on every PMS request or `/clients` returns an empty list. Every header helper in `plexctl.api` sets it.
- **Direct-to-client HTTP** is required for the Apple TV. Using PMS as a proxy (posting to PMS with `X-Plex-Target-Client-Identifier`) times out. `plexctl.playback` posts straight to the Apple TV's `baseurl` (`http://<host>:32500`) with the target identifier in the request headers.
- **`type=video`** must be on every player command or `seek`, `next`, `prev`, and `volume` silently time out.
- **`commandID` must be monotonically increasing across CLI invocations**. The Apple TV drops anything at or below the last ID it processed. `plexctl.playback._command_id` is seeded from `int(time.time())` at module load and incremented per call.
- **`playMedia` requires `address` and `port` params** so the Apple TV knows how to reach PMS. Without them it returns 400 "Parameter 'address' not found". These come from the `server_url` in the config.
- **Play queue creation needs the fully-qualified URI** `server://{machineIdentifier}/com.plexapp.plugins.library/library/metadata/{ratingKey}`. A bare `/library/metadata/{key}` URI yields a queue that PMS accepts (200 OK, queue ID returned) but cannot populate; `playMedia` then fails because `playQueueSelectedItemID` is null.
- **Adding items to an existing queue** is `PUT /playQueues/{id}?uri=<…>`, not POST, and the `uri` param takes the same `server://…` form.

---

## Error model

The CLI never lets a raw Python traceback reach stdout. Every failure path funnels through `json.dumps({"ok": False, "error": ...})` + `sys.exit(1)`.

### PMS and plex.tv requests (`plexctl.api`)

All five wrappers (`plex_tv_get`, `get`, `post`, `put`, `delete`) catch, in order:

1. `ConnectionError` — network unreachable, DNS failure, refused connection, SSL error. Message: `"connection failed: …"`.
2. `HTTPError` — non-2xx response. Message: `"HTTP <code>: <body first 200 chars>"`.
3. `Timeout` — read / connect timeout. Message: `"request timed out: …"`.
4. `JSONDecodeError` — response body not parseable as JSON. Message: `"invalid JSON response: …"`.
5. `RequestException` fallback — everything else (`TooManyRedirects`, `ChunkedEncodingError`, etc.). Message: `"request failed: …"`.

### Auth (`plexctl.auth.login`)

Same exception ladder, plus explicit guards on `r.json()["user"]["authToken"]` — `JSONDecodeError`, `KeyError`, and `TypeError` all produce specific JSON errors rather than tracebacks.

### Config (`plexctl.config.load`)

`tomllib.TOMLDecodeError` is caught and surfaced as `"invalid config at <path>: <message> — run plexctl auth login"`. A hand-edited or truncated config file cannot brick the CLI.

### Companion-side (`plexctl.playback._player_get`)

Raises a module-level `CompanionTransportError` on any `RequestException`. Queue operations catch it via the `_resolve_queue_id` helper and return `"transport error contacting <client>: …"` — distinct from the `"no active queue on <client>"` message that an actually-empty queue produces.

### Seek (`plexctl.playback._do_seek`)

Relative-seek tolerates missing or malformed `viewOffset`: `None` and non-numeric values return `None` from `_get_view_offset()` and the caller emits `"could not determine current playback position"`.

When seeking on a paused player the Companion API silently ignores `seekTo`, so `plexctl` auto-resumes → seeks → re-pauses. Each step is checked:

- Pre-seek `play` fails → seek aborted with `"could not resume before seek: …"`.
- `seekTo` fails → returned as-is.
- Post-seek `pause` fails → result downgraded to `{"ok": false, "error": "seeked but failed to restore pause state: …"}`.

Pass `--no-unpause` to disable the dance and manage state manually.

---

## Queue semantics

`plexctl queue K1 K2 ... KN [--shuffle] [--repeat]`:

1. `POST /playQueues` with K1's URI creates the queue; response carries `playQueueID` and `playQueueSelectedItemID`.
2. Remaining keys are added with `PUT /playQueues/{id}?uri=…`.
3. If any mid-loop `add()` fails, the partially-built queue is deleted via best-effort `DELETE /playQueues/{id}` (wrapped in `try / except SystemExit` because `api.delete` exits on failure). The returned error dict carries `partialQueueID` and `rollbackAttempted: true` so callers know what server-side state existed.
4. On success, `playback.play_queue()` tells the Apple TV to start playing from `playQueueSelectedItemID`.

`queue-show`, `queue-shuffle`, `queue-unshuffle`, `queue-clear`, `queue-remove` all resolve the active queue ID by polling the client's `/player/timeline/poll?wait=0` and looking for a `Timeline` entry with `type=video` and a non-null `playQueueID`. There is no local queue state — always fresh from the client.

---

## Configuration file

`~/.config/plexctl/config.toml`:

```toml
server_url = "http://your-pms.local:32400"
token = "…"
default_client = "Apple TV"
client_id = "plexctl-xxxxxxxx"
```

Mode is set to 0600 on every write. Values are escaped before writing (backslashes and double-quotes). Malformed TOML is caught at load and surfaced via the standard JSON error rather than crashing.

---

## Testing

```
pip install pytest
pytest -q
```

111 tests as of this writing. Coverage:

- Intent → command mapping (skill grammar fidelity)
- JSON shape contracts for each command
- Error-path behavior for each module
- Queue lifecycle including rollback

Tests patch `plexctl.api` with `unittest.mock.patch`, so they do not require a real PMS or network.

---

## The `/plex` skill

`.claude/skills/plex/SKILL.md` is a Claude Code skill that binds voice/text intent to the CLI. Key behaviors:

- **Row-number protocol** — any list containing `ratingKey` or `playQueueItemID` gets a leading `#` column; IDs are held in conversation context so follow-ups like *"play #2"* resolve without the user seeing the raw ID.
- **Debug mode** — leading `debug` token or `--debug` flag restores the raw ID columns and echoes the exact shell command run.
- **Pre-action state check** — before any playback-changing command the skill runs `now-playing` + `continue-watching` first, so it can avoid accidentally interrupting something and can resolve vague intents like *"resume"* against the actual queue.
- **Ambiguity rules** — multiple show matches are surfaced as a confirmation table rather than silently guessed; ambiguous client names trigger the CLI's ambiguity error (by design).
- **Default client** is Apple TV. Override in natural language with *"on the [name]"*.

---

## Extending

Adding a new command:

1. Add the module-level function (in `plexctl/library.py` / `plexctl/playback.py` / `plexctl/queue.py` / `plexctl/sessions.py`) that returns a `{"ok": ..., ...}` dict.
2. Register a Click command in `plexctl/cli.py` that wraps it and pipes through `_out()`.
3. Add a test in `tests/test_intent_examples.py` exercising the JSON shape and any failure modes.
4. If voice-exposed, update the grammar table in `.claude/skills/plex/SKILL.md`.

Do not bypass `_out()` from `cli.py` — the JSON-only stdout contract is what the `/plex` skill and any future scripting consumer relies on.
