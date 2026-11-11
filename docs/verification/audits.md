# Adversarial audits: summary

Each round used a fresh agent with no context. It audited `VERIFICATION.md` against the repo, the project criteria and the OSS release standard. Every gap was fixed before the next round.

The raw reports quoted private details while describing leaks, so this summary replaces them. Only generic descriptions are used here. The final round's report is `audit.md`.

| round | verdict | gaps |
|---|---|---|
| 1 | FAIL | 8 |
| 2 | FAIL | 6 |
| 3 | FAIL | 2 |
| 4 | FAIL | 1 |
| 5 | FAIL | 2 |
| 6 | FAIL | 5 |
| 7 | FAIL | 4 |
| 8 | FAIL | 4 |
| 9 | FAIL | 1 |
| 10 | FAIL | 1 |
| 11 | FAIL | 3 |
| 12 | FAIL | 2 |
| 13 | FAIL | 2 |
| 14 | FAIL | 3 |
| 15 | FAIL | 3 |
| 16 | FAIL | 2 |
| 17 | FAIL | 2 |
| 18 | FAIL | 1 |
| 19 | FAIL | 2 |
| 20 | FAIL | 2 |
| 21 | FAIL | 1 |
| 22 | FAIL | 1 |

## Round 1 (8 gaps)
1. **Privacy grep hit its own report.** `verify.sh`'s privacy grep matched a line of `VERIFICATION.md`, and the stated file count was stale. *Fixed:* the identifiers were removed from `VERIFICATION.md` and the count no longer appears.
2. **"One screen" was overstated.** *Fixed:* the claim was measured (`eval/scripts/measure_length.py`), and a fit-to-screen pass now enforces it (`explain.py`, tested).
3. **No evidence for the mechanism re-check, and the prompt changed after the eval.** *Fixed:* eval v3 was re-run on the shipped design.
4. **Losses were understated.** *Fixed:* exact per-session counts are in `docs/eval.md`.
5. **README overclaims** ("nothing else is sent", "every claim cites"). *Fixed:* the Mermaid CDN is disclosed, and the claim is now measured citation coverage.
6. **No artifact for the README render check.** *Fixed:* `assets/src/render_readme.py` plus screenshots.
7. **Stale CI and audit entries.** *Fixed.*
8. **The read-only test missed Codex, CLI `watch`, the web page and a stat-dirty file.**
   - *Fixed:* all four are now covered.
   - **This found a real bug:** `git diff` rewrote `.git/index` even with `--no-optional-locks`. It now runs against a throwaway index copy, and a mutation check shows the test catches the regression.

## Round 2 (6 gaps)
1. **The owner's identifiers were in unpushed history.** *Fixed:* history rewritten, and `verify.sh` gained a history scan.
2. **Eval transcript s03 echoed one of the owner's workflow preferences.** *Fixed:* redacted, disclosed in `docs/eval.md` and `DECISIONS.md`, and the question that relied on it replaced.
3. **API-key backends were never run.** *Fixed:* a stub-server test was added (`tests/test_backends.py`), and the docs state they are untested against the live APIs.
4. **Test count was wrong.** *Fixed.*
5. **The live-lag claim was unsupported.** *Fixed:* measured lag per event in `docs/verification/live-tail.md` (max 5.2 s).
6. **BLOCKED.md left out code changes and the OS claim was too broad.** *Fixed.*

