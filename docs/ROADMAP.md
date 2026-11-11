# Roadmap

Scope stays narrow: explain a recorded or running agent session, read-only, with checkable
citations. Items below are candidates, not commitments.

## Near term

- **Web view coverage.** Add a GET `/` check to `tests/test_readonly.py` and verify that
  `agent_readback/web/index.html` is included in the built wheel (the server loads it from
  package resources).
- **Eval coverage.** More recorded sessions (longer sessions, other agents such as Aider or Gemini CLI)
  and a second answerer model, to check the result is not specific to one model family.
- **Large sessions.** Better budgeting for sessions with thousands of events: summarise skipped
  ranges by phase instead of a single "omitted" marker.
- **Subagent sidechains.** Claude Code sidechain records (`isSidechain`) are skipped today; render
  them as nested events.
- **PyPI release** once the CLI surface is stable.

## Good first issues

Each item is self-contained. Keep the invariants in [AGENTS.md](../AGENTS.md): read-only, zero
runtime dependencies, synthetic test data only.

### 1. Gemini CLI / OpenCode / Aider transcript parser

- **Goal:** explain sessions from one more agent. Pick one format per PR.
- **Files:** new `src/agent_readback/transcripts/<agent>.py`; `transcripts/__init__.py`
  (`_sniff`, `Tail.__init__`, and a discovery root with a `READBACK_<AGENT>_DIR` override in
  `discover`, `resolve`, `_peek`); `tests/conftest.py` (synthetic builder);
  `tests/test_transcripts.py`.
- **Acceptance:** a test loads a synthetic transcript and asserts event kinds in order, a tool
  call folded with its result, a failed call marked `is_error`, and a file-writing call with
  `writes=True` and `files` set. The same file parsed through `Tail.poll()` in two halves gives the
  same events as `load()`. Follow the `feed()` contract in CONTRIBUTING.md.

### 2. `--since` for walkthrough

- **Goal:** `readback walkthrough --since E40` explains only the steps from E40 on (with earlier
  events still available for context), e.g. "what happened since I last looked".
- **Files:** `cli.py` (flag on the mode parsers), `explain.py` (`Explainer.run` passes the start
  index), `evidence.py` (`render(..., since=...)` already exists; mark earlier events as context),
  `prompts.py` (walkthrough instruction mentions the start id).
- **Acceptance:** with the `fake` backend, `--since E5` produces a prompt whose walkthrough
  instruction names E5 and whose cited ids are all >= E5; an unknown id exits 2 with a clear
  message. Extend `tests/test_readonly.py` with one `--since` run.

### 3. Export an explanation as standalone HTML

- **Goal:** `readback overview --html out.html` writes one self-contained file: the explanation
  with citations linked to an appendix of the cited events and hunks.
- **Files:** `cli.py` (`--html PATH` in `_llm_args`), new `src/agent_readback/export.py`
  (stdlib `html.escape` only), `docs/usage.md`.
- **Acceptance:** a test with the `fake` backend writes the file to `tmp_path`; every `[E#]`/`[H#]`
  in the text is an `<a href="#E#">` whose target exists; the file has no external URLs except the
  pinned Mermaid script when a diagram is present. The read-only test still passes (output path is
  outside the observed repo in the test).

### 4. Per-file filter `--file`

- **Goal:** `readback overview --file src/app.py` focuses on one file: only hunks in that file and
  events that touched it (plus user prompts and agent messages for context).
- **Files:** `cli.py` (`_session_args`), `evidence.py` (filter in `render`), possibly
  `gitdiff.py` (path matching against repo-relative names).
- **Acceptance:** `readback pack --file calc.py` on the `repo` fixture contains `calc.py` hunks and
  no `test_calc.py` hunk; tool events that did not touch `calc.py` are absent; user events remain.
  A glob (`--file 'src/*.py'`) works.

### 5. Token counting via the backend

- **Goal:** budget by real tokens instead of `CHARS_PER_TOKEN = 4` where the backend can count
  them (Anthropic `count_tokens` endpoint), falling back to chars/4.
- **Files:** `backends.py` (optional `count_tokens(text) -> int | None` method), `evidence.py`
  (accept a counter callable in `render`), `explain.py` (pass it through).
- **Acceptance:** a unit test with a fake counter that reports 2 chars/token produces a smaller
  pack than the default for the same budget; backends without the method behave exactly as before
  (existing tests unchanged). No new dependency.

### 6. Cite line ranges inside hunks

- **Goal:** allow `[H3:12-18]` to point at new-file lines 12-18 of hunk H3, and highlight just
  those lines in the web view.
- **Files:** `citations.py` (`CITE_RE`, `expand`, validation against `Hunk.new_start` and length),
  `prompts.py` (one sentence in `SYSTEM`), `web/index.html` (highlight), `tests/test_citations.py`.
- **Acceptance:** `check()` accepts `[H1:1-2]` for a hunk that covers those lines, reports
  `H1:40-41` as unknown when it does not, and `strip_unknown` drops only the bad range. Existing
  `[E#]`/`[H#]` behaviour is unchanged.

### 7. Windows CI

- **Goal:** find out what breaks on Windows and either fix it or document it.
- **Files:** `.github/workflows/ci.yml` (add `windows-latest`, initially `continue-on-error: true`),
  then fixes where needed: path handling in `gitdiff._link_edits` and `_untracked_diff`,
  `/dev/null` in `auto_base`, the `command` backend's `shlex.split`.
- **Acceptance:** the Windows job runs the full suite; either it passes and `continue-on-error` is
  removed, or each remaining failure has an issue and the README states what is unsupported.

### 8. `readback sessions --json`

- **Goal:** machine-readable session list for scripts and editor integrations.
- **Files:** `cli.py` (`cmd_sessions`), `docs/usage.md`.
- **Acceptance:** with `READBACK_CLAUDE_DIR` pointing at a synthetic tree, the output parses as a
  JSON list of objects with `path`, `agent`, `mtime`, `cwd`, `first_prompt`.
