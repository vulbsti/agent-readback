# Backends

A backend turns `(system prompt, prompt)` into an answer. The prompt contains the evidence pack:
transcript content and diff hunks of the observed session, clipped to `--budget`. **That content is
sent to whatever the backend talks to.** Run `readback pack` to see it.

## Selection

1. `--backend NAME`, else
2. `READBACK_BACKEND`, else
3. `READBACK_CMD` set → the `command` backend, else
4. auto-detect, first match wins: `claude` on `PATH`, `codex` on `PATH`, `ANTHROPIC_API_KEY` set,
   `OPENAI_API_KEY` set.

If nothing matches, readback exits with an error. The model is `--model`, else `READBACK_MODEL`,
else the backend default.

## `claude` (Claude Code CLI)

```
claude -p --output-format json --tools "" --no-session-persistence --setting-sources "" \
       --strict-mcp-config --system-prompt <SYSTEM> [--model M]
```

- Prompt on stdin; runs in a fresh temporary directory.
- No tools, no saved session, no user/project settings, no MCP servers.
- Uses the CLI's own login and default model. Data goes wherever that CLI is configured to send it.
- Token counts include cache reads and writes.

## `codex` (Codex CLI)

Tested with Codex CLI 0.166. Older versions (0.101 was checked) reject `--ignore-user-config`; upgrade Codex if you see that error.

```
codex exec --sandbox read-only --ephemeral --skip-git-repo-check --ignore-user-config --ignore-rules \
  -c 'web_search="disabled"' \
  --disable=code_mode_host --disable=shell_tool --disable=unified_exec --disable=multi_agent \
  --disable=image_generation --disable=view_image --disable=apps --disable=plugins \
  --disable=remote_plugin --disable=hooks --disable=memories --disable=skill_search \
  --disable=tool_suggest --disable=sleep_tool --disable=browser_use --disable=browser_use_external \
  --disable=computer_use --disable=in_app_browser \
  --json -o <tmpfile> [-m M] -
```

The `--disable` list is generated from `CODEX_DISABLED_FEATURES` in `src/agent_readback/backends.py`, the single source of truth.

- System prompt and prompt are sent together on stdin (system wrapped in `<instructions>`).
- Runs in a fresh temporary directory with Codex's read-only sandbox; nothing is persisted.
- Uses a throwaway `CODEX_HOME` that contains only a symlink to your `auth.json` (`$CODEX_HOME` or `~/.codex`), so your global `AGENTS.md`, memories and `config.toml` never reach the explainer. Note: `--ignore-user-config` alone skips only `config.toml`.
- **Tools disabled, by feature flag:** readback passes `-c web_search="disabled"` and `--disable` for every tool-providing feature (`CODEX_DISABLED_FEATURES` in `backends.py`: `code_mode_host`, `shell_tool`, `unified_exec`, `multi_agent`, `image_generation`, apps, plugins and more). In a probe with Codex 0.166, every attempt to run a shell command, fetch a URL, apply a patch or spawn an agent failed; with the earlier flags the same probe ran `ls /` and fetched a page (`docs/verification/backends.md`). Codex still declares the tool names, and a future Codex version could add a tool these flags don't cover, so prefer `claude` or an API backend for untrusted transcripts.
- Uses the CLI's own login and default model.

## `anthropic` (Messages API)

| env | |
|---|---|
| `ANTHROPIC_API_KEY` | required |
| `ANTHROPIC_BASE_URL` | default `https://api.anthropic.com` |
| `READBACK_MODEL` | default `claude-sonnet-5-5` |

- `POST {base}/v1/messages` with `x-api-key` and `anthropic-version: 2023-06-01`, `max_tokens`
  4096, via `urllib` (no SDK).
- The user message is marked `cache_control: ephemeral`, so repeated `ask` turns over the same
  evidence can hit the prompt cache.

## `openai` (OpenAI-compatible)

| env | |
|---|---|
| `OPENAI_API_KEY` | required (sent as `Authorization: Bearer`) |
| `OPENAI_BASE_URL` | default `https://api.openai.com/v1` |
| `READBACK_MODEL` or `--model` | required; there is no default because the endpoint may not be OpenAI's |

- `POST {base}/chat/completions` with a system and a user message.
- Works with any server that implements that endpoint (hosted gateways or a local server).

## `command` (any program)

| env | |
|---|---|
| `READBACK_CMD` | required, e.g. `READBACK_CMD='llm -m mymodel'` |

- The command is split with `shlex` (no shell) and run in a fresh temporary directory.
- It receives `SYSTEM + "\n\n" + prompt` on stdin and must print the answer on stdout; a non-zero
  exit is an error.
- `--model` is ignored; put the model in the command. Token counts are not reported.
- readback cannot restrict what this program does or where it sends data.

## `fake` (offline)

Deterministic, no network: echoes a cited bullet list built from the evidence ids (plus a stub
Mermaid block in `mechanism` mode). Used by the tests; useful for trying the CLI or web view
without a model.

## Other environment variables

| env | meaning |
|---|---|
| `READBACK_STATE_DIR` | readback's own state (ask threads). Default `$XDG_STATE_HOME/agent-readback`, else `~/.local/state/agent-readback`. |
| `READBACK_CLAUDE_DIR` | where Claude Code transcripts are found. Default `~/.claude/projects`. |
| `READBACK_CODEX_DIR` | where Codex transcripts are found. Default `~/.codex/sessions`. |

## What is sent where

| backend | destination of the evidence pack |
|---|---|
| `claude` | the provider configured for your Claude Code CLI |
| `codex` | the provider configured for your Codex CLI |
| `anthropic` | `ANTHROPIC_BASE_URL` |
| `openai` | `OPENAI_BASE_URL` |
| `command` | whatever `READBACK_CMD` does |
| `fake` | nowhere |

Every backend gets the same content: `prompts.SYSTEM`, the evidence pack, the mode instruction,
and for `ask` the question plus up to the last 6 turns of the thread. readback adds nothing else
to the request. At most two extra calls follow an answer: a citation repair (the same pack plus the
answer) and a fit-to-screen shortening (only the answer).
