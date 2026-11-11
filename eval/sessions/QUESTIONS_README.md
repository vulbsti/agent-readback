# Comprehension questions (`sN/questions.json`)

Each session has 10 questions. Claude (Opus 5.5) wrote them from the raw `transcript.jsonl` and `diff.patch` only, before any explainer output existed. The one exception is s03's q10, replaced during audit round 2 because the original relied on a redacted remark: the replacement was written later, from the transcript only, and no recorded score uses it (v1–v3 graded the original). It did not run any `readback` command or read anything under `src/`, so the questions do not depend on the tool being benchmarked. Transcripts were pretty-printed with a throwaway python3 script that only renders the JSONL records.

Rules: every answer can be checked against a transcript line (1-based JSONL line) and/or a diff file plus `@@` header, given in `evidence`. No question can be answered from `task.md` alone, and none are yes/no. Questions cover early, middle and late events. `accept` lists the facts a correct answer must contain and any acceptable variants.

| session | what | where | how | why | test | failure | sequence |
|---|---|---|---|---|---|---|---|
| s01 humanize (claude) | 1 | 1 | 3 | 1 | 2 | 1 | 1 |
| s02 escape-html (codex) | 1 | 1 | 3 | 1 | 2 | 1 | 1 |
| s03 more-itertools (claude) | 2 | 0 | 2 | 1 | 2 | 1 | 2 |
| s04 tabulate (codex) | 1 | 1 | 2 | 1 | 1 | 2 | 2 |
| s05 pretty-bytes (claude) | 2 | 0 | 2 | 2 | 1 | 2 | 1 |
| s06 ms (codex) | 1 | 1 | 3 | 1 | 2 | 1 | 1 |
