---
description: Explain what the coding agent in another session did (read-only). Modes overview | walkthrough | mechanism | ask <question> | web | sessions
argument-hint: "[overview|walkthrough|mechanism|ask <question>|web|sessions] [-s <session>]"
allowed-tools: Bash(readback:*), Bash(uvx:*)
---

Run the agent-readback CLI and show its result. Do not read the other session's files yourself.

1. Build the command: `readback $ARGUMENTS`. If `$ARGUMENTS` is empty, use `readback overview`.
   If the first word is not one of overview, walkthrough, mechanism, ask, web, sessions, events, treat
   all of `$ARGUMENTS` as a question: `readback ask "$ARGUMENTS"`.
   For `web`, add `--no-open` and run it in the background, then print the URL it reports.
2. Run it with the Bash tool from the current directory. If `readback` is not installed, use
   `uvx --from git+https://github.com/vulbsti/agent-readback readback ...` instead.
3. Print stdout to the user verbatim. Do not summarise, rephrase, re-explain or add commentary:
   the output is already the explanation, and citations like [E12] / [H3] refer to `readback events`.
4. If it fails because no session was found, run `readback sessions --all` and show the list.
