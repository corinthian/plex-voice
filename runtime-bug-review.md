# Runtime Bug Review

Generated on April 24, 2026.

## Scope

This review focuses on crashing bugs, silent failures, and execution-time error handling issues in the current `plexctl` codebase.

## Findings

### 1. Unhandled HTTP and JSON parse failures can crash the CLI

Severity: High

Files:
- `plexctl/api.py`
- `plexctl/auth.py`

Details:
- The request wrappers in `plexctl/api.py` catch `ConnectionError` and `HTTPError`, but do not catch other common runtime failures such as `Timeout`, broader `RequestException`, or JSON decoding failures from `r.json()`.
- The login flow in `plexctl/auth.py` has the same gap. It also assumes the auth response always contains `["user"]["authToken"]`.

Impact:
- Slow or unstable Plex endpoints can produce uncaught exceptions and raw stack traces instead of the CLI’s expected JSON error output.
- Non-JSON responses or changed response shapes can also crash the process.

Relevant lines:
- `plexctl/api.py:31-40`
- `plexctl/api.py:49-58`
- `plexctl/api.py:67-76`
- `plexctl/api.py:85-94`
- `plexctl/api.py:103-112`
- `plexctl/auth.py:33-55`

**Verification (2026-04-24): CONFIRMED.**
- Source re-read matches the finding: each wrapper in `api.py` catches only `ConnectionError` + `HTTPError`; `auth.py:33-41` identical pattern.
- Exception hierarchy probed empirically against installed `requests` 2.33.1:
  - `ReadTimeout` is NOT a subclass of `ConnectionError` or `HTTPError` → **escapes** current handlers (becomes raw traceback).
  - `Timeout` base class → **escapes**.
  - `requests.exceptions.JSONDecodeError` → **escapes** (only `<: RequestException`). Any non-JSON 2xx body (HTML error page, empty, garbled) crashes at `r.json()`.
  - `TooManyRedirects` → **escapes**.
  - `ConnectTimeout` and `SSLError` DO subclass `ConnectionError` and are caught (minor mitigation).
- `auth.py:43` additionally does `r.json()["user"]["authToken"]` with no guard — `KeyError`/`TypeError` on shape change, uncaught.
- Fix must broaden the `except` to `requests.exceptions.RequestException` (or add explicit `Timeout`/`JSONDecodeError` arms) and guard the auth-response shape.

### 2. Relative seek can crash if `viewOffset` is null or malformed

Severity: High

File:
- `plexctl/playback.py`

Details:
- `_get_view_offset()` converts `viewOffset` with `int(s.get("viewOffset", 0))`.
- If Plex returns `None`, an empty string, or any non-numeric value, this raises `TypeError` or `ValueError`.

Impact:
- Commands like `plexctl seek +30s` and `plexctl seek -10s` can crash instead of returning the intended JSON error.

Relevant lines:
- `plexctl/playback.py:90-102`
- `plexctl/playback.py:151-158`

**Verification (2026-04-24): CONFIRMED.**
- Source check: `plexctl/playback.py:101` is `return int(s.get("viewOffset", 0))` — no type guard.
- Exercised the exact call pattern in isolation:
  - `viewOffset = None` → `TypeError: int() argument must be ... not 'NoneType'`.
  - `viewOffset = ""` → `ValueError: invalid literal for int() with base 10: ''`.
  - `viewOffset = "abc"` → `ValueError`.
  - `viewOffset` missing (hits default `0`) → ok.
  - `viewOffset = "12345"` → ok.
- Plex has been observed to emit `viewOffset` absent or null during transitions (buffering / pre-first-frame), so this is reachable in production.
- Fix: coerce via `try: int(s.get("viewOffset") or 0) except (TypeError, ValueError): return None` and let caller emit the existing JSON error.

### 3. `play-latest --unwatched` is accepted but ignored

Severity: Medium

File:
- `plexctl/cli.py`

Details:
- The CLI exposes `--unwatched` and documents different behavior for it.
- The command implementation never uses the `unwatched` argument and always calls the same library function.

Impact:
- Callers receive a successful response even though the requested mode was not applied.
- This is a silent behavioral failure rather than a crash.

Relevant lines:
- `plexctl/cli.py:167-198`

**Verification (2026-04-24): CONFIRMED.**
- `cli.py:172` accepts `unwatched` param but `cli.py:178` calls `library.latest_unwatched_episode(query)` unconditionally — the flag is never read.
- `library.latest_unwatched_episode` already returns first unwatched episode in season order, falling back to most-recently-aired when all watched. So `--unwatched` and no-flag paths produce identical output.
- Docstring promises "force the next unwatched episode even if in-progress exists" — untrue; no in-progress/on-deck logic exists anywhere in library.py.
- Fix options: (a) thread `unwatched` into `latest_unwatched_episode` as a `strict` param that returns None (→ caller error) when nothing is truly unwatched, giving the flag real semantics; (b) remove the flag and update docstring + CLAUDE.md voice mapping. Going with (a) to preserve voice-input contract.

