# CLI usage

```
readback [-h] [--version] {sessions,events,pack,overview,walkthrough,mechanism,ask,watch,web} ...
```

Run it from the directory the agent worked in (or pass `--repo`). It reads the newest Claude Code
or Codex session for that directory and the git diff of that worktree. It never writes to either.

Errors go to stderr as `readback: <message>` with exit code 2.

## Choosing a session and a diff

These flags are shared by `events`, `pack`, `overview`, `walkthrough`, `mechanism`, `ask`, `watch`
and `web`.

| flag | meaning |
|---|---|
| `-s, --session SESSION` | transcript path, session id or unique id prefix/suffix, or `latest`. Default: the latest session run in `--repo` or the current directory, else the latest anywhere. Your own Claude Code session is excluded. |
| `--repo REPO` | worktree the agent changed. Default: the session's recorded cwd. Also used to pick `latest`. |
| `--base BASE` | git ref to diff against. Default `auto`: the parent of the first commit (by committer date) made between the session's start and 10 minutes after its last record, else `HEAD`. The diff is against the current worktree; for an old session, give an explicit ref or use `--diff-file`. |
| `--diff-file DIFF_FILE` | use this unified diff instead of reading git. |

With no usable repo, readback falls back to the edits recorded in the transcript. `readback events`
prints the diff source in its header (`git:<sha>`, `file`, `transcript`, or `none`).

Session files are found under `~/.claude/projects/*/*.jsonl` and
`~/.codex/sessions/**/rollout-*.jsonl`; override with `READBACK_CLAUDE_DIR` and
`READBACK_CODEX_DIR`.

## Model flags

Shared by `overview`, `walkthrough`, `mechanism`, `ask`, `watch` and `web`.

| flag | meaning |
|---|---|
| `--backend BACKEND` | `claude`, `codex`, `anthropic`, `openai`, `command` or `fake`. Default: `READBACK_BACKEND`, else auto-detect (see [backends.md](backends.md)). |
| `--model MODEL` | model passed to the backend. Default: `READBACK_MODEL`, else the backend's default. |
| `--budget BUDGET` | max tokens of evidence sent to the model (estimated at 4 chars/token). Default 40000. |
| `--lines LINES` | target answer length in lines. Defaults: overview 22, walkthrough 20, mechanism 10, ask 12. |
| `--json` | print a JSON object instead of text. |
| `--no-repair` | skip the second pass that fixes missing or unknown citations. |

After a text answer, a status line goes to stderr:

```
[claude · 42 events · cites 17 · coverage 100% · 9120→310 tok · 8.4s]
```

`--json` prints `mode`, `text`, `cited`, `unknown_removed`, `coverage`, `input_tokens`,
`output_tokens`, `backend`, `events_seen`, `seconds`.

## Commands

### `sessions`

List recent sessions, newest first.

```
readback sessions [--all] [--repo REPO] [-n N]
```

- `--all`: every directory, not just the current one (or `--repo`).
- `-n N`: how many to show (default 10).

If none match the current directory, it says so on stderr and lists all. Each entry shows modified
time, agent, session id, cwd, and the first user prompt.

### `events`

Index of transcript events and diff hunks with their ids. No model call.

```
readback events [-s SESSION] [--repo REPO] [--base BASE] [--diff-file DIFF_FILE]
```

Use it to look up a citation: `E7 Bash ! $ python -m pytest -q` (`!` marks a failed call), or
`H2 calc.py @@ -1,2 +1,4 @@ (+2 -0)`. `--budget` is accepted but unused here.

### `pack`

Print the evidence pack exactly as the model would receive it. No model call.

```
readback pack [-s SESSION] [--repo REPO] [--base BASE] [--diff-file DIFF_FILE] [--budget BUDGET]
```

Use it to check what will leave your machine and how the budget clips it.

### `overview`

Four sections: **Changed** (behavioural changes by file and function), **Why** (the user's goal
and the agent's stated reasons), **Tests** (each new or changed test: inputs and assertions; commands
run and their results), **Risks** (untested paths, assumptions, side effects, failures seen).

```
readback overview [session flags] [model flags]
```

### `walkthrough`

The agent's steps in order, grouped into phases (explore, edit, test, fix, report), including
failed commands and the agent's reaction.

```
readback walkthrough [session flags] [model flags]
```

### `mechanism`

A Mermaid `flowchart TD` of data and control flow through the changed code, then bullets that
explain each node or edge and how the tests exercise it.

```
readback mechanism [session flags] [model flags]
```

### `ask`

Multi-turn follow-up questions. The thread is kept per transcript in readback's state directory
and the last 6 turns are sent with each new question.

```
readback ask [--reset] [session flags] [model flags] [question ...]
```

- `readback ask "why TypeError, not ValueError?"`: ask; the question may also be unquoted words.
- `readback ask`: print the thread so far.
- `--reset`: clear the thread first (combine with a question to start a new thread with it).

### `watch`

Tail a running session and print each new event as it is written.

```
readback watch [session flags] [model flags] [--explain-every N] [--interval INTERVAL] [--duration SECONDS]
```

- `--explain-every N`: once at least N new events have arrived since the last one (checked once per poll), print a short delta explanation of what the agent
  just did (default 0 = off; needs a backend only when set).
- `--interval INTERVAL`: poll interval in seconds (default 1.0).
- The delta explanation diffs `--repo` (or the session cwd) with the `auto` base. `--base`,
  `--diff-file`, `--lines`, `--json` and `--no-repair` are accepted but not used by `watch`.
- `--duration SECONDS`: stop after that many seconds (default: run until Ctrl-C).

### `web`

Local web view: explanation on one side, transcript events and diff hunks on the other. Citations
are links that scroll to and highlight the evidence. The page refreshes from the transcript, so it
works on a running session.

```
readback web [session flags] [model flags] [--port PORT] [--no-open]
```

- `--port PORT`: default 8765. Binds to 127.0.0.1 only.
- `--no-open`: print the URL instead of opening a browser.
- `--lines`, `--json` and `--no-repair` are accepted but not used.

## Environment variables

| variable | used for |
|---|---|
| `READBACK_BACKEND` | default backend |
| `READBACK_MODEL` | default model |
| `READBACK_CMD` | command for the `command` backend |
| `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL` | `anthropic` backend |
| `OPENAI_API_KEY`, `OPENAI_BASE_URL` | `openai` backend |
| `READBACK_STATE_DIR` | where ask threads are stored (default `$XDG_STATE_HOME/agent-readback` or `~/.local/state/agent-readback`) |
| `READBACK_CLAUDE_DIR` | Claude Code transcripts root (default `~/.claude/projects`) |
| `READBACK_CODEX_DIR` | Codex transcripts root (default `~/.codex/sessions`) |

## Examples

```bash
readback sessions                          # what is there for this directory
readback overview                          # latest session here
readback walkthrough -s 3f2a               # a specific session by id prefix
readback mechanism --repo ../worktree-b    # agent worked in another worktree
readback ask "which test covers the negative case?"
readback overview --diff-file change.patch --backend anthropic
readback watch --explain-every 10          # follow a running agent
readback web --no-open                     # browser view with clickable citations
readback pack --budget 8000 | less         # inspect what would be sent
```
