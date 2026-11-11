# Adversarial audit: round 22

A fresh auditor with no prior context checked `VERIFICATION.md` row by row against the repo at `89eddd2` (tag `v0.1.0`), the eight project criteria and the OSS release standard. It also re-checked the fixes from rounds 1–21 (`audits.md`) instead of trusting the summary.

**Verdict: FAIL (1 gap).**

## What was run

| check | result |
|---|---|
| `bash scripts/verify.sh` | 11 passed, 0 failed (tests, lint, zero deps, sanitizer 0 findings, privacy grep 0 hits in 289 tracked files, history scan, commit identities, gitleaks "no leaks found", media sizes, required files, ROADMAP 8 issues, `claude plugin validate .`) |
| `uv run pytest -q` | 10 passed |
| CI steps of `.github/workflows/ci.yml` on `git archive HEAD` in a clean `python:3.10-slim` container | ruff check and format pass, 10 passed (Python 3.10.22, git 2.47.3) |
| Mutation checks on a copy of `src/` and `tests/` | each fix from rounds 1, 17, 18, 19, 20 and 21 makes the suite fail when reverted: no throwaway index (1 fails), no `core.hooksPath=/dev/null` (1 fails), no `--no-textconv` (2 fail), `copyfile` instead of `copy2` (1 fails), no `--until` bound on `--base auto` (1 fails), unknown-only citation lines counted as cited (1 fails), no Codex uuid-prefix match (1 fails) |
| Eval numbers recomputed from `eval/results/v3` | `summarize.py` output matches every table in `docs/eval.md` and README; each stored score equals the sum of its grades; v3 raw files are byte-identical to v2; coverage recomputed with `citations.check`: 330 of 340 lines (97.1%), min 90.0%, mean 97.5% over 18 notes; screen rows 32–46 @120 and 42–59 @80, as published |
| README quickstart from a freshly built wheel in a throwaway `HOME`, `READBACK_BACKEND=fake` | `events`, `overview`, `ask`, thread print and `mechanism` work; `sessions` and `overview` with no sessions give the documented messages; wheel contains `web/index.html` |
| Web view (`readback web --backend fake` on s06) in a browser | clicking the `H3` chip selects, highlights and scrolls the diff hunk into view; a foreign `Host` header and a POST without `X-Readback` both get 403 |
| `claude` backend flags, tiny real call | the model reports no tools and no global `CLAUDE.md` content (matches `docs/verification/backends.md`); the probe left no transcript and no config entry |
| `codex` backend, tiny real call (Codex CLI 0.166.0) | flags still accepted, answer returned; the throwaway `CODEX_HOME` was removed; no `auth.json` link left anywhere in the scratch area |
| GitHub, read-only `gh api` | repo is `private`; `main` is at `a23145f`; run 42070291758 has 4/4 jobs `success` on `a23145f` |
| Privacy | private-pattern grep, plus an extra sweep for further personal project, host and tool names: no hits in tracked files (only false positives such as `\n1`). The demo GIF frames, README renders and image metadata show no personal data |

## Per-criterion results

### Project criteria

