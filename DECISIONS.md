# Decisions

Decisions made while building v0.1.0, with the reason for each. The owner was not available for questions, so each choice below was made and recorded here.

## Name: `agent-readback` (CLI `readback`)
"Readback" is the aviation and radio practice of repeating an instruction back so both sides know it was understood. That is the job of this tool. Checked on 2026-11-05:
- PyPI `agent-readback`: 404 (free).
- npm `agent-readback`: 404 (free).
- GitHub `vulbsti/agent-readback`: free. The one search hit is an unrelated repo whose name contains that substring.
- `readback` alone is taken on PyPI and npm.
- `whatdid`, `loupe` and `tracebook` were rejected because they are taken on npm or PyPI.

## Language and dependencies: Python 3.10+, zero runtime dependencies
- One-command install (`uv tool install` or `pipx`), with nothing to resolve.
- The HTTP backends use `urllib`, and the web view uses `http.server`.
- The frontend is a single static HTML file.
- Mermaid loads from jsdelivr at a pinned version, and only when a diagram is shown.

## License: Apache-2.0
This is the OSS standard default. There was no reason to deviate.

## Commit identity
Commits use `vulbsti <29302849+vulbsti@users.noreply.github.com>`, so no personal email appears in a public history.

## Read-only design
The guarantee is enforced by construction, not by convention:
- **Transcripts** are only opened with `open(path, "rb")`. Tailing seeks to a byte offset and never writes or locks.
- **Git** calls always use `--no-optional-locks` and `GIT_OPTIONAL_LOCKS=0`. `git diff` and `git ls-files` also run against a throwaway copy of the index (`GIT_INDEX_FILE`).
  - **Why both:** the final audit found that the read-only test had no stat-dirty file, so it could not catch an index rewrite. With such a file added, a plain `git diff <base>` rewrote `.git/index` *even with* `--no-optional-locks` (git 2.43).
  - **Protection now:** the temp index closes that hole.
  - **Proof:** the test fixture now includes a stat-dirty file. Removing the temp index makes `tests/test_readonly.py` fail.
- **Hooks** (audit round 21): writing the throwaway index still ran the repo's `post-index-change` hook, which could write into the worktree. Every git call now passes `-c core.hooksPath=/dev/null`, and the read-only fixture has such a hook.
- **Filters and diff drivers** (audit round 20): `git diff` runs the repo's clean filters and diff drivers. readback passes `--no-ext-diff --no-textconv` and unsets git-lfs's clean filter, so LFS objects and cached textconv notes are never written (the read-only fixture includes a cachetextconv driver; an LFS probe with a control is in `docs/verification/readonly-real-backend.md`). Other custom clean filters cannot be disabled by wildcard, so that exception is disclosed in SECURITY.md. The throwaway index is copied with `shutil.copy2`, keeping its mtime, because a fresh mtime defeats git's racy-entry check and hid same-size edits made in the second of the last index write.
- **Split index exception:** In a repo with git's split index (`core.splitIndex=true`), git itself refreshes the mtime of `.git/sharedindex.*` whenever it reads the index, even through readback's throwaway copy; the bytes do not change. This cannot be configured away (git freshens a shared index it loads), so it is disclosed in SECURITY.md rather than tested. Every git call also passes `-c core.fsmonitor=false`.
- **Untracked files** are rendered by reading them. `git add -N` is avoided because it writes the index. Only regular files are read (`lstat`, `O_NOFOLLOW`); symlinks are rendered as their link text, mode 120000, as git does. Audit round 22 showed that following them could put a file from outside the worktree (or endless `/dev/zero`) into the pack; the test fixture has an outside-pointing link.
- **The explainer model** cannot write. With `claude` and the API backends it gets no tools at all. For `codex exec`, audit round 16 showed that the earlier flags still left the model a shell and a working web tool. The backend now also disables web search and every tool-providing feature (`CODEX_DISABLED_FEATURES` in `backends.py`, including `code_mode_host` and `shell_tool`). A probe found every tool call fails, while a control with the old flags ran `ls /` and fetched a web page (`docs/verification/backends.md`). It still uses a throwaway `CODEX_HOME` (only `auth.json` linked, so no global instructions or memories). The block rests on Codex's feature flags, which is disclosed in SECURITY.md. For `claude -p` that means `--tools ""`, no session persistence, no setting sources and no MCP. For `codex exec` it means a read-only sandbox and `--ephemeral`. Either way it runs in a fresh temp dir, never in the observed repo.
- **Explainer state** (ask threads) lives in `$XDG_STATE_HOME/agent-readback/`.
- **Test:** `tests/test_readonly.py` hashes the bytes and mtime of every file in the transcript and the worktree (including `.git`) before and after a full session. That session covers every CLI mode, a multi-turn ask, live watch, the web API, and a backend that deliberately tries to write to its cwd. The test then checks that nothing changed.

