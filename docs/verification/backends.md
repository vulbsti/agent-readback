# Backends exercised

| backend | where it was exercised |
|---|---|
| `claude` (`claude -p`, tools disabled) | the whole eval (`docs/eval.md`), `docs/verification/readonly-real-backend.md`, `plugin.md`, `demo.gif` |
| `codex` (`codex exec --sandbox read-only --ephemeral --ignore-user-config …`; web search and tool features disabled) | below |
| `command` (`READBACK_CMD`) | `docs/verification/fresh-user.md`; `tests/test_readonly.py` (a command that tries to write to its cwd) |
| `fake` | test suite |
| `anthropic`, `openai` | `tests/test_backends.py` runs both against a local stub server, checking auth headers, model, system prompt, the cache marker and reply/token parsing. Neither has been run against the live APIs (no keys on the build machine). |

## `readback overview --backend codex` on eval session s06 (hardened flags, see `docs/backends.md`)

```
$ readback overview -s eval/sessions/s06/transcript.jsonl --diff-file eval/sessions/s06/diff.patch --backend codex
**Changed**
- `src/index.ts:parse` falls back after single-value matching fails: sticky, case-insensitive component matching → recursive unit conversion → summed milliseconds. [E6, H3]
- Compound parsing requires multiple unit-bearing parts, consistent signs, and complete consumption; malformed parts, tabs, commas, and boundary spaces return `NaN`. [E6, H3]
- `README.md` documents compounds, negative signs, the 100-character limit, and using `parse` for compound TypeScript strings. [E7, H1]

**Why**
- The user requested compound durations while preserving single-unit behavior and the input limit, without installing dependencies. [E1]
- The agent retained the original single-unit path as the conversion source and added full-string validation to reject invalid components and mixed signs. [E5, H3]

**Tests**
- `sums compound durations…` checks spaced, adjacent, written-out, fractional, month/millisecond, and negative inputs against exact millisecond totals. [E7, H2]
- `rejects mixed signs…` checks conflicting signs, `+`, missing/unknown units, junk, commas, boundary spaces, and tabs; every result must be `NaN`. [E7, H2]
- `preserves single-value parsing…` checks unitless, fractional-negative, case-insensitive inputs, 100-character acceptance, overlength/empty throws, and trailing-space rejection. [E7, H2]
- `node --test src/compound.test.ts` exited `0`; the agent reported all three tests passed under Node `v26.9.0`. [E8, E9]
- `git diff --check` exited `0`; the compiler probe reported `TypeScript compiler not installed`, so type checking did not run. [E8]

**Risks**
- Running the existing test suites is not shown; single-unit compatibility evidence covers only the new regression assertions. [E8, H2]
- Compound-specific length boundaries and exhaustive unit aliases are not tested in the added file. [H2]
- The initial memory search exited `1`; subsequent repository inspection succeeded, but a matching memory result is not shown. [E3, E4]
- `StringValue` and `parseStrict` remain documented as single-value interfaces; compound TypeScript typing was not verified by a compiler. [E8, H1]

[codex · 9 events · cites 11 · coverage 100% · 19298→498 tok · 15.1s]
```

## Isolation probe: is the user's global configuration in the explainer's context?

The probe asks the model whether its context contains a heading that exists only in the build machine's global `~/.claude/CLAUDE.md`. The heading text is not reproduced here.

| run | flags | answer |
|---|---|---|
| readback's `claude` backend | `claude -p --tools "" --no-session-persistence --setting-sources "" --strict-mcp-config --system-prompt …` | **NO**: global instructions not loaded |
| control | `claude -p --tools "" --no-session-persistence` (defaults) | YES: the probe detects them when present |

For the `codex` backend, a run with readback's throwaway `CODEX_HOME` was inspected: its recorded prompt contained no global instructions and no memory block, only Codex's built-in system prompt and environment context.

## Tool probe for the `codex` backend (audit round 16)

Audit round 16 found that the earlier `codex` flags (memories, apps, browser and computer use disabled) still left the model a working shell and web tool. The backend now also passes `-c web_search="disabled"` and disables every tool-providing feature (`CODEX_DISABLED_FEATURES` in `src/agent_readback/backends.py`). Both probes below ran `codex exec` with readback's isolated `CODEX_HOME`, in a temp dir, with Codex CLI 0.166.0. The prompt demanded real attempts and had no "do not run commands" note.

**Current flags** (exactly `CODEX_DISABLED_FEATURES` plus the web-search override): every attempt failed, and no file appeared in the model's working directory.

| attempt | result |
|---|---|
| `ls /` via `functions.exec` | `code-mode host is disabled` |
| fetch `https://example.com` | `code-mode host is disabled` |
| `apply_patch` creating `probe.txt` | `code-mode host is disabled` |
| `collaboration.spawn_agent` running `ls /` | `collab spawn failed: … no rollout found for thread id …` (fails under `--ephemeral`) |

**Control, earlier flags:** the model listed the root directory with `ls /` and fetched `https://example.com` through Codex's web tool.

Codex still declares the tool names (`functions.exec`, `collaboration.*`). The block depends on Codex's feature flags, so a later Codex version could add a tool these flags don't cover.

After the change, `readback overview --backend codex` on s06 still produced a normal cited overview (22 s; sections Changed/Why/Tests/Risks, citations such as `[E7, H2]`, `[E8, E9]`).
