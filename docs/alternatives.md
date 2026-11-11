# Alternatives and adjacent tools

Checked 2026-11-05 against each project's GitHub repo (`gh api repos/OWNER/REPO` for stars, license and
last push) or official docs. Star counts and dates are from that day. Anything not stated in a
primary source is marked "not verified".

The question each row answers: how far does the tool get you toward understanding *what a coding
agent did in a session and why*, using the transcript and the code change as evidence?

## Comparison

| Project | Form factor | What it does for "understanding what the agent did" | Reads live sessions? | Cites evidence? | Multi-turn? | License | Stars | Last activity |
|---|---|---|---|---|---|---|---|---|
| agent-readback (this repo) | CLI + Claude Code plugin + local web view | LLM answers (overview, walkthrough, Mermaid mechanism, free questions) built from the transcript plus the git diff | Yes (`watch`, live tail) | Yes, transcript event ids and diff hunks | Yes (`ask`) | Apache-2.0 | n/a (unreleased) | local |
| Claude Code `/btw` | Built-in slash command | Side question answered from the current conversation context; not added to history | Yes, current session only | No | Partly: one reply per ask, but the newest 20 earlier side questions are replayed; VS Code panel allows follow-ups | Proprietary | n/a | docs checked 2026-11-05 |
| Claude Code `/export`, `/recap`, `/resume`, `/rewind`; Codex `codex resume` | Built-in commands | Plain-text export, one-line recap, resume or rewind a session | Current session | No | Via resume (adds to that session) | Claude Code proprietary; Codex CLI Apache-2.0 | n/a | docs checked 2026-11-05 |
| [daaain/claude-code-log](https://github.com/daaain/claude-code-log) | Python CLI, TUI, local server | Renders Claude Code JSONL as HTML/Markdown/JSON with filtering, timeline, full-text search; Codex support beta | Yes (`watch`, `serve --watch`) | n/a (renders the transcript, makes no claims) | No | MIT | 1,255 | 2026-11-05 |
| [d-kimuson/claude-code-viewer](https://github.com/d-kimuson/claude-code-viewer) | Local web client (Node) | Real-time log view, tool-call rendering, Git diff viewer with inline comments, also starts/continues sessions | Yes | n/a | n/a (it is a client for the agent itself) | MIT | 1,306 | 2026-08-18 |
| [matt1398/claude-devtools](https://github.com/matt1398/claude-devtools) | Desktop app / Docker | Tool-call inspector with inline Edit diffs, thinking, subagent trees, per-turn token attribution, compaction view, SSH remote sessions | Not verified | n/a | No | MIT | 4,014 | 2026-09-26 |
| [PixelPaw-Labs/codex-trace](https://github.com/PixelPaw-Labs/codex-trace) | Desktop + web viewer | Codex CLI `~/.codex/sessions` viewer: turns, exec/patch/MCP events, tokens, orchestrator-worker links | Yes (SSE live tail) | n/a | No | MIT | 119 | 2026-10-31 |
| [SpecStory](https://github.com/specstoryai/getspecstory) | CLI + IDE extensions + cloud | Saves sessions from many agents to `.specstory/history/`; optional cloud search and "ask" across sessions; `/lore` mines history into skills | Captures during the session | Not verified | Cloud chat (login required); details not verified | Apache-2.0 (CLI); cloud and Cursor/Copilot extensions closed | 1,368 | 2026-11-05 |
| [entireio/cli](https://github.com/entireio/cli) (Entire) | CLI + hosted Git forge | Captures agent sessions as checkpoints linked to commits; `entire checkpoint explain`, search, `dispatch` summaries; Trails with review-agent findings | Captures during the session; `trail watch` streams | `checkpoint explain` shows prompt, transcript and files; citation in generated text not verified | Not verified | MIT (CLI) | 5,310 | 2026-11-05 |
| [git-ai-project/git-ai](https://github.com/git-ai-project/git-ai) | Git extension | Line-level AI attribution in git notes, linking lines to agent, model and prompt; `git ai blame`, stats | No (recorded at commit) | Attribution per line by construction; no explanations | No | Apache-2.0 | 2,944 | 2026-11-05 |
| [Langfuse](https://github.com/langfuse/langfuse) + [Claude Observability Plugin](https://github.com/langfuse/claude-observability-plugin) | Hosted or self-hosted observability platform + Claude Code hook plugin | Traces Claude Code turns, generations, tool calls and tokens into Langfuse | Per turn (Stop hook) | n/a (traces, not explanations) | Not verified | MIT core + separate `ee/` license; plugin MIT | 37,051 (plugin 30) | 2026-11-05 (plugin 2026-10-26) |
| [The-PR-Agent/pr-agent](https://github.com/The-PR-Agent/pr-agent) (also CodeRabbit) | PR bot / CLI | `/describe`, `/review`, `/ask` over a PR diff; CodeRabbit posts walkthroughs with Mermaid sequence diagrams | No (PR diff only, no transcript) | Not verified | `/ask` per call; CodeRabbit chat in PR comments | MIT (CodeRabbit proprietary) | 15,003 | 2026-11-05 |
| [SeanPash/Codey](https://github.com/SeanPash/Codey) | Claude Code plugin + local browser timeline | Timeline of every step, live terminal narration (simple/deep/teach), "Explain this step", stuck-loop detection | Yes | "Rich" mode grounds explanations in actual edits; citation format not verified | Not verified | MIT | 2 | 2026-07-07 |
| [aoprisan/agentdiff](https://github.com/aoprisan/agentdiff) | Rust TUI | Diff scoped to one Claude Code run, per-hunk "why" pulled from the transcript, test/lint commands and results, review checklist; read-only | Yes (live re-diff) | Yes, transcript intent next to each hunk (no LLM text) | No | None stated on GitHub | 0 | 2026-07-03 |

## Notes

- **Claude Code `/btw`.** Per the [interactive-mode docs](https://code.claude.com/docs/en/interactive-mode),
  it answers only from what is already in context, has no tool access, and its exchanges never
  enter the conversation history. It is the closest built-in to agent-readback's "no context added"
  rule and costs little with a warm prompt cache; agent-readback is weaker in that it needs a
  separate backend call and a full evidence pack, but `/btw` cannot see the git diff unless the agent
  already read it, cannot inspect a Codex session, and gives no citations.
- **Built-in history commands.** `/export` writes plain text; `/recap` gives one line; `/resume` and
  `codex resume` reopen a session, which adds to that session's context. Codex `/diff` and `/review`
  behaviour was only seen in third-party cheat sheets and the Codex features page (not verified in
  full).
- **claude-code-log.** Mature renderer with watch mode, archive search and a TUI; it does not
  generate explanations. It covers far more Claude Code record types than agent-readback (which
  skips subagent sidechains) and has a polished HTML view; agent-readback has no archive search.
- **claude-code-viewer.** A full web client (chat, resume, commit, push) with a Git diff viewer. It
  shows evidence but does not explain it; it also writes to the repo when used for commits, which
  agent-readback never does. agent-readback's web view is far more basic.
- **claude-devtools.** Desktop debugger with deep Claude Code coverage (thinking, context
  attribution, subagents, SSH remotes, notifications). No LLM explanations and no Codex support
  stated. agent-readback has no token/context analysis and no remote-machine support.
- **codex-trace.** Codex-only viewer with live tail; a sibling project,
  [delexw/claude-code-trace](https://github.com/delexw/claude-code-trace) (385 stars, MIT), does the
  same for Claude Code. Viewers only, no generated answers.
- **SpecStory.** Supports roughly 15 agents versus agent-readback's two, and has team sync and
  cross-session Q&A in its cloud. Its local CLI is a capture/export tool; whether its cloud answers
  cite specific events was not verified.
- **Entire.** The broadest adjacent product: session capture tied to commits, rewind/resume,
  semantic search, and review agents on a hosted forge. Transcripts are pushed to the Git remote by
  default (per its README). agent-readback has no persistence, search, team or hosted features; it
  explains one session at a time from local files.
- **git-ai.** Answers "which lines did an agent write, from which prompt" durably across rebases
  and squashes, and has a Teams product. It does not explain mechanism or answer questions;
  agent-readback does not record anything and loses its view once the transcript is gone.
- **Langfuse.** General LLM observability with a Claude Code plugin that ships traces to a Langfuse
  server. Good for cost/latency dashboards across many sessions; not aimed at explaining a code
  change. AgentOps ([AgentOps-AI/agentops](https://github.com/AgentOps-AI/agentops), 5,949 stars, MIT,
  last push 2026-06-25) is a similar SDK-based session-replay service; no Claude Code or Codex
  transcript integration found in its README (not verified beyond that).
- **PR-Agent / CodeRabbit.** Explain a diff at PR time, including Mermaid sequence diagrams
  (CodeRabbit, per its [walkthrough docs](https://docs.coderabbit.ai/pr-reviews/walkthroughs)). They
  never see the agent's transcript, so they cannot say why a change was made or what was tried and
  reverted. They do integrate with GitHub/GitLab review flows, which agent-readback does not.
- **Codey.** The closest in intent: explains each step of a Claude Code run live, with a local
  timeline. It runs inside the executor session via hooks and its intervention buttons feed text
  to Claude on click; whether narration adds to the executor's context was not verified. Very new
  (2 stars), Claude Code only.
- **agentdiff.** The closest in method: per-hunk mapping from diff to the transcript turn that
  produced it, read-only, no LLM. It does not generate overviews, diagrams or answers, and supports
  only Claude Code. agent-readback's answers depend on an LLM backend (and send the evidence pack to
  it), which agentdiff avoids.

## Where agent-readback is weaker overall

- Two transcript formats only (Claude Code, Codex CLI); subagent sidechains are skipped.
- Every answer depends on an LLM backend (`claude`, `codex`, or an API key); the evidence pack is
  sent to that backend, and answer quality varies with the model.
- No hosted UI, no team sharing, no persistence or cross-session search; the web view is local and
  minimal.
- No token, cost or context-window analysis.
- Not yet published on PyPI; no user base.

## Also checked

- [simonw/claude-code-transcripts](https://github.com/simonw/claude-code-transcripts): Apache-2.0,
  1,730 stars, last push 2026-02-12. Converts Claude Code sessions to paginated HTML and can publish
  to a Gist; its README notes the Claude Code for web commands are currently broken.
- `nyatinte/ccexp` (270 stars, MIT): explores Claude Code configuration files and slash commands,
  not transcripts. Not an alternative.
