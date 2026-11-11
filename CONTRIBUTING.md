# Contributing

Thanks for helping. This file covers setup, tests, the eval, adding a transcript format, and
releases. Architecture is in [docs/architecture.md](docs/architecture.md); rules for AI coding
agents working on the repo are in [AGENTS.md](AGENTS.md).

## Dev setup

Requires Python >= 3.10, git, and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/vulbsti/agent-readback
cd agent-readback
uv sync                                         # creates .venv with pytest + ruff
uv run pytest                                   # tests
uv run ruff check . && uv run ruff format --check .
uv run readback --help                          # the CLI from your checkout
```

Without uv: `PYTHONPATH=src python3 -m agent_readback --help` works too, since there are no
runtime dependencies. Keep it that way: the package must import with the standard library only.

Linux and macOS are supported. Windows is untested.

## Tests

The suite is deliberately small. Each test guards a property that would be expensive to lose:

| file | guards |
|---|---|
| `tests/test_readonly.py` | the read-only guarantee, end to end (every mode, ask thread, watch, web API, a backend that tries to write) |
| `tests/test_transcripts.py` | Claude and Codex parsing, live tail with partial lines, diff base selection, transcript-diff fallback |
| `tests/test_citations.py` | citation parsing/checking, the repair pass and the fit-to-screen shortening pass |
| `tests/test_backends.py` | the `anthropic` and `openai` backends against a local stub HTTP server |

Rules:

- Add a test only when it protects real behaviour. Verify the rest once by hand.
- Fixtures are synthetic builders in `tests/conftest.py` (`claude_records`, `codex_records`, the
  `repo` fixture). Extend those rather than adding files.
- **Never commit real transcripts**, in tests or anywhere else. They contain prompts, paths, and
  often secrets.
- Tests that need a model use `--backend fake` or a scripted backend object; no test may require
  network access or a CLI login.
- The `repo` fixture sets `git config user.email/user.name` per repo, so no global git identity is
  needed.

## Eval

`eval/` measures whether readback's explanation helps a reader answer factual questions about a
session better than the raw transcript plus diff, at the same token budget.

```bash
uv run python eval/run_eval.py                          # all sessions, budgets 2000,6000, plus raw@full
uv run python eval/run_eval.py --sessions s01 --budgets 2000 --no-full
```

- Requires the `claude` CLI, signed in. It makes real model calls (answer and judge per condition).
- Each session lives in `eval/sessions/sNN/` (`transcript.jsonl`, `diff.patch`, `meta.json`,
  `task.md`, `questions.json`).
- Results are cached in `eval/results/`; delete a file there to recompute it.
- New sessions are built with `eval/scripts/collect.py` and must be sanitized. Before committing:

  ```bash
  uv run python eval/scripts/sanitize.py --check eval/sessions
  ```

  It must report `0 finding(s)`.

## Adding a transcript format

Parsers live in `src/agent_readback/transcripts/`. A parser is a class with:

```python
class MyParser:
    agent = "my-agent"  # stored in Session.agent

    def __init__(self, path: str):
        self.session = Session(agent=self.agent, path=path)

    def feed(self, rec: dict, line: int) -> None:
        """Consume one decoded JSONL record (line = 1-based line number)."""
```

The `feed()` contract:

- It is called once per complete line, in order, for finished files and for live tails alike
  (`Tail.poll()`). It must work incrementally: never assume the whole file is available.
- Ignore records you do not understand; never raise on unknown shapes.
- Append `Event`s with sequential ids `E1, E2, ...` (`f"E{len(self.session.events) + 1}"`).
- Fold a tool call and its result into **one** event: create it on the call, remember it by call id,
  and set `output`, `result_line` and `is_error` when the result arrives.
- Set `writes=True` and `files` for tool calls that modify files, and `patch` (unified diff) when
  the transcript carries one; this feeds the no-repo diff fallback.
- Fill `session_id`, `cwd`, `model`, `started`, `ended` when the records carry them.
- Drop injected context (system reminders, environment blocks, instruction files) so that only
  real user prompts become `user` events.

Then:

1. Add a `looks_like_<agent>(first_records)` sniffer and wire it into `_sniff()` and `Tail.__init__`
   in `transcripts/__init__.py`.
2. If the agent stores sessions in a known directory, add a root (with a `READBACK_<AGENT>_DIR`
   override) to `discover()`, `resolve()` and `_peek()`.
3. Add a synthetic builder to `tests/conftest.py` and one test in `tests/test_transcripts.py` that
   checks event kinds, call/result folding and error detection.

## Pull requests

- One logical change per PR. Run `uv run pytest -q`, `uv run ruff check .` and
  `uv run ruff format --check .` before pushing; CI runs the same on Linux and macOS.
- Changes to `prompts.py` change the product's output. Describe the effect and, if you can, run
  the eval on at least one session before and after.
- Update `CHANGELOG.md` under `## [Unreleased]`.

## Releases

1. Bump the version in all three places: `pyproject.toml` (`version`),
   `src/agent_readback/__init__.py` (`__version__`), `.claude-plugin/plugin.json` (`version`).
2. Move the `## [Unreleased]` entries in `CHANGELOG.md` to `## [X.Y.Z] - YYYY-MM-DD` and update the
   compare links.
3. Run tests, lint and format checks.
4. Commit, then tag and push the tag:

   ```bash
   git tag -a vX.Y.Z -m "vX.Y.Z"
   git push origin vX.Y.Z
   ```

Users install from git (`uv tool install git+https://github.com/vulbsti/agent-readback`), so the
tag is the release.
