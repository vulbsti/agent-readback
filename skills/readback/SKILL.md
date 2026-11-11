---
name: readback
description: Explain what another coding-agent session (Claude Code or Codex) did, mechanistically and with citations, without touching that session's context or repo. Use when the user asks "what did the agent do", "explain the changes in the other window", "why did it change X", "walk me through that session", or wants a diagram of how the new code works.
---

# readback: explain another agent's session

`readback` is a read-only CLI. It reads a Claude Code or Codex transcript plus the git diff of the
worktree it changed, and sends a compact, id-tagged evidence pack to a separate model call that cannot write: no tools with
the `claude` and API backends, every tool feature disabled with `codex`. Nothing is written to the observed session, its transcript or its repo; the follow-up
thread lives in readback's own state directory.

Use it from a second window (the "explainer" window) while the executor agent works in the first.

## Pick the session
- Default: the most recent session run in the current directory, excluding this session.
- `readback sessions` lists recent sessions here (`--all` for every directory). Pass one with
  `-s <id-prefix or path>`.
- If the agent's worktree is elsewhere, pass `--repo <dir>`.

## Modes
| ask for | run |
|---|---|
| what changed, why, tests, risks | `readback overview` |
| step by step | `readback walkthrough` |
| how the new code works (Mermaid) | `readback mechanism` |
| a follow-up question (multi-turn) | `readback ask "why TypeError, not ValueError?"` |
| clickable citations in a browser | `readback web --no-open` (then share the URL) |
| live: follow the running agent | `readback watch --explain-every 10 --duration 120` (without `--duration` it runs until stopped) |
| ids behind citations | `readback events` |

## Rules
- Relay readback's output verbatim. It is already terse and cited; don't pad it or re-explain.
- Answer follow-ups with `readback ask`, which keeps the thread, rather than reading the transcript yourself.
- Never edit, commit or run commands in the observed repo.
- Backend: auto-detects `READBACK_CMD`, then `claude`, then `codex`, then `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`.
  Override with `--backend` or `READBACK_BACKEND`.