| # | criterion | result | evidence checked |
|---|---|---|---|
| 1a | Claude Code transcripts, finished | PASS | parser test passes; s01, s03, s05 parse (quickstart and recomputation above) |
| 1b | Claude Code transcripts, live | PASS | `test_live_tail_sees_only_complete_lines_and_late_results` passes; `live-tail.md`: lag figures recounted (7 of 12 within ~1 s, max 5.2 s) |
| 1c | Codex CLI transcripts | PASS | parser test passes, including id-prefix resolution (mutation check); s02, s04, s06 parse |
| 2 | Four modes, multi-turn ask, Mermaid | PASS | `prompts.MODES`; all modes run with the fake backend; ask thread persists and prints; Mermaid diagram rendered in the demo GIF's Mechanism frame |
| 3 | Claims cite [E#]/[H#]; clickable in the web view | PASS (measured) | coverage recomputed exactly; chip click verified in a browser |
| 4 | Read-only checksum test | PASS | `tests/test_readonly.py` passes, and its protections are load-bearing (mutation checks). Disclosed exceptions (split index mtime, custom clean filters) hold as stated. Gap 1 concerns *what is read*, not what is written |
| 5 | Comprehension eval | PASS | 6 sessions × 10 keyed questions; same budgets (explainer context ≤ B, raw = B); explainer beats raw at 2k (74.6 vs 54.2) and 6k (85.0 vs 80.0); losses, ceiling, variance and the s03 q10 replacement are disclosed |
| 6 | Concise, one screen | PASS (at 120 columns, as qualified) | fit-to-screen code and test; lengths recomputed; the 80-column overflow is stated |
| 7 | `claude -p`, `codex exec`, API key; no hardcoded vendor | PASS | `backends.pick`; real calls for `claude` and `codex`; API backends only stub-tested, as stated |
| 8 | Never adds to the executor's context, never modifies its repo | PASS | no writes found; plugin cost and the `--plugin-dir` recommendation are disclosed; own session skipped via `CLAUDE_CODE_SESSION_ID` |
| — | Deliverables: CLI, plugin, web view | PASS | `claude plugin validate .` passes; command and skill files present; web view works |

### OSS standard

| item | result | evidence checked |
|---|---|---|
| A. Own repo, distinct name, `DECISIONS.md` | PASS | `DECISIONS.md` § Name |
| A. Private repo under vulbsti, pushed | PARTIAL (accepted owner blocker) | private, `main` at `a23145f`; later commits and tag unpushed (BLOCKED.md #1) |
| A. No work email, no co-author lines | PASS | `verify.sh` identities check; repo-local identity is the noreply address; tag tagger is noreply |
| A. Not public, release commands in `RELEASE.md` | PASS | `RELEASE.md` steps 0–4 |
| B. Sources read-only, live tools untouched | PASS (not independently verifiable beyond the repo) | no code references sibling repos |
| B. No personal data at HEAD | PASS | privacy grep, extra sweep, GIF frames; history handled by RELEASE step 1 (accepted) |
| B. gitleaks 0 findings | PASS | `verify.sh` |
| C. One-command install, OS stated | PASS | wheel builds and installs; README states Linux/macOS CI scope and Windows untested |
| C. Fresh-user test | PASS | `fresh-user.md` run 2 PASS; current quickstart re-run by this audit |
| C. Few meaningful tests, CI green | PASS for last pushed commit; later commits accepted blocker | 10 tests in 4 files; local container CI on HEAD passes |
| C. Tag `v0.1.0`, CHANGELOG | PASS | tag on HEAD; `CHANGELOG.md` |
| D. Project files, docs, ROADMAP ≥5, AGENTS.md | PASS | `verify.sh` required-files check; ROADMAP has 8 |
| E. Hero, architecture SVG light/dark, demo GIF, explainer visual, sizes, rendered check | PASS | files present and distinct per theme; 1.1 MB total; renders match the current README commit |
| F. README claims backed; bad numbers reported; Alternatives | FAIL on one claim (Gap 1); otherwise PASS | see Gap 1 |
| G. Decisions, BLOCKED, VERIFICATION, audit loop | PASS | files present; this report |

## Gaps

### 1. Untracked symlinks are followed: files outside the worktree are read and sent to the backend

- **Where:** `src/agent_readback/gitdiff.py`, `_untracked_diff()`, which calls `os.path.getsize(path)` and `open(path, "rb").read()` on every name from `git ls-files --others`.
- **Why:** both calls follow symlinks. An untracked symlink in the observed worktree that points outside it is rendered as a new-file hunk containing the *target file's contents*. Those contents go into `readback pack` and to the model backend. Reproduced with an untracked link to a file outside the repo: the pack contained the target's text as `[H2] link_to_secret (added, +1 -0)`. `git diff` itself would show only the link target path (mode `120000`). A link to a device such as `/dev/zero` makes readback read without end: under a 3 GB memory cap it died with `MemoryError`, and without a cap it would exhaust memory. Any agent or planted instruction that can create a symlink in the worktree can make readback upload a file such as an SSH key or cloud credentials to the explainer backend, or hang it. This contradicts README ("readback only reads the transcript file and the git diff") and SECURITY.md's description of what leaves the machine ("diff hunks of the worktree"). Nothing discloses it. Gap rules 1 and 2.
- **Fix:** in `_untracked_diff`, `os.lstat()` each path. Render a symlink the way git does (`new file mode 120000`, body = `os.readlink()` text), and skip anything that is not a regular file (`stat.S_ISREG`). Add an untracked symlink to a file outside the repo to the `repo` fixture, and assert that the target's content is absent from the pack in an existing test. Then update SECURITY.md and re-run local container CI.

## Notes (not gaps)

1. **The fit-to-screen fallback is untested.** `docs/eval.md` and VERIFICATION row 6 cite `test_answers_longer_than_a_screen_are_shortened` for "keep the original if the shorter one drops below 90% coverage". The test covers only the accepted-shortening path: replacing `chk3.coverage >= 0.9` with `True` still passes. The code is a single visible condition. Consider one more assertion, or cite the test only for the shortening pass.
2. **The `claude` CLI adds its own context.** Even with readback's flags, `claude -p` puts the signed-in account's email address and the current date into the model's context (about 1k tokens of CLI overhead; probe in this round). That goes to the same provider the CLI is logged into, and `docs/backends.md` correctly says readback itself adds nothing. A one-line mention in `docs/backends.md` would make "what is sent" complete.
3. **`latest` silently falls back to any directory.** In explain modes, `latest` falls back to the newest session from any directory with no stderr notice (`sessions` does print one). `docs/usage.md` and `architecture.md` disclose it, but README comments it as "latest session here". A stderr line naming the chosen session's cwd would prevent explaining the wrong session.
4. **Mermaid has no SRI.** It loads from jsDelivr at a pinned version but without an `integrity` hash. That is disclosed as a network call; SRI would harden it.
5. **Unhandled bad query.** `/api/session?since=<non-integer>` raises an unhandled `ValueError` in the web handler (connection dropped, not a 400).
6. **Leftover temp dirs.** `eval/scripts/readonly_check.py` creates `readback-check-*` state directories under the system temp dir and never removes them; older runs left some behind. They contain no credentials.
7. **Stale pattern entry.** One entry in the untracked private-pattern file is still in an old encoded form and can never match. It is harmless, since the generic email pattern covers the case, and the file is not committed.
8. **A design note mentions the owner's taste.** `DECISIONS.md` ties the terse style limits to the owner's taste. It is a product-design preference, not private data, but it could be rephrased as a project goal before going public.
9. **Accepted owner-only items** (not counted): unpushed commits and tag, CI not yet run on them, and history needing the single-commit rebuild in RELEASE.md step 1.

AUDIT VERDICT: FAIL (1 gap)