### 4. Client discovery can crash or target the wrong device

Severity: Medium

File:
- `plexctl/clients.py`

Details:
- Active and registered devices are keyed by lowercase `name`.
- Missing or null names will raise errors during `.lower()`.
- Duplicate device names overwrite each other in the lookup map.

Impact:
- `clients` and client resolution can fail unexpectedly on incomplete Plex data.
- If two devices share the same display name, the wrong client can be selected without warning.

Relevant lines:
- `plexctl/clients.py:23-40`
- `plexctl/clients.py:53-73`

**Verification (2026-04-24): CONFIRMED.**
- `clients.py:25` `{c["name"].lower(): c for c in active}` — if `name` is missing → `KeyError`; if `name` is `None` → `AttributeError` on `.lower()`.
- `clients.py:30` `active_by_name.get(d["name"].lower())` — same two crash modes on the `/devices.json` side.
- Dict construction is last-write-wins, so two active clients sharing a display name cause the earlier one to be silently replaced. `resolve()` at `clients.py:59-70` scans the merged `list_clients()` output and returns the *first* entry whose name matches — which after the overwrite may not be the device the user intended.
- Fix: filter out entries with missing/non-string names in both `_active_clients` consumption and the registered-devices loop; detect duplicate lowercased names and surface an ambiguity error from `resolve()` rather than silently picking one.

### 5. Queue creation can leave partial server-side state after failure

Severity: Medium

File:
- `plexctl/queue.py`

Details:
- Queue creation posts the first item, then appends the remaining items one at a time.
- If one of the later `add()` calls fails, the function returns an error but does not roll back the queue already created on the server.

Impact:
- The command can fail while still leaving a partially built queue behind.
- This creates state drift between the CLI’s reported outcome and Plex’s actual queue state.

Relevant lines:
- `plexctl/queue.py:5-35`
- `plexctl/queue.py:104-114`

**Verification (2026-04-24): CONFIRMED.**
- `queue.py:13-19` posts the first item via `/playQueues` which returns `playQueueID`.
- `queue.py:28-31` then iterates remaining ratingKeys calling `add()`; the first failure returns the error dict immediately with no cleanup step.
- PMS PlayQueues are server-side objects keyed by `playQueueID` and are retrievable until eviction (~hours); a partial queue can remain visible to clients until then.
- Fix: on mid-loop failure, attempt best-effort rollback via `api.delete(f"/playQueues/{queue_id}")` (wrap in `try/except SystemExit` since `api.delete` exits the process on failure), and include the `playQueueID` in the returned error so callers can see what state was left behind.

## Validation Notes

- `pytest` could not be run in the current environment because `python3 -m pytest -q` failed with `No module named pytest`.
- This report is based on static source review and failure-path inspection.

## Second-Pass Addendum

### 6. Malformed `config.toml` can brick the CLI with an uncaught traceback

Severity: High

File:
- `plexctl/config.py`

Details:
- `load()` calls `tomllib.load()` directly and does not catch parse failures.
- Nearly every command reaches `cfg.load()` before doing any work.

Impact:
- A truncated or manually edited `~/.config/plexctl/config.toml` can cause an uncaught `TOMLDecodeError` at startup.
- This bypasses the CLI's JSON error contract and turns a recoverable configuration problem into a hard crash.

Relevant lines:
- `plexctl/config.py:16-20`
- `plexctl/config.py:33-39`

**Verification (2026-04-24): CONFIRMED.**
- Source check: `plexctl/config.py:19-20` calls `tomllib.load(f)` with no try/except. `require()` re-enters `load()` at line 34, so every command that needs a token inherits this crash path.
- Reproduced: pointed `cfg.CONFIG_PATH` at a hand-rolled malformed toml file (`server_url = "http://x\nbroken = = \n`) and called `cfg.load()` → uncaught `tomllib.TOMLDecodeError: Illegal character '\n' (at line 1, column 23)`.
- Real-world trigger is plausible: partial writes (power loss during `save()`), manual edits, or merge-conflict markers in `~/.config/plexctl/config.toml`.
- Fix: wrap `tomllib.load` in `try/except tomllib.TOMLDecodeError` and emit the standard JSON error (`{"ok": False, "error": "invalid config at <path>: <msg> — run plexctl auth login"}`), then `sys.exit(1)`.

### 7. Seek can report success while leaving playback in the wrong state

Severity: Medium

File:
- `plexctl/playback.py`

Details:
- When seeking while paused, `_do_seek()` sends a pre-seek `play`, then performs `seekTo`, then sends a post-seek `pause`.
- The return value only reflects the `seekTo` call. Failures from the pre-seek `play` and post-seek `pause` calls are ignored.

