# Verification

This maps every criterion (the project criteria from the build brief and the owner's OSS release standard, sections A–G; the standard lives outside this repo) to evidence: a command with its output, or a file. Mechanical checks can be re-run with `scripts/verify.sh`, which prints PASS/FAIL per check (last run: 11 passed, 0 failed). Items that need the owner are marked **BLOCKED** and listed in `BLOCKED.md`.

## Project criteria

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1a | Claude Code transcripts, finished | PASS | `tests/test_transcripts.py::test_claude_folds_tool_results_and_skips_injected`; real sessions s01, s03, s05 parsed in the eval (`docs/eval.md`) |
| 1b | Claude Code transcripts, live (tailing while the session runs) | PASS | `tests/test_transcripts.py::test_live_tail_sees_only_complete_lines_and_late_results` (partial lines, late tool results); real run: `docs/verification/live-tail.md` (`readback watch` on a running `claude -p` agent: 7 of 12 events printed within ~1 s of the agent's own record timestamp, max lag 5.2 s; a cited delta explanation once at least 6 new events had arrived, here after E10) |
| 1c | Codex CLI transcripts | PASS | `tests/test_transcripts.py::test_codex_classic_and_code_mode_calls` (classic calls, code-mode `exec`, web calls); real sessions s02, s04, s06 in the eval |
| 2 | Four modes: overview, walkthrough, ask (multi-turn), mechanism (Mermaid) | PASS | `src/agent_readback/prompts.py` (`MODES`); every mode run with a real backend in `docs/verification/readonly-real-backend.md` and `docs/verification/fresh-user.md`; the multi-turn thread is kept per session (`explain.Explainer.history`, printed by `readback ask` with no question); Mermaid rendered in the web view (`docs/img/demo.gif`, Mechanism frame) |
| 3 | Every claim cites events and hunks; citations clickable in the web view | PASS (measured, not absolute) | `citations.py` checks every answer, drops unknown ids, and runs one repair pass if under 90% coverage (`tests/test_citations.py`). Measured coverage: 90.0–100% of factual lines per note, mean 97.5% per note (pooled: 330 of 340 lines, 97.1%), across the 18 v3 eval notes (`docs/eval.md`). Clicking a chip scrolls to, expands and highlights the event or hunk: checked in a browser (`docs/img/demo.gif`, frames 2–5) |
| 4 | Read-only guarantee: a test checksums the transcript and worktree before and after a full session | PASS | `tests/test_readonly.py`. **What it hashes:** bytes + mtime of every file of the observed transcripts and the worktree incl. `.git`. **Scope:** a Claude Code transcript and a Codex transcript, each through every CLI command and mode except `web` (exercised through its server, `make_server`, below); ask ×2 plus thread print; CLI `watch --duration` with delta explanations; the web view's `/` page and every API endpoint; a backend that tries to write into its cwd. **Fixture:** includes a stat-dirty tracked file. **Mutation check:** removing the throwaway-index protection in `gitdiff.git_diff` makes the test fail (`.git/index` rewritten), restoring it makes it pass. **Real-backend run:** on a real, stat-dirty git worktree (239 files): `docs/verification/readonly-real-backend.md` → `RESULT: PASS (nothing modified)`. **Fixture also has** a cached-textconv diff driver and a `post-index-change` hook (removing `--no-textconv` or `core.hooksPath=/dev/null` fails the test). **LFS:** container probe with a control in `readonly-real-backend.md`. **Disclosed exceptions:** with `core.splitIndex=true`, git refreshes the mtime (not the bytes) of `.git/sharedindex.*` on every index read (audit round 19); a repo's custom non-LFS clean filter runs as configured (SECURITY.md) |
| 5 | Comprehension eval: ≥5 real recorded sessions, 10 questions each, a fresh answerer with and without the explainer under the same token budget; explainer beats raw | PASS | **Sessions:** `eval/sessions/s01–s06` (3 `claude -p`, 3 `codex exec`, 6 MIT repos), 60 questions with keys in `questions.json`. **Harness and data:** `eval/run_eval.py`; every answer and grade in `eval/results/v1–v3`. **Report:** `docs/eval.md`. **Shipped design (v3), 2 runs:** **74.6% vs 54.2% @2k tokens, 85.0% vs 80.0% @6k**. **Ceiling:** the full raw transcript scores 97.9% at ~57k tokens. **Losses:** raw ties or beats the explainer in 3/6 sessions @6k and 2/6 @2k. **History:** v1→v2 parser fix, v2→v3 fit-to-screen pass; v3 reuses the v2 raw runs, which do not depend on readback |
| 6 | Concise, mechanistic style; default answers fit on one screen | PASS (at 120 columns) | **Rules:** style rules and line limits in `prompts.py`. **Enforcement:** the fit-to-screen pass in `explain.py` shortens any answer longer than 48 rows × 120 columns, keeping the original if the shorter one drops below 90% citation coverage (test `test_answers_longer_than_a_screen_are_shortened`). **Measured** (`eval/scripts/measure_length.py eval/results/v3`): overview 35–40 rows, walkthrough 32–39, mechanism 35–46. At 80 columns they wrap to 42–59 rows, which is stated in `docs/eval.md`. **Examples:** `docs/verification/plugin.md`, `fresh-user.md` |
| 7 | Runs through `claude -p`, `codex exec` or an API key; no hardcoded vendor | PASS | **Backends** (`src/agent_readback/backends.py`): `claude`, `codex`, `anthropic`, `openai` (any compatible endpoint), `command` (any CLI) and `fake`, chosen by `--backend` / `READBACK_BACKEND` / `READBACK_CMD`. **`claude`:** the whole eval. **`codex exec`:** a real run in `docs/verification/backends.md`; web search and every tool-providing feature are disabled; a probe found every shell, web, patch and agent-spawn call fails, and a control with the earlier flags succeeded (`docs/verification/backends.md`; the reliance on Codex feature flags is disclosed in SECURITY.md). **`command`:** the fresh-user test. **`anthropic` and `openai`:** request shape and reply parsing tested against a local stub server (`tests/test_backends.py`); not run against the live APIs (no keys on the build machine), as stated in `docs/verification/backends.md` |
| — | Deliverables: CLI, Claude Code plugin (skill + command), local web view | PASS | CLI `readback` (`docs/usage.md`); plugin: `.claude-plugin/`, `commands/readback.md`, `skills/readback/SKILL.md`, `claude plugin validate .` → passed, end-to-end slash-command runs in `docs/verification/plugin.md`; to keep the executor's context untouched it should be loaded only in the explainer window (`--plugin-dir`), while a user-scope install adds ~180 tokens of descriptions to every session (estimate in `docs/verification/plugin.md`) (disclosed in README and `docs/plugin.md`); web view `src/agent_readback/web/` (`docs/img/demo.gif`) |

## OSS standard

### A. Repo and identity
| Item | Status | Evidence |
|---|---|---|
| Own git repo under `~/proj/oss/<name>/`, distinct name checked on GitHub/PyPI/npm | PASS | `DECISIONS.md` § Name (PyPI 404, npm 404, GitHub free for `agent-readback`) |
| Private GitHub repo under vulbsti, pushed | PASS | https://github.com/vulbsti/agent-readback, `PRIVATE`, recreated on 2026-11-12 from one clean commit with `main` and `v0.1.0` (BLOCKED.md → Resolved). The pre-release repository was deleted on 2026-11-12 |
| No work-domain author email; no `Co-Authored-By` lines | PASS | `scripts/verify.sh` → "commit identities": every author/committer address on every ref is a GitHub noreply address (ours, plus Dependabot's), and no commit message has a co-author line |
| Commits at verified milestones | PASS | `git log --oneline` (milestone commits, not per-step) |
| Not public, nothing published; go-public/publish commands in `RELEASE.md` | PASS | Repo visibility `PRIVATE`; `RELEASE.md`; nothing was published or posted |

### B. Sources and privacy
| Item | Status | Evidence |
|---|---|---|
| Sources read-only; the owner's live tools untouched | PASS | The owner's source repos and transcript folders were only read (`sed`/`grep`/`cat`). Nothing in them, or in the owner's live tools and their data directories, was modified. Transcript parsing was written fresh in `src/agent_readback/transcripts/`, with no dependency on sibling repos |
| No personal data; fixtures synthetic or generated for the repo | PASS | **Tests:** builders in `tests/conftest.py`. **Eval transcripts:** recorded for this repo and sanitized by allowlist (`eval/scripts/sanitize.py`); `sanitize.py --check eval/sessions` reports 0 findings. **Workflow-preference echoes:** two agent final messages (s01, s03) echoed the owner's preferences. Both are redacted at HEAD, disclosed in `docs/eval.md` and `DECISIONS.md`, and now caught by the sanitizer; a sweep of all six transcripts found no others. The published history is one commit built from this tree, so the earlier versions are not in it (BLOCKED.md → Resolved). **Vault:** no vault text; the owner's notes informed intent only and are not quoted anywhere |
| gitleaks on full history: 0 findings | PASS | `scripts/verify.sh` → `no leaks found` |
| grep for the owner's home path, work domain, name, and email addresses | PASS at HEAD | `scripts/verify.sh`, "privacy grep on tracked files": generic patterns (foreign home paths, real emails, tokens) plus the owner-specific patterns from an untracked local file (`.work/private-patterns.txt`, never committed; DECISIONS.md), giving `0 hits`. The history scan reports earlier commits that still contain removed details, which is why published history must be rebuilt from HEAD (BLOCKED.md #3) |

### C. Usable by other people
| Item | Status | Evidence |
|---|---|---|
| One-command install; supported OS stated | PASS | README Install (`uv tool install git+…` / `pipx`; plugin via marketplace or `--plugin-dir`); CI passed on Linux and macOS for the last pushed commit; later commits tested on Linux; Windows untested (README states exactly this) |
| Fresh-user test from the README only, in a throwaway HOME | PASS | `docs/verification/fresh-user.md`: run 1 `VERDICT: PASS` with 6 friction points → fixed (READBACK_CMD auto-selects, readable backend errors, empty-sessions message, quickstart order, latency/budget note); run 2 `VERDICT (run 2): PASS`; its 3 remaining nits fixed afterwards (mechanism length, sessions message, web flags in README) |
| Few meaningful tests | PASS | 10 tests in 4 files, each covering a guarantee: parsing both formats, live tail, diff base, citations + repair, fit-to-screen, read-only, API backends against a stub |
| GitHub Actions CI (lint + tests) green on the private repo | PASS | Run [43094381369](https://github.com/vulbsti/agent-readback/actions/runs/43094381369) on the published release commit `d8d49c2`: **4/4 jobs success**, ubuntu-latest and macos-latest × py3.10 and py3.13. Earlier runs, including the one on `a23145f`, were in the pre-release repository, deleted on 2026-11-12. The same steps also pass in a clean `python:3.10-slim` container (`docs/verification/ci-local.md`), and `scripts/verify.sh` passes. Dependabot is enabled. |
| Tag `v0.1.0`; `CHANGELOG.md` | PASS | `git tag` → `v0.1.0`; `CHANGELOG.md` |

### D. Maintainable as an open-source project
| Item | Status | Evidence |
|---|---|---|
| LICENSE (Apache-2.0), README, CONTRIBUTING, CODE_OF_CONDUCT (Contributor Covenant), SECURITY, issue templates, PR template, CODEOWNERS (@vulbsti), Dependabot | PASS | `scripts/verify.sh` → "required project files" PASS |
| `docs/architecture.md`, usage guides, `docs/ROADMAP.md` with ≥5 good first issues | PASS | `docs/architecture.md`, `docs/usage.md`, `docs/plugin.md`, `docs/backends.md`; ROADMAP has 8 scoped good first issues (goal, files, acceptance test) |
| `AGENTS.md` | PASS | `AGENTS.md` (layout, invariants, checks to run, how to add a backend/format/mode) |

### E. Visuals
| Item | Status | Evidence |
|---|---|---|
| Hero image | PASS | `docs/img/hero.jpg` (gpt-6-luna via `codex exec`, prompt in `assets/src/hero.prompt.txt`, overlay `assets/src/hero.html`) |
| Architecture diagram (SVG, light + dark) | PASS | `docs/img/architecture-{light,dark}.svg` via `<picture>`; source `assets/src/architecture.py` |
| Demo GIF of the real tool running | PASS | `docs/img/demo.gif`: Playwright capture of the real web view with the real `claude` backend (`assets/src/demo_web.py`) |
| Explainer visual | PASS | `docs/img/live.png` (real `readback watch` output from a live session, `assets/src/live.html`) and `docs/img/eval-{light,dark}.svg` (eval chart, `assets/src/eval_chart.py`) |
| Sources in `assets/src/`; each image < 2 MB, README media < 10 MB | PASS | `scripts/verify.sh` → largest 765 KB, total 1.1 MB |
| Checked as rendered in a GitHub-style README, light and dark | PASS | `assets/src/render_readme.py` renders README.md with github-markdown-css in both color schemes via Playwright: `docs/verification/readme-render-light.png`, `readme-render-dark.png`. The first render led to fixes in the diagram routing and clipped labels |

### F. Honesty
| Item | Status | Evidence |
|---|---|---|
| Every README claim backed by a test or benchmark | PASS | **Eval numbers and coverage:** `docs/eval.md` + `eval/results/v3/summary.json`. **Read-only:** `tests/test_readonly.py` + `docs/verification/readonly-real-backend.md`. **Live:** `test_live_tail…` + `docs/verification/live-tail.md`. **Zero deps:** `pyproject.toml`. **Throwaway-index git:** `gitdiff.git_diff` + mutation check. **Linux + macOS:** CI run 42070291758. **10–60 s latency:** timings in `docs/verification/readonly-real-backend.md`, `fresh-user.md`. **"Sends nothing else":** only `backends.py` and the web page's Mermaid CDN make network calls; the `codex` backend's model has web search and its tool features disabled (probe in `docs/verification/backends.md`) |
| Bad numbers reported | PASS | `docs/eval.md`: the raw full transcript beats the explainer (97.9% vs 85.0%); the 6k margin (+5 points) is within run-to-run variance; raw ties or wins in 3/6 sessions @6k and 2/6 @2k; v3 accuracy slightly below v2; at 80 columns the answers exceed one screen; explainer cost is 26k–71k tokens per session |
| Factual Alternatives section after checking the projects | PASS | `docs/alternatives.md` (13 projects checked via GitHub API / docs on 2026-11-05) and the README summary |

### G. How to work
| Item | Status | Evidence |
|---|---|---|
| Decisions recorded | PASS | `DECISIONS.md` |
| Owner-only items logged | PASS | `BLOCKED.md` |
| This file maps every criterion | PASS | this file |
| Final adversarial audit by a fresh agent | PARTIAL: last full round (22) found 1 gap, fixed and re-checked narrowly; no full round passed clean | Rounds 1–22: every gap and its fix in `docs/verification/audits.md` (the raw reports quoted private details while describing leaks, so they were replaced by the summary). Round 22's report, the last full round: `docs/verification/audit.md`. Its one gap (untracked symlinks) was fixed in code with a test, a mutation check, a probe and local container CI, under the convergence decision recorded in `audits.md` |

## CI on the re-created repository (2026-11-12)

The repository was re-created from clean history on 2026-11-12 (BLOCKED.md → Resolved). Earlier run ids refer to the pre-release repository, which was deleted on 2026-11-12. First CI run on the new repository: [run 43094381369](https://github.com/vulbsti/agent-readback/actions/runs/43094381369) on `d8d49c2` (the published release commit): ubuntu-latest and macos-latest × py3.10 and py3.13: 4/4 success. Before the push, every object was checked by the owner's out-of-repo privacy gate (private-terms scan of text, messages and binary strings; author identities; gitleaks): 0 findings.
