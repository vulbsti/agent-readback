# AGENTS.md

Instructions for AI coding agents (Claude Code, Codex, others) working on this repository.

## What this is

`readback` explains what a coding agent did in another session. It reads a Claude Code or Codex
transcript plus the git diff of the worktree that agent changed, renders an id-tagged evidence pack,
sends it to a separate model that cannot write (no tools; for Codex, every tool feature and web search disabled), and checks its citations of `[E#]` events / `[H#]` hunks (coverage is enforced at ≥90% with one repair pass, not 100%).
Pipeline details: [docs/architecture.md](docs/architecture.md).

## Layout

```
src/agent_readback/
  cli.py              argparse entry point (`readback`), one cmd_* per subcommand
  model.py            Event, Hunk, Session dataclasses
  transcripts/
    __init__.py       format sniffing, Tail (incremental reader), load, discover, resolve
    claude.py         Claude Code parser (ClaudeParser.feed)
    codex.py          Codex CLI parser (CodexParser.feed), incl. code-mode exec
  gitdiff.py          attach_diff: diff file | git (auto base + untracked) | transcript fallback
  evidence.py         render(): budgeted evidence pack; index_lines() for `events`
  prompts.py          SYSTEM prompt, per-mode instructions, line limits, REPAIR prompt
  citations.py        parse/expand/check citations, strip unknown ids
  explain.py          Explainer (run, repair pass, ask threads), live(), state_dir()
  backends.py         claude, codex, anthropic, openai, command, fake; pick()
  web/server.py       local web view + JSON API (127.0.0.1 only)
tests/                conftest.py (synthetic builders), test_readonly.py, test_transcripts.py, test_citations.py, test_backends.py
eval/                 run_eval.py, scripts/collect.py, scripts/sanitize.py, sessions/sNN/
commands/readback.md  Claude Code slash command (/agent-readback:readback)
skills/readback/      Claude Code skill
.claude-plugin/       plugin.json, marketplace.json
docs/                 architecture, usage, plugin, backends, roadmap
```

## Invariants (do not break)

1. **Read-only guarantee.** readback must never write to the observed transcript, the observed
   worktree (including `.git`), or the agent's config.
   - Open transcripts and worktree files only with `open(path, "rb")`.
   - Call git only through `gitdiff._git` (it adds `--no-optional-locks`, `GIT_OPTIONAL_LOCKS=0` and the `_SAFE_CONFIG` overrides: no fsmonitor, no hooks, no git-lfs clean filter); `git diff` also needs `--no-ext-diff --no-textconv`.
     Anything that reads the index (`diff`, `ls-files`, `status`) must pass `index=` a throwaway copy,
     as `git_diff()` does: `git diff` rewrites stat-dirty entries even with `--no-optional-locks`.
     Never use git commands that write (`add`, `add -N`, `stash`, `checkout`, `update-index`, ...).
   - Backends must run the model without tools (Codex: read-only sandbox, web search off and every tool feature in `CODEX_DISABLED_FEATURES` disabled) and outside the observed repo (`backends._run` uses
     a temp dir).
   - readback's own writes go only under `explain.state_dir()`.
   - `tests/test_readonly.py` must stay green. Extend it when you add a mode, command or endpoint;
     never weaken or skip it.
2. **Zero runtime dependencies.** `dependencies = []` in `pyproject.toml`. Use the standard
   library (`urllib`, `http.server`, `json`, `subprocess`). Dev tools go in `[dependency-groups]`.
3. **No personal transcripts in the repo.** Tests use synthetic builders in `tests/conftest.py`. The only recorded transcripts are the sanitized eval sessions in `eval/sessions/`, made for this repo on OSS sandbox copies.
   Eval sessions must pass:
   `python eval/scripts/sanitize.py --check eval/sessions` (0 findings).
   No personal names, emails or home paths in any committed file.
4. **Prompts are the product.** Output style (terse, mechanistic, factual lines cited, coverage checked at ≥90%, one
   screen) is defined in `prompts.py` (`SYSTEM`, `MODES`, `DEFAULT_LINES`, `REPAIR`). Do not
   reword them casually; explain any change in the PR and, if possible, run the eval before and
   after.
5. **Python >= 3.10**, Linux and macOS. Ruff config is in `pyproject.toml` (line length 110).

## Before you finish

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run python eval/scripts/sanitize.py --check eval/sessions   # if eval/ changed
```

Also update `CHANGELOG.md` (`[Unreleased]`) and the relevant `docs/` page when behaviour or flags
change. Do not commit personal transcripts or `.work/`; new eval sessions must pass `eval/scripts/sanitize.py --check`. `eval/results/` is committed: it is the evidence behind `docs/eval.md`.

## How to add things

### A backend

1. In `backends.py`, add a class with `name` and `complete(self, system, prompt) -> Reply`. Its
   constructor takes `model: str | None` and raises `BackendError` if it is not configured.
2. CLI backends: build the argv, disable every tool, and call `_run(cmd, prompt)` (temp-dir cwd).
   HTTP backends: use `_post()`; read keys and base URLs from env vars.
3. Register it in `BACKENDS`. Only add it to auto-detection in `pick()` if detection is cheap and
   unambiguous.
4. Update the `--backend` help in `cli._llm_args`, `docs/backends.md`, and the backend list in
   `SECURITY.md` (what it sends where).

### A transcript format

Follow "Adding a transcript format" in [CONTRIBUTING.md](CONTRIBUTING.md): parser class with an
incremental `feed(rec, line)`, a `looks_like_*` sniffer wired into `_sniff()` and `Tail`, optional
discovery root with a `READBACK_*_DIR` override, a synthetic builder and one parser test.

### A mode

1. Add the instruction to `prompts.MODES` and a default to `prompts.DEFAULT_LINES`.
2. Add a subparser in `cli.build_parser()` (reuse `_session_args` / `_llm_args`, `cmd_mode`).
3. If the web view should offer it, allow it in `web/server.py` `/api/explain`.
4. Add the mode to the loop in `tests/test_readonly.py`, and to `commands/readback.md` and
   `skills/readback/SKILL.md` if users should reach it from the plugin.
5. Document it in `docs/usage.md`.
