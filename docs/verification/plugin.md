# Claude Code plugin, end to end

readback was installed into an isolated venv (`uv pip install .`) and put on PATH. Claude Code then loaded the plugin from the checkout with `--plugin-dir`. Both slash commands ran in a fresh `claude -p` session; there were no permission denials and the output was relayed verbatim.

## `/agent-readback:readback events -s eval/sessions/s06/transcript.jsonl --diff-file eval/sessions/s06/diff.patch`

```
is_error= False turns= 2 permission_denials= 0
codex 01a1ab92-0b4a-72f2-a35d-f983bb3d26f7 · 9 events · 3 hunks (file)
   E1 user         Extend `parse` in src/index.ts to accept compound durations such as "1h 30m", "2d3h", "1 …
   E2 assistant    I’ll inspect the existing parser and its tests first, then add compound parsing while pre…
   E3 exec_command ! $ rg -n 'agent-readback|compound duration' /home/user/.codex/memories/MEMORY.md -> exit 1…
   E4 exec_command $ cat src/index.ts -> exit 0 $ git status --short && find .. -name AGENTS.md -print -> ex…
   E5 assistant    The existing parser already defines the accepted number and unit forms. I’m keeping that …
   E6 apply_patch  apply_patch src/index.ts
   E7 apply_patch  apply_patch src/compound.test.ts, README.md
   E8 exec_command $ node --version && if [ -x node_modules/.bin/tsc ]; then node_modules/.bin/tsc --noEmit;…
   E9 assistant    `parse` now sums compound durations such as `1h 30m`, `2d3h`, and `1.5h 10s`. It rejects …
   H1 README.md @@ -154,10 +154,19 @@ As of `v3.0`, you can import `parse` a (+9 -0)
   H2 src/compound.test.ts @@ -0,0 +1,31 @@ (+31 -0)
   H3 src/index.ts @@ -80,7 +80,27 @@ export function parse(str: string): numbe (+21 -1)
```

## `/agent-readback:readback ask -s … why does a single-part input skip the compound branch?`

```
False 2 0
[claude · 9 events · cites 5 · coverage 100% · 4995→687 tok · 15.9s]
A valid single-part input never reaches the compound code, because that code sits inside `if (!match?.groups)`. It runs only when the original single-value regex fails to match [H3].

- **Normal single inputs:** inputs like `1h`, `100` and `-.5 hr` match the existing regex, so `match.groups` is set. The function then continues to the original conversion code below the branch, which is unchanged [H3, H2].
- **Agent's stated intent:** the agent said it was "keeping that single-unit path intact" and adding the compound check alongside it [E5].
- **Single-part input that fails the old regex:** it does enter the loop. After one component, `count` is 1, so `return count > 1 ? total : NaN` returns `NaN`. This keeps the old rejection behaviour [H3].
- **Trailing space:** `'1s '` is rejected by `if (offset === str.length && str.endsWith(' ')) return NaN`. The test asserts it is `NaN` [H3, H2].
- **Recursion:** each compound part is converted by calling `parse(component[0])`. That call is a single-part string, so it matches the original regex and never re-enters the compound branch [H3].
- **Tests:** `src/compound.test.ts` includes a "preserves single-value parsing" test, and `node --test src/compound.test.ts` exited 0 [H2, E8].
- **Not shown:** the full original single-value regex was truncated in the `cat src/index.ts` output [E4]. Type checking was not run because `tsc` is not installed [E8].

```

Plugin manifest validation:

```
✔ Validation passed with warnings
```

## Context cost of a user-scope install

Claude Code's own estimate, run from the repo root (Claude Code 2.1.318):

```
$ claude --plugin-dir . plugin details agent-readback
...
Projected token cost
  Always-on:   ~177 tok   added to every session

Per-component (rounded)
  component  always-on  on-invoke
  readback        ~120       ~670
  readback         ~60       ~350
```

The two `readback` rows are the skill and the slash command (Claude Code lists both as skills). The docs round this to "about 180 tokens". With `--plugin-dir` in the explainer window only, the executor's session pays none of it.
