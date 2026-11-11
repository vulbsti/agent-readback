## What and why

<!-- One or two sentences. Link the issue if there is one. -->

## How it was checked

- [ ] `uv run pytest -q`
- [ ] `uv run ruff check . && uv run ruff format --check .`
- [ ] Manual run (paste the command; redact output):

## Checklist

- [ ] Read-only guarantee kept; `tests/test_readonly.py` passes unchanged or is extended, not weakened.
- [ ] No new runtime dependency.
- [ ] No real transcripts, paths or secrets added. Eval sessions pass `python eval/scripts/sanitize.py --check eval/sessions`.
- [ ] `prompts.py` changes: effect on output described (eval run if possible).
- [ ] `CHANGELOG.md` updated under `[Unreleased]`.
- [ ] Docs updated (`docs/`, `--help` text) if behaviour or flags changed.
