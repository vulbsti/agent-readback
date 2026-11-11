# Read-only check with a real backend on a real worktree

`tests/test_readonly.py` proves the guarantee in CI, using synthetic data and offline backends. This check complements it: `eval/scripts/readonly_check.py` ran against session s01's actual sandbox worktree, a git repo with staged changes (239 files including `.git`), using the real `claude` backend.

Before the run, a tracked file (`README.md`) was made **stat-dirty**: its mtime changed, its content did not (`touch -d '+5 seconds' README.md`). In that state a plain `git diff` rewrites `.git/index`, even with `--no-optional-locks` (git 2.43). That is the case the final audit led us to fix (see DECISIONS.md).

```
$ touch -d "+5 seconds" <s01 worktree>/README.md
$ python eval/scripts/readonly_check.py <s01 transcript> <s01 worktree> --backend claude
files hashed: 239 (transcript + worktree incl. .git)
readback events      exit=0   0.1s stdout= 2228 chars 
readback pack        exit=0   0.1s stdout=18616 chars 
readback overview    exit=0  15.3s stdout= 2440 chars [claude · 18 events · cites 16 · coverage 100% · 9552→1065 tok · 15.2s]
readback walkthrough exit=0  31.6s stdout= 2793 chars [claude · 18 events · cites 20 · coverage 100% · 20132→2624 tok · 31.5s]
readback mechanism   exit=0  34.8s stdout= 3000 chars [claude · 18 events · cites 13 · coverage 100% · 20347→3262 tok · 34.7s]
readback ask         exit=0   9.5s stdout= 1555 chars [claude · 18 events · cites 14 · coverage 92% · 9486→708 tok · 9.4s]
readback ask         exit=0  10.8s stdout= 1338 chars [claude · 18 events · cites 4 · coverage 100% · 10199→672 tok · 10.7s]
web /api/explain  events=18 cited=16 coverage=0.96
web /api/ask      events=18 cited=5 coverage=1.0
files hashed after: 239; changed or new: 0
RESULT: PASS (nothing modified)
```

An earlier run, made before the throwaway-index fix and without a stat-dirty file, also passed: 239 files, 0 changed.

## Filters and diff drivers (audit round 20)

`git diff` runs the observed repo's clean filters and diff drivers. readback's protections are `--no-ext-diff --no-textconv` on `git diff` and, on every git call, `-c filter.lfs.process= -c filter.lfs.clean= -c filter.lfs.required=false` (`_SAFE_CONFIG` in `gitdiff.py`).

- **Cached textconv:** the read-only test fixture has a committed file with a `cachetextconv` diff driver, modified afterwards. Without `--no-textconv`, `git diff` creates `refs/notes/textconv/*`, and `tests/test_readonly.py` fails (mutation check run in audit round 20).
- **git-lfs** (not installed on the build host, so run in `python:3.10-slim` with git and git-lfs from Debian): a repo tracking `*.bin` with LFS, one committed `a.bin`, then `a.bin` rewritten. Snapshot of every file and directory under `.git` (path, size, mtime) before and after:

```
diff bytes 97
['diff --git a/a.bin b/a.bin', 'Binary files a/a.bin and b/a.bin differ']
LFS PROBE: .git unchanged
== control: plain git diff
control: CHANGED
> lfs/objects/4c/df/4cdfa603…  2000 …
```

readback's diff left `.git` unchanged and showed a binary-diff hunk; a plain `git diff` on the same repo stored a new object under `.git/lfs/objects/`. Custom clean filters other than LFS cannot be disabled by wildcard; that exception is disclosed in SECURITY.md.

- **Hooks** (audit round 21): writing readback's throwaway index ran the repo's `post-index-change` hook. Every git call now passes `-c core.hooksPath=/dev/null`. The read-only fixture has a hook that appends to a file under `.git`; removing the override fails `tests/test_readonly.py`.
- **Untracked symlinks** (audit round 22): untracked paths are `lstat`ed; symlinks are rendered as their link text (mode 120000) and never followed, and non-regular files are skipped. The fixture has an untracked link to a secret outside the worktree; following it fails `tests/test_transcripts.py` (mutation check). A probe with a link to `/dev/zero` and a FIFO returned a one-line link hunk and no hang.
- **Racy entries:** the throwaway index is copied with `shutil.copy2`, keeping its mtime. `tests/test_transcripts.py` makes a same-size edit right after a commit and checks it appears in the diff; with `shutil.copyfile` the edit was missing in 3 of 3 runs.
