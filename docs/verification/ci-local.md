# CI steps run locally in a clean container

GitHub Actions ran CI on the last pushed commit, `a23145f`: run 42070291758, **4/4 jobs green** (ubuntu and macOS × py3.10 and py3.13). The commits after it could not be pushed from the build session (see BLOCKED.md).

For those later commits, the exact steps of `.github/workflows/ci.yml` were run on a `git archive` export of `e8cab1a`, inside `python:3.10-slim` (the lowest supported Python; the container ships git 2.47). `e8cab1a` is the last commit that changes code, tests, scripts or configuration (audit round 22 stopped following untracked symlinks in `src/agent_readback/gitdiff.py` and extended `tests/conftest.py` and `tests/test_transcripts.py`). Commits after it change only documentation. Check with `git diff --stat e8cab1a HEAD -- src tests scripts eval/scripts 'assets/src/*.py' .github pyproject.toml uv.lock`, which prints nothing. (Non-Python sources under `assets/src/`, such as the HTML behind the README screenshots, are not touched by CI.)

```bash
git archive e8cab1a -o .work/src.tar && docker run --rm -v "$PWD/.work/src.tar:/src.tar:ro" -w /w python:3.10-slim bash -c "apt-get update && apt-get install -y git; pip install uv; tar xf /src.tar; uv sync; uv run ruff check .; uv run ruff format --check .; uv run pytest -q; python --version; git --version"
```

Last lines of the log (apt, pip and `uv sync` output omitted):

```
All checks passed!
66 files already formatted
..........                                                               [100%]
10 passed in 3.94s
Python 3.10.22
git version 2.47.3
```
