# Comprehension eval

**Question:** if you read readback's explanation, do you understand what the agent did better than if you read the raw transcript and diff, given the same reading budget?

**Answer:** yes, at both budgets tested, with the shipped design (v3):
- **2,000 tokens:** readback scores **74.6% vs 54.2%**.
- **6,000 tokens:** readback scores **85.0% vs 80.0%**.

Each cell is 120 graded answers. Reading the *entire* raw transcript and diff scores 97.9%, but costs about 5× the tokens of the 6,000 budget and about 12× the 2,000 one. So readback is a compression tool, not a replacement for the full record: it wins when reading time or context is limited.

Everything below can be reproduced with `uv run python eval/run_eval.py --reps 2 && python eval/summarize.py`. Every answer and every grade is in `eval/results/`.

## Setup

**Sessions.** Six real agent runs, recorded for this eval in sandbox copies of small MIT-licensed repos (`eval/sessions/sNN/`: sanitized transcript, final diff, task, `meta.json`):

| id | agent | model | repo | task | events |
|---|---|---|---|---|---|
| s01 | Claude Code (`claude -p`) | claude-opus-5-5 | python-humanize | `intword(compact=True)` with K/M/B/T suffixes and rounding carry | 18 |
| s02 | Codex (`codex exec`) | gpt-6.1-sol | escape-html | `unescape()` with numeric entities and invalid code points | 9 |
| s03 | Claude Code | claude-opus-5-5 | more-itertools | `default=` for `argmin` / `argmax` without duplicated logic | 20 |
| s04 | Codex | gpt-6.1-sol | python-tabulate | new `dokuwiki` table format with alignment and escaping | 20 |
| s05 | Claude Code | claude-opus-5-5 | pretty-bytes | `roundingMode` option; the spec contradicted the code | 38 |
| s06 | Codex | gpt-6.1-terra | ms | compound durations (`"1h 30m"`) in `parse` | 9 |

**Contamination from the owner's settings, disclosed:** the recording agents ran under the owner's own CLI accounts.
- **Claude:** Claude Code loaded the owner's global instructions despite `--setting-sources project`. The s01 and s03 transcripts each contained one sentence echoing one of the owner's workflow preferences. Both sentences, and their paraphrases in the recorded results, were removed without a marker, so their position reveals nothing, and s03's q10, which asked about its sentence, was replaced for future runs (no s01 question depended on its sentence). Scores recorded in v1–v3 graded the original q10.
- **Codex:** the s04 and s06 agents searched the owner's Codex memory file (only the path is visible; no content). Those commands remain in the transcripts.

Agents ran inside their own OS sandboxes: Claude Code's bubblewrap bash sandbox with an allowlist of test commands, and Codex `workspace-write`. Nothing was installed from the network; Python repos used a venv with only pytest, and JS repos used Node's built-in test runner. s05's first attempt ended early and was rerun with a non-interactive instruction appended to the task. Part of that instruction is shortened in the committed copy; no question depends on it (recorded in its `meta.json`).

**Questions.** 10 per session, 60 in total (`questions.json`), written by a separate agent from the raw transcript and diff only, with an answer key, the key facts required, and the evidence location. The mix covers what/where, how (mechanism), test (what a test asserts), failure/sequence, and why (stated reasons, spec conflicts). See `eval/sessions/QUESTIONS_README.md`.

**Conditions.** For each session and budget B:
- `explainer@B` gets readback's `overview` + `walkthrough` + `mechanism`, generated once per session with no knowledge of the questions (the explainer prompt contains only the transcript and diff). Any remaining budget is filled with readback's evidence pack.
- `raw@B` gets the raw transcript rendered as plain text (every message, tool input and tool output, untrimmed) plus the raw diff, cut deterministically: the diff first (up to 40% of B), then the head and tail of the transcript.
- `raw@full` gets the whole raw transcript and diff with no limit (the ceiling).

**Answering and grading.** A fresh `claude -p --model claude-sonnet-5-5` (no tools, no session persistence, nothing but the material and the questions) answers all 10 questions. A second fresh `claude -p` grades each answer against the key without seeing the condition: 1 correct, 0.5 partial, 0 wrong or "unknown". Each condition is run twice (`--reps 2`).

