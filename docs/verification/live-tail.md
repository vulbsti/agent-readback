# Live tailing a running Claude Code session

A `claude -p` agent was started in a sandbox with a fixed `--session-id`, and `readback watch --explain-every 6 --backend claude` was started on its transcript while the agent was still running. Timestamps were added by the shell. A cited delta explanation is produced once at least 6 new events have arrived since the last one; the threshold is checked once per poll, so here it came after E10, because E6–E10 arrived in one poll. Paths are shortened.

```
17:37:01 watching ~/.claude/projects/-sandbox-live1/56d60b05-461e-4844-a677-c7f122b9abb3.jsonl (Ctrl-C to stop)
17:37:01    E1 user         Add an optional second argument `options` to escapeHtml with a boolean `quotes` (default true). When
17:37:05    E2 Bash         $ ls -R | grep -v node_modules | head -50; cat package.json; git ls-files # List project files and p
17:37:08    E3 Read         index.js
17:37:19    E4 Bash         ! $ python3 - <<'EOF' p='index.js' s=open(p).read() s=s.replace("""var matchHtmlRegExp = /["'&<>]/ """
17:37:19    E5 Write        test/options.test.js 'use strict' var test
17:37:28    E6 assistant    Bash heredoc was blocked; I'll use Edit instead.
17:37:28    E7 Edit         index.js --- old var matchHtmlRegExp = /["
17:37:28    E8 Edit         index.js --- old * @return {string} * @pub
17:37:28    E9 Edit         index.js --- old case 34: // " escape = '&
17:37:28   E10 Edit         index.js --- old case 39: // ' escape = '&
17:37:36 
17:37:36 - Agent inspected the repo (`index.js`, `test/index.js`, `package.json`) and read `escapeHtml`'s char-code switch implementation [E2, E3].
17:37:36 - First edit attempt via Python heredoc in Bash was blocked ("Contains brace with quote character"); agent switched to the Edit tool [E4, E6].
17:37:36 - Added `matchHtmlNoQuotesRegExp = /[&<>]/`; `escapeHtml(string, options)` computes `quotes = !(options && options.quotes === false)` and picks the regex accordingly [E7, E8, H1, H2].
17:37:36 - In the switch, `case 34`/`case 39` now `continue` when `!quotes`, skipping `&quot;`/`&#39;` output [E9, E10, H3].
17:37:36 - Created `test/options.test.js` with 7 `node:test` cases: default/empty/true options, quotes false, mixed `&<>`, quotes-only, leading-quote edge cases [E5, H4].
17:37:36 - Requested `node --test test/options.test.js` has NOT been run yet; existing `test/index.js` suite also not run — correctness unverified [E1].
17:37:36 
17:37:37   E11 Bash         ! $ node --test test/options.test.js; ls node_modules/.bin/mocha 2>/dev/null && npx mocha test/ # Run 
17:37:42   E12 assistant    I added the `options` argument to `escapeHtml` and wrote tests for it. `node --test test/options.tes
```

## Lag between the agent's record and readback printing it

Each event's own timestamp in the transcript was compared with the second at which `watch` printed it (the shell timestamps above, 1 s resolution; `--interval 0.5`):

| event | agent record time | printed | lag (s) |
|---|---|---|---|
| E1 | 17:37:01.185 | 17:37:01 | ≈0 |
| E2 | 17:37:05.495 | 17:37:05 | ≈0 |
| E3 | 17:37:08.373 | 17:37:08 | ≈0 |
| E4 | 17:37:14.603 | 17:37:19 | 4.4 |
| E5 | 17:37:19.389 | 17:37:19 | ≈0 |
| E6 | 17:37:22.762 | 17:37:28 | 5.2 |
| E7 | 17:37:23.963 | 17:37:28 | 4.0 |
| E8 | 17:37:25.963 | 17:37:28 | 2.0 |
| E9 | 17:37:27.015 | 17:37:28 | 1.0 |
| E10 | 17:37:28.015 | 17:37:28 | ≈0 |
| E11 | 17:37:35.828 | 17:37:37 | 1.2 |
| E12 | 17:37:42.783 | 17:37:42 | ≈0 |

- **Result:** 7 of the 12 events printed within about a second; the largest lag was 5.2 s.
- **Likely cause of the multi-second lags:** they come in bursts (E6–E10 all printed in the same second, and E4 printed with E5). That pattern fits Claude Code appending several records to the file at once, not readback's polling, which runs every 0.5 s.
- **Not proven:** without file-write timestamps we cannot rule out readback contributing to the lag.
