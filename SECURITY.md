# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | yes       |
| < 0.1   | no        |

## Reporting a vulnerability

Use GitHub private vulnerability reporting:
<https://github.com/vulbsti/agent-readback/security/advisories/new>.

If that page is not available, open a feature-request issue titled "security contact request". Include no details,
and a maintainer will set up a private channel.

Please include the version (`readback --version`), OS, backend, and a minimal reproduction. Do not
attach real transcripts; build a synthetic one (see `tests/conftest.py` for the shape). Do not open a
public issue for a vulnerability.

The maintainers aim to acknowledge reports within 7 days. Fixes ship as a 0.1.x patch release with a
CHANGELOG entry and a published advisory.

## Threat model

readback reads another agent's session (a Claude Code or Codex CLI transcript plus the git
worktree it changed) and asks a separate model to explain it. Two properties matter.

### 1. Read-only guarantee

Nothing is written to the observed transcript or the observed worktree (including `.git`), and readback
writes no agent configuration. Three exceptions: the `codex` backend's linked `auth.json` may be refreshed
by Codex itself, as any `codex` run would (see below); a custom clean filter (other than git-lfs, which readback disables) configured by the repo runs when git hashes a changed file it applies to, and readback cannot stop that filter from writing; and in a repo with git's split index (`core.splitIndex=true`), git itself refreshes the mtime of `.git/sharedindex.*` whenever it reads the index, even through readback's throwaway copy; the bytes do not change. Every git call also passes
`-c core.fsmonitor=false -c core.hooksPath=/dev/null` and unsets git-lfs's clean filter, and `git diff` runs
with `--no-ext-diff --no-textconv`, so a repo's config cannot make git run a hook (such as
`post-index-change`, which fires when git writes readback's throwaway index), start an fsmonitor or
external diff command, store
LFS objects, or cache textconv output in `refs/notes` (probe in `docs/verification/readonly-real-backend.md`). This is enforced in code, not by convention:

- **Transcripts** are opened only with `open(path, "rb")` (`transcripts/__init__.py`). Live tailing
  seeks to a byte offset, reads complete lines, and never locks, truncates or touches the file.
- **Git** is always invoked as `git --no-optional-locks -C <repo> ...` with `GIT_OPTIONAL_LOCKS=0`
  and stdin closed (`gitdiff._git`). `git diff` and `git ls-files` also run against a throwaway copy
  of the index (`GIT_INDEX_FILE`), because `git diff <base>` rewrites stat-dirty index entries even
  with `--no-optional-locks`; the real `.git/index` is never written. Untracked files are rendered as new-file hunks by reading them directly, not via
  `git add -N`. Untracked files above 200 KB are summarised, binary files are skipped.
- **The explainer model cannot write, and never runs in the observed repo.** Every CLI backend runs
  in a fresh temporary directory (`backends._run`):
  - `claude`: `claude -p --tools "" --no-session-persistence --setting-sources "" --strict-mcp-config`.
  - `codex`: `codex exec --sandbox read-only --ephemeral --skip-git-repo-check --ignore-user-config
    --ignore-rules -c web_search="disabled"`, with every tool-providing feature disabled
    (`CODEX_DISABLED_FEATURES` in `backends.py`: code-mode host, shell, unified exec, multi-agent,
    image generation, apps, plugins, hooks, memories, browser and computer use, and more). It runs with a throwaway
    `CODEX_HOME` holding only a link to your `auth.json`, so your global Codex instructions, memories
    and config are not loaded. Because it is a symlink, a token refresh during the call writes through
    to your real `auth.json`, exactly as a normal `codex` run would. **Its tool block rests on Codex feature flags.**
    Before audit round 16 this backend still had a working shell and web tool, so planted transcript text
    could have made it read local files and send them to a URL. With the current flags, a probe (Codex
    0.166) found every shell, web, patch and agent-spawn call fails, while a control with the old flags
    succeeded (`docs/verification/backends.md`). Codex still declares the tool names, and a future
    version could add a tool these flags don't cover. The prompt also tells it not to run commands. Use
    `claude` or an API backend for untrusted transcripts.
  - `anthropic` / `openai`: plain HTTPS requests with no tool definitions.
  - `command`: the `READBACK_CMD` command is split with `shlex` (no shell) and runs in the temp dir.
    It is a command you choose; readback cannot restrict what it does beyond its working directory.
- **readback's own state** (ask threads) lives in a separate state directory
  (`READBACK_STATE_DIR`, else `$XDG_STATE_HOME/agent-readback`, else
  `~/.local/state/agent-readback`).
- **Session discovery** skips the caller's own Claude Code session (`CLAUDE_CODE_SESSION_ID`).

`tests/test_readonly.py` checks this end to end: it hashes the content and mtime of every file in
the transcript and the worktree, runs every CLI mode, a multi-turn ask, live watch, the web API and
a backend that tries to write to its cwd, and asserts that nothing changed.

### 2. Local web view

`readback web` serves a page and a small JSON API:

- it binds to `127.0.0.1` only;
- requests whose `Host` header is not `127.0.0.1`, `localhost` or `[::1]` are rejected (DNS
  rebinding);
- every POST (which can trigger a model call) must carry `X-Readback: 1`. A custom header forces a
  CORS preflight that the server never approves, so other web pages cannot make it spend tokens.

There is no authentication: any local user or process that can reach the port can read the session
through the API. Do not expose the port through a tunnel or proxy.

### What leaves your machine

**The evidence pack is sent to the LLM backend you choose.** It contains transcript content (user
prompts, the agent's messages and reasoning summaries, tool inputs and outputs, file paths) and diff
hunks of the worktree, clipped to the token budget. If the transcript or worktree contains secrets,
they can be included. Untracked files are read only if they are regular files inside the worktree:
symlinks are rendered as their link text (as git does) and never followed, and devices or FIFOs are
skipped, so a planted link cannot pull a file from elsewhere on your machine into the pack (audit
round 22). Run `readback pack` to see exactly what would be sent. With the `claude` or
`codex` CLI backend the data goes wherever that CLI is configured to send it; with `anthropic` /
`openai` it goes to `ANTHROPIC_BASE_URL` / `OPENAI_BASE_URL`. The `fake` backend sends nothing.

The web page loads Mermaid (pinned `mermaid@11.4.1`) from `cdn.jsdelivr.net` to render diagrams.
That request carries no session content; diagrams are rendered in the browser.

### Out of scope

- What the backend provider does with the data it receives.
- Behaviour of a user-supplied `READBACK_CMD`.
- Prompt injection inside the observed transcript changing the explanation's content. With the
  `claude`, `anthropic` and `openai` backends the explainer has no tools, so injected text can affect
  only the answer text, which is shown with citations you can check against `readback events`. With
  the `codex` backend, the same holds as long as Codex honours the disabled features; before audit
  round 16 it did not cover Codex's shell and web tool (see above).