Impact:
- A paused seek can return `{"ok": true}` even if the item failed to re-pause and is now playing.
- This is a silent state drift bug: the user asked for a seek, but the final player state may no longer match the original paused state.

Relevant lines:
- `plexctl/playback.py:141-149`

**Verification (2026-04-24): CONFIRMED.**
- Source check: `plexctl/playback.py:141-149` — `_do_seek` only returns the result of `seekTo`. The pre-seek `play` at line 144 and the post-seek `pause` at line 148 have their return values discarded.
- Scenarios where the final state drifts from user intent:
  - Pre-seek `play` fails → `time.sleep(1.0)` still runs, then `seekTo` is issued against a still-paused player; Plex sometimes applies the seek but state is unpredictable, and even if `seekTo` returns ok, we then issue `pause` to an already-paused player which is a no-op. Worst case: pre-seek play did actually land after the sleep expired, seek applied, pause failed — video now playing when user wanted paused.
  - Post-seek `pause` fails → result reports `{"ok": true}` while video is playing.
- Fix: check the result of the pre-seek `play` and bail with a clear error if it fails; check the post-seek `pause` and downgrade the return to `{"ok": false, "error": "seeked but failed to restore pause state"}` when it fails.

### 8. Queue commands can misreport transport failures as “no active queue”

Severity: Medium

Files:
- `plexctl/playback.py`
- `plexctl/queue.py`

Details:
- `_player_get()` swallows any `RequestException` and returns `None`.
- `current_queue_id()` treats `None` the same as “no queue is present”.
- All queue operations then turn that into a user-facing “no active queue” error.

Impact:
- If the client is unreachable or its Companion endpoint errors, commands like `queue-show`, `queue-clear`, and `queue-shuffle` can report the wrong problem.
- This is a silent failure classification bug: transport errors are flattened into an ordinary empty-state response.

Relevant lines:
- `plexctl/playback.py:49-73`
- `plexctl/queue.py:38-49`
- `plexctl/queue.py:52-101`

**Verification (2026-04-24): CONFIRMED.**
- `playback.py:72-73` collapses every `RequestException` (including `Timeout`, `ConnectionError`, and — per finding #9 — `JSONDecodeError`) to `None`.
- `queue.py:41-42` maps `None` onto "no queue" without any further discrimination, and `queue.py:52-101` (`show`, `shuffle`, `unshuffle`, `clear`, `remove_item`) all surface that as `"no active queue on <client>"`.
- Usability impact is real: on an Apple TV that is reachable on the network but whose Companion endpoint is flaky, the user sees the wrong diagnostic and thinks their queue is missing.
- `_player_get` is only called from `queue.current_queue_id` (grep confirms), so the blast radius of a signature change is contained.
- Fix: raise a distinct `TransportError` (or return a sentinel like `{"__transport_error__": ...}`) from `_player_get` on `RequestException`; let `current_queue_id` propagate it, and have each queue operation catch it and return `{"ok": false, "error": f"transport error: <detail>"}` instead of the empty-state message.

### 9. Companion JSON decode failures are still uncaught in `_player_get()`

Severity: Medium

File:
- `plexctl/playback.py`

Details:
- `_player_get()` only catches `requests.exceptions.RequestException`.
- If the client returns non-JSON content with a `200` response, `r.json()` can raise a decode exception that is not caught here.

Impact:
- Queue-related commands that depend on `_player_get()` can still terminate with a traceback instead of returning JSON error output.
- This overlaps with the broader API-layer issue, but it exists on the client Companion path separately and affects queue inspection/control directly.

Relevant lines:
- `plexctl/playback.py:68-73`
- `plexctl/queue.py:38-49`

**Verification (2026-04-24): PARTIALLY REFUTED.**
- In `requests` 2.33.1 (the pinned floor in `pyproject.toml` is `>=2.31`, which shipped the same taxonomy), `requests.exceptions.JSONDecodeError` IS a subclass of `RequestException` — empirically verified with `issubclass(...)`. So the existing `except RequestException` on `playback.py:72` DOES catch it, and `_player_get` will not crash on non-JSON 2xx bodies.
- The finding's crash claim therefore does not hold against the pinned dependency. However, the behavioral half of the finding is valid and overlaps with #8: a non-JSON 200 body is collapsed to `None`, which queue ops then report as "no active queue" — same misclassification.
- No separate fix is required beyond the #8 transport-error plumbing; as long as `_player_get` surfaces the `JSONDecodeError` (via the new sentinel/exception) rather than squashing to `None`, callers will get the right diagnostic.

## Updated Validation

- Local tests now run under the project `.venv`.
- `.venv/bin/pytest -q` passes: `111 passed in 0.05s`
