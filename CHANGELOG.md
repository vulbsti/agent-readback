# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-11-05

### Added

- `readback` CLI, a read-only explainer for coding-agent sessions, with four explanation modes:
  `overview` (changed / why / tests / risks), `walkthrough` (numbered steps), `mechanism` (Mermaid
  data/control-flow diagram plus bullets) and `ask` (multi-turn follow-up questions, thread kept
  per session in readback's state directory, `--reset` to start over).
- Non-LLM commands: `events` (event and hunk index with ids), `pack` (the exact evidence pack sent
  to the model), `sessions` (recent sessions for the current directory or `--all`).
- `watch`: live tail of a running session, printing each new event; `--explain-every N` adds a
  short delta explanation every N events.
- `web`: local web view (127.0.0.1) with the explanation beside the transcript events and diff
  hunks; citations are links.
- Citations: claims cite `[E#]` transcript events and `[H#]` diff hunks. Answers are checked
  for unknown ids and uncited lines, repaired once if coverage is below 90%, and unknown ids are
  stripped. Coverage is reported with each answer.
- Transcript parsers for Claude Code (`~/.claude/projects`) and Codex CLI (`~/.codex/sessions`),
  including Codex code-mode `exec` calls. Parsing is incremental and works on live files.
- Diff collection: `--diff-file`, git worktree against `--base` (default `auto`: parent of the
  first commit made inside the session's time window, else `HEAD`, plus untracked files), or the edits recorded
  in the transcript when there is no repo.
- Evidence pack with a token budget (`--budget`, default 40000) that gives user prompts, agent
  messages, failing commands and hunks the most room.
- Backends: `claude` CLI, `codex` CLI, Anthropic Messages API, OpenAI-compatible
  `/chat/completions`, generic stdin/stdout `command`, and an offline `fake`. Auto-detected as
  `READBACK_CMD`, then the CLIs, then API keys; override with `--backend` / `READBACK_BACKEND`.
- Fit-to-screen pass: answers longer than 48 rows × 120 columns are shortened once, keeping
  citation coverage ≥ 90%.
- Claude Code plugin: `/agent-readback:readback` command and a `readback` skill.
- Read-only guarantee enforced in code (binary-mode reads, `git --no-optional-locks` plus a throwaway
  index copy for `git diff`, explainer
  model in a temp dir that cannot write: no tools for `claude` and the API backends; for `codex`, a read-only sandbox,
  web search and every tool-providing feature disabled, and an isolated `CODEX_HOME`) and covered by `tests/test_readonly.py`.
- Comprehension eval (`eval/run_eval.py`) over six sanitized recorded sessions, with
  `eval/scripts/sanitize.py --check` for committed transcripts.
- Zero runtime dependencies; Python >= 3.10; Linux and macOS.

[Unreleased]: https://github.com/vulbsti/agent-readback/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/vulbsti/agent-readback/releases/tag/v0.1.0
