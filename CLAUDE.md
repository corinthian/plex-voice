# plexctl — Claude Code Project Instructions

Session-level notes for Claude Code running inside this repo. The canonical voice / text intent grammar lives at [`.claude/skills/plex/SKILL.md`](.claude/skills/plex/SKILL.md) — treat that as the source of truth for command mappings, debug mode, row-number handling, and output formatting.

This file covers what is specific to this session: how voice input reaches Claude, recent behavior changes, and where to look.

---

## Session Setup

This macOS Claude Code session should be named **plex** (use `/rename plex` if not already set). The iPad connects via `/remote-control`. Voice input arrives as relayed messages from the iPad Claude session.

Your job when a voice transcript comes in: parse it into a `plexctl` shell command, run it (or confirm if the action is destructive), and render the JSON result per the formatting rules in `.claude/skills/plex/SKILL.md`.

You can also invoke the same behavior directly with `/plex <phrase>` — both paths hit the same grammar.

---

## Supported Clients

| Client | Controllable |
|---|---|
| Apple TV | Yes — default target |
| iPad | No — no Companion HTTP endpoint (port=null) |
| Plex for Mac | No — not a Companion client |
| Plex Web (browser) | No — WebSocket only |

If the user asks to control the Mac or browser player, tell them it is not supported and suggest switching to Apple TV. Default client is Apple TV — omit `--client` when targeting it.

---

## Recent Behavior Changes

These are the post-review changes that affect how commands resolve. Update any cached grammar in your head accordingly:

- **`plexctl play-latest "<show>" --unwatched`** is now strict. With the flag, if nothing is strictly unwatched the command returns `{"ok": false, "error": "no unwatched episodes for: <query>"}` instead of falling back to the most-recently-aired episode or a movie search. Without the flag, behavior is unchanged (unwatched-preferred, falls back to latest aired, then movie).
- **Ambiguous client names error out.** If two active clients share a lowercased name, `plexctl` returns `ambiguous client name '<name>' — multiple active devices share this name; specify by machineIdentifier`. Surface that to the user and ask them to pick by machineIdentifier (visible in `plexctl clients --debug`).
- **Queue ops now distinguish transport failure from empty queue.** `queue-show`, `queue-shuffle`, `queue-unshuffle`, `queue-clear`, and `queue-remove` return `transport error contacting <client>: …` when the Companion endpoint is unreachable, separately from `no active queue on <client>`. When you see the transport error, prompt the user to re-open the Plex app rather than saying the queue is empty.
- **`plexctl queue K1 K2 ...` rolls back on partial failure.** If adding a later key fails, the partially-created queue is deleted server-side (best effort). The error dict carries `partialQueueID` and `rollbackAttempted: true` — surface the queue ID only in debug mode.
- **Seek on a paused player** auto-resumes, seeks, and re-pauses. Failures on either transition produce explicit errors (`could not resume before seek: …` / `seeked but failed to restore pause state: …`) rather than silent state drift. Show the error verbatim; no paraphrasing.

---

## Project Layout Quick Reference

- `plexctl/` — the CLI implementation
- `.claude/skills/plex/SKILL.md` — the `/plex` skill (full grammar, formatting rules)
- `README.md` — user-facing intro and install
- `DOCS.md` — technical reference (architecture, modules, error model, extensions)
- `STATUS.md` — rolling bug / future-work tracker
- `runtime-bug-review.md` — audit trail for the last runtime-safety review
- `tests/test_intent_examples.py` — pytest suite (111 tests)

---

## Execution

Once intent is clear and unambiguous, run the command directly without asking. Only pause for confirmation when the action is destructive (`stop`, `queue-clear`) or the target is genuinely unclear.

Full intent grammar, output formatting, row-number protocol, debug mode, and ambiguity rules: [`.claude/skills/plex/SKILL.md`](.claude/skills/plex/SKILL.md).