## Context isolation from the executor
- readback never sends anything to the executor session. It only reads the transcript file.
- The plugin is meant for a *second* window. In that window, readback excludes the window's own session (`CLAUDE_CODE_SESSION_ID`) when it picks "latest".

## Plugin: recommend `--plugin-dir` in the explainer window
Audit round 7 pointed out that a user-scope marketplace install loads the plugin into every Claude Code session, including the executor's. That costs about 180 tokens of command and skill descriptions (Claude Code's own estimate: `claude --plugin-dir . plugin details agent-readback` reports ~177 tokens always-on, split ~120 and ~60 between the skill and the command; see `docs/verification/plugin.md`).
- Project and local scope don't avoid this, because both windows usually share one directory.
- The docs therefore recommend `claude --plugin-dir` in the explainer window only, and disclose the cost of the user-scope install.

## Events: a tool call and its result are one event
- A citation such as `[E7]` then means "ran pytest, and it failed with X", not two half-records.
- Claude results attach by `tool_use_id`.
- Codex results attach by `call_id`, or by `item_completed` in Codex's newer "code mode", where one `exec` call wraps several commands. Those commands are folded into the enclosing event with their exit codes.

## Diff base: `--base auto`
- The default base is the parent of the first commit (by committer date) made between the session's start and 10 minutes after its last record, else `HEAD`. This catches agents that commit mid-session. Audit round 18 found the window had no end, so a commit made weeks after a session could become its base; it is now bounded, and `tests/test_transcripts.py` covers it. The diff is against the current worktree, so `--base` or `--diff-file` is safer for old sessions.
- `--diff-file` overrides the base.
- With no repo at all, readback falls back to the patches recorded in the transcript (`Edit` structured patches, `apply_patch`, `FileChange`).

## Citations are validated, then repaired once
- Every answer is checked for unknown ids and for factual lines without a valid citation. A line whose only ids are unknown counts as uncited (audit round 19 found it had counted as cited, which inflated the printed coverage).
- If coverage is under 90% or an id is unknown, one repair pass asks the model to cite or drop claims.
- Ids that are still unknown are stripped.
- The coverage figure is printed with every answer.

## Style limits are part of the prompt
Default line limits are 22 for overview (4 sections), 20 for walkthrough, 10 bullets plus a diagram for mechanism, and 12 for ask. Since v3, a fit-to-screen pass also shortens any answer longer than 48 rows × 120 columns. The prompts ban filler, restating the task and generic advice, and ask for concrete identifiers, values, exit codes and input-to-output flow. The goal is an answer a reviewer reads in under a minute.

## Backend auto-detection order: `READBACK_CMD`, `claude` CLI, `codex` CLI, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`

`READBACK_CMD` comes first. Setting it is an explicit choice, and the fresh-user test showed that leaving it after the CLIs surprised users who also had a signed-out `claude` on PATH.
- CLIs come first because people running coding agents usually already have one signed in, and it needs no API key.
- No vendor is hardcoded. `--backend`, `READBACK_BACKEND` and `READBACK_CMD` (any command that reads stdin) cover other providers.
- The Anthropic default model is `claude-sonnet-5-5`. The OpenAI-compatible backend requires an explicit model, because the endpoint may not be OpenAI's.