**Explainer model.** `readback` with the `claude` backend (the CLI's default model, claude-opus-5-5 at the time), `--budget 40000`, with the citation repair pass and (v3) the fit-to-screen pass on.

## Results (v3, the shipped design)

### Overall

| condition | budget (tokens) | accuracy | per-rep accuracy | answerer input tokens (mean) | n questions |
|---|---|---|---|---|---|
| explainer | 2000 | **74.6%** | 75.8% / 73.3% | 4,674 | 120 |
| raw | 2000 | **54.2%** | 53.3% / 55.0% | 4,848 | 120 |
| explainer | 6000 | **85.0%** | 84.2% / 85.8% | 10,725 | 120 |
| raw | 6000 | **80.0%** | 79.2% / 80.8% | 12,365 | 120 |
| raw | full (no limit) | **97.9%** | 96.7% / 99.2% | 56,631 | 120 |

### Per session (score out of 10, mean over repetitions)

| session | explainer@2000 | raw@2000 | explainer@6000 | raw@6000 | raw@full |
|---|---|---|---|---|---|
| s01 | 8.50 | 5.75 | 9.00 | 9.75 | 10.00 |
| s02 | 8.00 | 4.50 | 9.50 | 7.75 | 9.75 |
| s03 | 8.00 | 8.00 | 9.50 | 10.00 | 10.00 |
| s04 | 5.25 | 2.75 | 5.75 | 5.25 | 9.25 |
| s05 | 7.50 | 3.25 | 7.75 | 5.50 | 10.00 |
| s06 | 7.50 | 8.25 | 9.50 | 9.75 | 9.75 |

### One-time explainer cost (overview + walkthrough + mechanism, incl. repair passes)

| session | tokens in+out |
|---|---|
| s01 | 45,875 |
| s02 | 25,720 |
| s03 | 48,862 |
| s04 | 65,946 |
| s05 | 71,427 |
| s06 | 27,318 |

The budget is the size of the material (chars / 4). "Answerer input tokens" is what the answering model actually consumed, including the questions and the CLI's own overhead.

**Raw conditions** (`raw@2000`, `raw@6000`, `raw@full`) do not depend on readback's design. The v3 tables reuse the v2 raw runs, copied into `eval/results/v3/`. Only the explainer conditions were re-run for v3.

**Citation coverage of the v3 notes:** a valid citation on 90.0–100% of factual lines per note, mean 97.5% per note; pooled over all 340 factual lines, 330 (97.1%) are cited (repair threshold 90%).

**Length of the v3 notes**, measured with `python eval/scripts/measure_length.py eval/results/v3`. "One screen" is a 48-row, 120-column terminal, enforced by the fit-to-screen pass.

| mode | non-blank lines (min–max) | rows @120 (min–max) | rows @80 (min–max) |
|---|---|---|---|
| overview | 23–31 | 35–40 | 47–55 |
| walkthrough | 20–25 | 32–39 | 42–53 |
| mechanism | 27–34 | 35–46 | 42–59 |

At 80 columns the notes wrap to 42–59 rows, so they do not fit one 80×48 screen.

## Iteration history (reported honestly)

**v1** used the first design. The explainer won at both budgets, but s04 scored low.

### Overall (v1)

| condition | budget (tokens) | accuracy | per-rep accuracy | answerer input tokens (mean) | n questions |
|---|---|---|---|---|---|
| explainer | 2000 | **76.7%** | 76.7% | 4,672 | 60 |
| raw | 2000 | **53.3%** | 53.3% | 4,848 | 60 |
| explainer | 6000 | **88.3%** | 88.3% | 10,668 | 60 |
| raw | 6000 | **79.2%** | 79.2% | 12,365 | 60 |
| raw | full (no limit) | **92.5%** | 92.5% | 56,630 | 60 |

Diagnosing s04's misses found a **parser bug**. In Codex's newer "code mode", one `exec` call can run a web search plus shell commands. readback replaced the JS source with the shell commands and dropped the script output, so the agent's DokuWiki research was invisible. In v1, two of s04's three zero-score answers at 6,000 tokens were about that research and the lint sequence that followed.

**v2** changed two things:
1. The Codex parser keeps non-shell tool calls from code mode (e.g. `web__run(...)`) and their script output. A regression case was added to `tests/test_transcripts.py`.
2. `overview` gained a **Tests** section (each new test: inputs and assertions), because knowing what the new tests check, and how, is central to reviewing an agent's change.

Effect: the 2,000-token gap held (+22.0 points in v2 vs +23.4 in v1). The 6,000-token gap shrank from +9.1 to +5.4. The `raw@full` ceiling also moved, from 92.5% to 97.9%, with identical inputs. So run-to-run variance of the answerer and judge is several points, and the 6,000-token difference should be read as "modestly better", not as a precise number.

**v3** added a **fit-to-screen pass**.

*Why:* the final audit measured the v2 notes against the one-screen goal. Wrapped at 120 columns, mechanism reached 59 rows and overview up to 46:

| mode | non-blank lines (min–max) | rows @120 (min–max) | rows @80 (min–max) |
|---|---|---|---|
| overview | 23–31 | 34–46 | 44–57 |
| walkthrough | 15–30 | 29–43 | 38–59 |
| mechanism | 31–48 | 40–59 | 56–75 |

*The change:* if an answer exceeds 48 rows at 120 columns, one extra call shortens it. The shortened version must keep at least 90% citation coverage, otherwise the original is kept. A test covers this (`tests/test_citations.py::test_answers_longer_than_a_screen_are_shortened`). The mechanism prompt also now asks for single-level, one-line bullets.

*Effect:*
- All v3 notes fit (max 46 rows).
- Explainer accuracy dropped slightly: 76.2% → 74.6% at 2k and 85.4% → 85.0% at 6k. Both are within run-to-run noise.
- One-time explainer cost fell by about 30%.

#### v2 overall

| condition | budget (tokens) | accuracy | per-rep accuracy | answerer input tokens (mean) | n questions |
|---|---|---|---|---|---|
| explainer | 2000 | **76.2%** | 76.7% / 75.8% | 4,758 | 120 |
| raw | 2000 | **54.2%** | 53.3% / 55.0% | 4,848 | 120 |
| explainer | 6000 | **85.4%** | 85.8% / 85.0% | 11,049 | 120 |
| raw | 6000 | **80.0%** | 79.2% / 80.8% | 12,365 | 120 |
| raw | full (no limit) | **97.9%** | 96.7% / 99.2% | 56,631 | 120 |



## Where the explainer still loses points

**Sessions where raw ties or wins** (v3, mean of 2 runs):
- At 6,000 tokens raw is as good or better in **3 of 6** sessions: s01 (9.75 vs 9.00), s03 (10.00 vs 9.50) and s06 (9.75 vs 9.50).
- At 2,000 tokens raw ties or wins in **2 of 6**: s03 (8.00 vs 8.00) and s06 (8.25 vs 7.50).
- **Session size** (full raw material, chars / 4, from `raw_context(sdir, None)` in `eval/run_eval.py`): s01 6.8k, s03 7.0k, s02 14.3k, s06 16.9k, s05 26.6k, s04 113k tokens.
  - s01 and s03 are short: 6,000 tokens holds about 87% of them, so raw loses little.
  - s06 is not short (6,000 tokens holds about a third), yet raw still ties or wins. Size does not explain it; one untested guess is that its single, linear change survives the head-and-tail cut.
  - readback's clearest wins are s02 (14.3k), s05 (26.6k) and s04 (113k).

**Detail-heavy questions** cost points: the exact inputs of a test loop, the second assertion of a test, the exit code of a sandbox failure. At small budgets the evidence pack is cut hard, and the notes do not enumerate every assertion. s04 (12 lint and patch rounds) is the lowest-scoring session in every condition, including raw@full (9.25 vs 9.75–10.00 for the others).

**Cost:** generating the three notes costs 26k–71k model tokens per session (v3), once per session. The answering side is cheaper: 10.7k vs 12.4k input tokens at the 6,000 budget, and 10.7k vs 57k against reading everything.

## Threats to validity

- Six sessions and 60 questions is small. Sessions are short (9–38 events); long multi-hour sessions are untested.
- One model family answers and grades (Claude Sonnet 5.5); the explainer is Claude Opus 5.5. The questions were written by a Claude agent.
- The raw baseline's truncation (diff first, then head and tail of the transcript) is one reasonable choice, not the only one.
- The agents ran with the owner's global CLI configuration, which influenced their behaviour in small ways (see Setup).
- Agent "thinking" text was empty in all six transcripts, so "why" questions rely on the agents' visible messages.