## Round 3 (2 gaps)
1. **The s03 remark was still in history, and the PR refs block a force-push.**
   - *Fixed:* every unpushed commit was rewritten.
   - The pushed commits need the owner to recreate the repo (BLOCKED.md #3, RELEASE.md step 1).
2. **Stale local-CI evidence.** *Fixed:* re-run on the final code commit.

## Round 4 (1 gap)
1. **The repo-recreation commands would have failed** because `origin` already existed. *Fixed:* `git remote remove origin` first, and the PR-ref commit ids were corrected.

## Round 5 (2 gaps)
1. **A second transcript (s01) echoed an owner workflow preference.** *Fixed:* redacted, disclosed and added to the sanitizer. All six transcripts were swept, and no others were found.
2. **`docs/eval.md` quoted the owner's notes.** *Fixed:* the quote was removed.

## Round 6 (5 gaps)
1. **Committed audit reports and `VERIFICATION.md` named private hosts, tools, apps and local projects.** *Fixed:* the raw reports were replaced by this summary, and `VERIFICATION.md` was reworded.
2. **Private patterns were stored rot13-encoded in the repo**, which anyone can decode. *Fixed:* they moved to an untracked local file; the repo keeps only generic patterns.
3. **Recorded results and disclosures still let a reader rebuild the s03 remark.** *Fixed:* whole lines and answers were redacted (scores unchanged), and the disclosures were made generic.
4. **`RELEASE.md` used a `gh` flag the installed version lacks.** *Fixed:* it now uses `gh api -X PATCH … -f visibility=public`.
5. **`RELEASE.md` described the history leak too narrowly.** *Fixed:* step 1 now covers every earlier private detail and rebuilds from HEAD.

## Round 7 (4 gaps)
1. **One line of `docs/eval.md` still restated a private workflow rule.** *Fixed:* made generic.
2. **The round 6 report restated private details.** *Fixed:* folded into this summary.
3. **The `codex` backend is not tool-less.** `codex exec` always provides a shell, read-only here, so the model could read local files.
   - *Hardened:* the backend now ignores user config and rules, disables memories, apps and browser/computer use, and tells the model not to run commands.
   - *Disclosed:* README, SECURITY.md, AGENTS.md, `docs/backends.md` and DECISIONS.md now say so instead of claiming "no tools".
4. **A user-scope plugin install puts its descriptions (~120 tokens) into the executor's context too.** *Fixed:* the docs now recommend `claude --plugin-dir` in the explainer window only and disclose the cost of the user-scope install.

## Round 8 (4 gaps)
1. **The `codex` backend still loaded the user's global Codex instructions.** `--ignore-user-config` skips only `config.toml`. *Fixed:* a throwaway `CODEX_HOME` holding only a symlink to `auth.json`. Verified that no global instructions or memories are injected.
2. **Leftover "no tools" claims** in `SKILL.md` and `CHANGELOG.md`. *Fixed.*
3. **Private vulnerability reporting is not enabled.** *Fixed:* `SECURITY.md` has a fallback, and `RELEASE.md` adds the enabling command.
4. **The s05 disclosure implied what a private rule says.** *Fixed:* made generic.

## Round 9 (1 gap)
1. **Stale local-CI evidence:** round 8 had changed code after the documented container run. *Fixed:* re-ran it on the final code commit.

The round 9 notes were also addressed:
- third-party MIT notices for the code excerpts in the eval sessions (`eval/sessions/THIRD_PARTY_NOTICES.md`);
- stale references;
- a note in SECURITY.md on the Codex auth symlink.

## Round 10 (1 gap)
1. **The s05 rerun prompt, read with the disclosure, let a reader infer a private rule.** *Fixed:* the clause is shortened in the committed copies (marked), and the docs no longer attribute s05's early stop to the owner's configuration. No question or score depends on it. The phrase is now in the local private pattern file.

Notes also fixed: round count, SECURITY fallback issue type, the exact command in `ci-local.md`.

## Round 11 (3 gaps)
1. **Redaction markers had topical neighbours.** In two eval transcripts and their recorded results, the marker sat beside a sentence that, read with the disclosure, hinted at what the removed remark was about. *Fixed:* the markers are removed outright, so no position is visible, and the disclosures no longer say where in the transcript the sentence was.
2. **"Every claim cited" survived** in the plugin manifest and CHANGELOG. *Fixed:* measured wording, also in `AGENTS.md` and the architecture diagram label.
3. **The README quickstart broke in zsh** (macOS default), which does not word-split an unquoted `$S`. *Fixed:* a shell function with `"$@"`, re-checked under bash and dash.

Notes also fixed: the README budget line now says one answer can take up to three model calls, and `docs/plugin.md` says readback reads (never writes) the executor's transcript.

## Round 12 (2 gaps)
1. **Recorded note metadata did not match the redacted note text.** Two stored `cited` lists still held an id whose line had been removed, a few stored coverage values were computed before redaction, and one length-table cell was off by one. *Fixed:* `cited` and coverage were recomputed from the stored text with `citations.check`, and the length table was regenerated with `measure_length.py`. The published coverage minimum is now 90.0% (was 90.5%); the mean is unchanged at 97.5%. Accuracy scores are unaffected.
2. **`docs/usage.md` gave the wrong default `overview` length** (18, the code says 22). *Fixed.*

Notes also fixed: README wording on when the repair runs, what each extra call sends, and `READBACK_CMD`; `AGENTS.md` now acknowledges the sanitized eval transcripts.

## Round 13 (2 gaps)
1. **`docs/architecture.md` embedded a diagram file that does not exist.** *Fixed:* it now uses the light/dark `<picture>` block, like the README.
2. **The "generic" email patterns listed one uncommon top-level domain**, which, read with other files, hinted at a private domain. *Fixed:* both `scripts/verify.sh` and `eval/scripts/sanitize.py` now match any 2–6 letter TLD, with one exclusion for `@pytest.` decorators in JSON-escaped transcripts. Because this changed scripts, the local container CI was re-run on the new commit (`ci-local.md`).

Notes also fixed: `watch` delta notes are not repaired (README), the fit-to-screen pass keeps the original if shortening loses coverage (VERIFICATION), the CONTRIBUTING test table, the SECURITY wording on Codex's `auth.json` refresh, and the tested Codex CLI version (`docs/backends.md`).

## Round 14 (3 gaps)
1. **The README render screenshots were stale.** *Fixed:* re-rendered from the current README with `assets/src/render_readme.py`.
2. **The plugin's context cost was understated** (~120 tokens counted only the skill). *Fixed:* Claude Code's own estimate (~177 tokens) is recorded in `docs/verification/plugin.md`, and the docs say about 180.
3. **The live-tail evidence misstated when the delta explanation arrived.** The threshold is checked once per poll, so it came after E10, not after exactly 6 events. *Fixed* in `live-tail.md` and VERIFICATION.

Notes also fixed: `docs/backends.md` mentions the repair and shorten calls, `docs/architecture.md` mentions backend temp dirs, and the CONTRIBUTING test table lists the shortening test.

## Round 15 (3 gaps)
1. **The README live screenshot still said the delta came "after 6 new events".** *Fixed:* `assets/src/live.html` now says "after ≥6 new events, here E10", and `docs/img/live.png` was re-rendered.
2. **`docs/eval.md` explained raw's ties and wins with session sizes its data contradicts.** *Fixed:* the measured size of each session is listed, and the text no longer claims that size explains s06.
3. **The README's coverage figure was a per-note mean presented as a share of lines.** *Fixed:* the README now gives the pooled figure (330 of 340 factual lines, 97.1%); `docs/eval.md` and VERIFICATION give both.

## Round 16 (2 gaps)
1. **The `codex` backend's model still had a shell and a working web tool**, despite the docs saying "read-only shell, no network". A planted instruction in a transcript could have made it read local files and send them to a URL. *Fixed in code:* `CodexCLI` now passes `-c web_search="disabled"` and disables every tool-providing Codex feature (`CODEX_DISABLED_FEATURES`). A probe found every shell, web, patch and agent-spawn attempt fails, while a control with the old flags succeeded (`docs/verification/backends.md`). Every doc statement about the backend was corrected, and the reliance on Codex feature flags is disclosed. Local container CI was re-run on the new code commit.
2. **`docs/eval.md` said s04 is worst "except raw@full"**, but it is lowest there too. *Fixed.*

Notes also fixed: the `prompts.py` docstring no longer says every claim is cited, and SKILL.md's `watch` example has `--duration`.

## Round 17 (2 gaps)
1. **A Codex session could not be picked by an id prefix**, though the docs promise `-s <id-prefix>`: Codex files are named `rollout-<timestamp>-<uuid>.jsonl` and `resolve()` matched only the start or end of the name. *Fixed in code:* the trailing uuid is matched by prefix, with assertions in `test_codex_classic_and_code_mode_calls`; a mutation check shows they fail without the fix.
2. **`docs/backends.md` still showed the pre-round-16 `codex exec` command.** *Fixed:* the block is generated from `CODEX_DISABLED_FEATURES`.

Notes also fixed: `--duration` and the "at least N events" wording in `docs/usage.md`, and the Codex and citation wording in `AGENTS.md`. The round 16 auditor's probe directory was moved out of the tree.

## Round 18 (1 gap)
1. **`--base auto` searched for commits with no end time.** The first commit on HEAD after the session started became the base's child, even one made weeks later by someone else, so a finished session could be explained with hunks the agent never wrote. *Fixed in code:* `auto_base` now limits the search to the session window (start to 10 minutes after the last record), with assertions for a post-session commit and for a session that committed nothing (a mutation check fails without the bound). The docs and `--base` help now describe the window and say the diff is against the current worktree.

Notes also fixed: the s03 question-type table and the provenance of its replacement q10 (`eval/sessions/QUESTIONS_README.md`).

## Round 19 (2 gaps)
1. **Printed coverage could be too high.** A line whose only citations were unknown ids counted as cited, so an answer with 1 of 3 lines validly cited could report 100%. The same figure decided whether a repair or a shortened answer was kept. *Fixed in code:* `citations.check` counts a line as cited only if one of its ids is valid; the test covers it, and a mutation check fails without the fix. Stored eval coverage is unchanged (no stored note had unknown ids).
2. **"Never touched" did not hold for repos using git's split index**: git refreshes the mtime of `.git/sharedindex.*` whenever it reads the index. Reproduced here; it cannot be configured away. *Disclosed* in README, SECURITY.md, DECISIONS, the read-only test docstring and VERIFICATION row 4. Every git call now also passes `-c core.fsmonitor=false`, so a repo's config cannot make git start an fsmonitor command.

## Round 20 (2 gaps)
1. **`git diff` ran the repo's filters and diff drivers**, so a changed git-lfs file made git store an object under `.git/lfs/objects/`, and a `cachetextconv` driver wrote `refs/notes/textconv/*` (and showed converted text instead of real bytes). *Fixed in code:* `--no-textconv` on `git diff` and git-lfs's clean filter unset on every git call. The read-only fixture gained a cachetextconv driver (removing the flag fails the test), and a container probe with a control shows the LFS fix. Custom non-LFS clean filters cannot be disabled by wildcard, so they are a disclosed exception.
2. **Same-size edits made in the second of the last index write could vanish from the diff**, because the throwaway index copy got a fresh mtime that defeated git's racy-entry check. *Fixed in code:* `shutil.copy2` keeps the mtime, and a regression assertion failed 3 of 3 runs without the fix.

## Round 21 (1 gap)
1. **A repo hook could write into the observed worktree:** writing readback's throwaway index still ran the repo's `post-index-change` hook. *Fixed in code:* every git call passes `-c core.hooksPath=/dev/null`; the read-only fixture has such a hook, and removing the override fails `tests/test_readonly.py`.

Note also fixed: VERIFICATION row 4 says `web` is exercised through its server, not the CLI.

## Round 22 (1 gap, last full round)
1. **Untracked symlinks were followed**, so a link to a file outside the worktree put that file's contents into the evidence pack sent to the backend, and a link to `/dev/zero` read without end. *Fixed in code:* untracked paths are `lstat`ed, symlinks are rendered as their link text (as git does), non-regular files are skipped, and regular files are opened with `O_NOFOLLOW`. The fixture has an outside-pointing link; following it fails the test (mutation check). Disclosed in SECURITY.md.

Notes also fixed: the README's "latest session" comment, and a DECISIONS line reworded as a project goal.

**Convergence decision:** rounds 11–22 each found 1–3 gaps, moving from core claims to rarer configurations. Round 22 was declared the last full round. Its one gap was fixed and re-checked narrowly (the targeted test, a mutation check, a probe, and local container CI) instead of starting round 23. The remaining notes in the round 22 report are non-blocking hardening ideas.

## Earlier history
Commits before the final ones still contain some of the details removed above. `scripts/verify.sh` checks that HEAD is clean and reports how many earlier commits are affected. The published history must be rebuilt from HEAD (RELEASE.md step 1) before the repo goes public.