## Web view security
- It binds to `127.0.0.1`.
- POSTs need an `X-Readback: 1` header. A custom header forces a CORS preflight, which the server never approves, so other sites cannot spend the user's tokens.
- The Host header must be local, which blocks DNS rebinding.

## Eval design
- **Sessions:** six sessions were recorded from real agents (three `claude -p`, three `codex exec`) on six MIT-licensed repos: humanize, escape-html, more-itertools, python-tabulate, pretty-bytes and ms.
- **Isolation:** sessions ran in sandbox copies, with each agent's own OS sandbox. Claude used its bubblewrap bash sandbox with an allowlist of test commands; Codex used `workspace-write`. Running cloned code directly on the host was blocked by the session's safety classifier, and agent-side sandboxing is the safer method anyway.
- **No installs:** no dependencies were installed from the network for the sandboxes. The Python repos used a shared venv containing only pytest, and the JS repos used Node's built-in test runner.
- **s05 rerun:** the first s05 attempt ended early. It was rerun with an explicit non-interactive instruction; part of it is shortened in the committed copy. Both facts are in `eval/sessions/s05/meta.json`.
- **Questions:** a separate subagent wrote them from the raw transcript and diff only, without access to readback's output.
- **Explainer notes:** the overview, walkthrough and mechanism notes were generated once per session, with no knowledge of the questions.
- **Budget:** both conditions get the same context budget. The baseline is the raw transcript rendered as plain text plus the raw diff, cut deterministically: the diff first (up to 40%), then the head and tail of the transcript. The full raw transcript is reported too, as a ceiling.
- **Answering and grading:** a fresh `claude -p` with no tools answers. A separate fresh judge grades against the key without seeing the condition.

## Disclosure: the eval agents saw the owner's settings
The audits found two eval transcripts with an agent sentence that echoed a workflow preference from the owner's global instructions. Round 2 found s03; round 5 found s01. A sweep of all six transcripts for workflow terms found no others.
- **Removed at HEAD:** both sentences, their paraphrases in the recorded results, and the s03 question about its sentence. Since audit round 11 they are removed without a marker, because a marker's neighbours hinted at the topic. The sanitizer now flags both kinds of remark.
- **s03 in history:** every unpushed commit was rewritten so none contains the s03 sentence.
- **s01 in history:** the s01 sentence remains in every commit before the HEAD redaction, including the two already pushed to the private repo (`af5bd0f`, `a23145f`).
- **Fix:** recreating the repo from a single commit built from HEAD (`RELEASE.md` step 1) removes both.
  - The Dependabot PR refs (`refs/pull/1/head` → `0d15c10`, `refs/pull/2/head` → `ffd92cb`, both children of `a23145f`) keep those commits reachable, and a force-push cannot delete them.
  - Removing the sentence means recreating the repo from clean history, or asking GitHub Support to purge the refs.
  - That is the owner's decision; `RELEASE.md` step 1 has the commands.
- **Sanitizer:** `sanitize.py --check` now flags this kind of remark.

## Private privacy patterns live outside the repo
Earlier versions stored the owner's identifiers and private markers in the repo, rot13-encoded. Audit round 6 rightly objected that anyone can decode rot13.
- **Now:** `eval/scripts/sanitize.py` and `scripts/verify.sh` hold only generic patterns: foreign home paths, real email addresses, tokens and account ids.
- **Private patterns:** names, domains, machines, tools and instruction phrases are read from an untracked file, `.work/private-patterns.txt` (override with `READBACK_PRIVATE_PATTERNS`).
- **Without that file:** both tools say so and run the generic checks only.

## Transcript sanitizing for committed eval sessions
- `eval/scripts/sanitize.py` uses an allowlist. It keeps conversation records and drops account ids, API request blobs, injected instructions and memory, environment context and encrypted reasoning.
- It rewrites paths and identities.
- `--check` fails on any forbidden pattern: generic ones in the script, plus owner-specific ones from the untracked private pattern file (see above).
