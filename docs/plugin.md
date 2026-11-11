# Claude Code plugin

The repository is also a Claude Code plugin. It adds one slash command and one skill that call the
`readback` CLI.

## Install

**Recommended: load it only in the explainer window.** This keeps the executor's context completely untouched:

```bash
git clone https://github.com/vulbsti/agent-readback ~/agent-readback   # once
claude --plugin-dir ~/agent-readback                                   # start the explainer window like this
```

**Convenient alternative: install from the marketplace.** In user scope this loads in *every* Claude Code session:

```
/plugin marketplace add vulbsti/agent-readback
/plugin install agent-readback@agent-readback
```

- **What it adds:** the slash command's and the skill's descriptions, about 180 tokens, go into each session's context, including the executor's. `claude --plugin-dir . plugin details agent-readback` estimates ~177 tokens always-on (two components: ~120 and ~60).
- **What it doesn't add:** readback still sends nothing to the executor. It reads the executor's transcript file but never writes it or adds to its context.
- **Project and local scope don't help:** they attach to the directory, and the two windows usually share one directory.

The command runs `readback` if it is on `PATH`, else
`uvx --from git+https://github.com/vulbsti/agent-readback readback`. Installing the CLI avoids the
`uvx` start-up cost:

```bash
uv tool install git+https://github.com/vulbsti/agent-readback
# or
pipx install git+https://github.com/vulbsti/agent-readback
```

## The two-window workflow

1. **Executor window**: the agent that does the work (Claude Code or Codex), in your repo.
2. **Explainer window**: a second Claude Code session started in the same directory, with the
   plugin.

In the explainer window, ask about the executor's session. readback reads the executor's transcript
and worktree, read-only. Nothing is sent to the executor, and its files and `.git` are not modified. Its context is untouched
when the plugin is loaded only in the explainer window (`--plugin-dir`). A user-scope install also
puts the plugin's ~180-token command and skill descriptions into the executor's context (see Install). When readback picks the "latest" session it
skips the explainer window's own session (`CLAUDE_CODE_SESSION_ID`), so it finds the executor.

If the executor works in another directory or worktree, pass `--repo <dir>`; to pick a specific
session, run `/agent-readback:readback sessions` and pass `-s <id-prefix>`.

## `/agent-readback:readback`

```
/agent-readback:readback [overview|walkthrough|mechanism|ask <question>|web|sessions|events] [flags]
```

| input | runs |
|---|---|
| (empty) | `readback overview` |
| `walkthrough` | `readback walkthrough` |
| `mechanism` | `readback mechanism` |
| `ask why TypeError?` | `readback ask "why TypeError?"` |
| `why TypeError?` (no mode word) | treated as a question: `readback ask "why TypeError?"` |
| `web` | `readback web --no-open` in the background; prints the URL |
| `sessions` | `readback sessions` |
| `events` | `readback events` |

Any other CLI flag (`-s`, `--repo`, `--backend`, `--lines`, ...) passes through. The command prints
readback's output verbatim; citations such as `[E12]` and `[H3]` refer to `readback events`. If no
session is found it shows `readback sessions --all`.

The command is allowed to run only `readback` and `uvx` through Bash.

## Skill

The `readback` skill lets Claude reach for the CLI on its own when you ask things like "what did
the agent in the other window do", "why did it change X", or "draw how the new code works". It
follows the same rules: relay output verbatim, answer follow-ups with `readback ask`, never edit or
run commands in the observed repo.

## Backend

Inside Claude Code the `claude` CLI is normally on `PATH`, so it is auto-detected. The explainer
call runs `claude -p` with all tools disabled, no session persistence, no settings and no MCP, in a
temporary directory. Override with `READBACK_BACKEND` or `--backend`; see
[backends.md](backends.md).
