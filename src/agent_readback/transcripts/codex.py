"""Codex CLI rollout parser (~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl).

Two tool-call shapes are handled:
  * classic: response_item function_call / custom_tool_call (shell, exec_command,
    apply_patch) followed by *_output with the same call_id;
  * code mode: a custom_tool_call named "exec" whose input is a JS snippet that
    calls tools.exec_command / tools.apply_patch. The concrete commands, exit
    codes and file changes then arrive as event_msg item_completed records
    (CommandExecution / FileChange), which are folded into the enclosing event.
"""

from __future__ import annotations

import json
import re
from typing import Any

from ..model import Event, Session

INJECTED_PREFIXES = (
    "<environment_context",
    "<user_instructions",
    "# AGENTS.md instructions",
    "<permissions",
    "<INSTRUCTIONS>",
    "<user_shell_command",
    "<turn_aborted",
)
PATCH_FILE_RE = re.compile(r"^\*\*\* (?:Update|Add|Delete) File: (.+)$|^\*\*\* Move to: (.+)$", re.M)


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    out = []
    for c in content or []:
        if isinstance(c, dict):
            t = c.get("text")
            if t:
                out.append(t)
    return "\n".join(out)


def _output_text(output: Any) -> tuple[str, int | None]:
    """Return (text, exit_code) from the many shapes Codex uses for tool output."""
    exit_code = None
    if isinstance(output, list):
        texts = [_content_text([o]) if isinstance(o, dict) else str(o) for o in output]
        output = "\n".join(t for t in texts if t)
    if isinstance(output, dict):
        output = json.dumps(output)
    text = str(output or "")
    # code-mode chunks embed JSON objects with exit_code/output
    pieces = []
    for m in re.finditer(r"\{\"chunk_id\".*?\}(?=\n|$)", text):
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError:
            continue
        if obj.get("exit_code") is not None:
            exit_code = obj["exit_code"]
        if obj.get("output"):
            pieces.append(obj["output"])
    if pieces:
        text = "\n".join(pieces)
    try:
        obj = json.loads(text)
        if isinstance(obj, dict) and "output" in obj:
            meta = obj.get("metadata") or {}
            exit_code = meta.get("exit_code", exit_code)
            text = str(obj["output"])
    except (json.JSONDecodeError, TypeError):
        pass
    m = re.search(r"(?:Exit code|Process exited with code):? (-?\d+)", text)
    if m and exit_code is None:
        exit_code = int(m.group(1))
    return text, exit_code


def _render_call(name: str, args: Any) -> str:
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            return args
    if isinstance(args, dict):
        cmd = args.get("command") or args.get("cmd")
        if isinstance(cmd, list):
            cmd = " ".join(cmd[2:] if cmd[:2] in (["bash", "-lc"], ["/bin/bash", "-lc"]) else cmd)
        if cmd:
            return f"$ {cmd}"
        if name == "update_plan":
            return "\n".join(
                f"[{p.get('status')}] {p.get('step')}" for p in args.get("plan", []) if isinstance(p, dict)
            )
        return json.dumps(args, ensure_ascii=False)
    return str(args)


EXEC_PLACEHOLDER = "exec (code mode)"
SCRIPT_HEADER_RE = re.compile(r"^Script completed\nWall time [\d.]+ seconds\nOutput:\n?", re.M)
CODE_TOOL_RE = re.compile(r"tools\.([A-Za-z_]+)\(")


def _summarize_exec(code: str) -> str:
    """Code-mode `exec` input is JS. Shell commands and patches are filled in later from
    item_completed records; other tool calls (web search/fetch, MCP tools, ...) are only
    visible here, so list them with their (clipped) arguments."""
    lines = []
    for m in CODE_TOOL_RE.finditer(code):
        tool = m.group(1)
        if tool in ("exec_command", "apply_patch", "write_stdin"):
            continue
        args = code[m.end() : m.end() + 300].split("));", 1)[0]
        lines.append(f"{tool}({args})")
    return "\n".join(lines) or EXEC_PLACEHOLDER


def _patch_files(patch: str) -> list[str]:
    return [a or b for a, b in PATCH_FILE_RE.findall(patch or "")]


class CodexParser:
    agent = "codex"

    def __init__(self, path: str):
        self.session = Session(agent=self.agent, path=path)
        self._calls: dict[str, Event] = {}
        self._last_tool: Event | None = None

    def _new(self, **kw) -> Event:
        ev = Event(id=f"E{len(self.session.events) + 1}", **kw)
        self.session.events.append(ev)
        return ev

    def feed(self, rec: dict, line: int) -> None:
        if not isinstance(rec, dict):
            return
        s = self.session
        rtype = rec.get("type")
        p = rec.get("payload") if isinstance(rec.get("payload"), dict) else {}
        ts = rec.get("timestamp")
        if ts:
            s.started = s.started or ts
            s.ended = ts
        if rtype == "session_meta":
            s.session_id = s.session_id or p.get("id") or p.get("session_id")
            s.cwd = s.cwd or p.get("cwd")
            return
        if rtype == "turn_context":
            s.model = s.model or p.get("model")
            s.cwd = s.cwd or p.get("cwd")
            return
        if rtype == "event_msg" and p.get("type") == "item_completed":
            self._item_completed(p.get("item") or {}, line)
            return
        if rtype != "response_item":
            return
        pt = p.get("type")
        if pt == "message":
            role = p.get("role")
            text = _content_text(p.get("content")).strip()
            if not text or role not in ("user", "assistant"):
                return
            if role == "user" and text.startswith(INJECTED_PREFIXES):
                return
            self._new(kind=role, text=text, line=line, ts=ts)
        elif pt == "reasoning":
            summ = "\n".join(x.get("text", "") for x in p.get("summary") or [] if isinstance(x, dict)).strip()
            if summ:
                self._new(kind="reasoning", text=summ, line=line, ts=ts)
        elif pt in ("function_call", "custom_tool_call", "local_shell_call"):
            name = p.get("name") or ("shell" if pt == "local_shell_call" else "tool")
            raw = p.get("arguments") if pt == "function_call" else p.get("input")
            if pt == "local_shell_call":
                raw = p.get("action") or {}
            text = (
                _summarize_exec(raw) if name == "exec" and isinstance(raw, str) else _render_call(name, raw)
            )
            ev = self._new(kind="tool", tool=name, text=text, line=line, ts=ts, call_id=p.get("call_id"))
            if name == "apply_patch" or "apply_patch" in str(raw)[:2000]:
                files = _patch_files(str(raw))
                if files:
                    ev.files.extend(files)
                    ev.writes = True
                    if name == "apply_patch":
                        ev.patch = str(raw)
            if ev.call_id:
                self._calls[ev.call_id] = ev
            self._last_tool = ev
        elif pt in ("function_call_output", "custom_tool_call_output", "local_shell_call_output"):
            ev = self._calls.get(p.get("call_id", ""))
            text, code = _output_text(p.get("output"))
            if ev is None:
                ev = self._new(kind="tool", tool="?", text="(call not in transcript)", line=line, ts=ts)
            if not ev.output:
                ev.output = text
            else:  # code mode: keep script output (e.g. web results) not already folded in from item_completed
                extra = SCRIPT_HEADER_RE.sub("", text).strip()
                if extra and extra not in ev.output:
                    ev.output += "\n[script output]\n" + extra
            ev.result_line = line
            if code not in (None, 0):
                ev.is_error = True

    def _item_completed(self, item: dict, line: int) -> None:
        ev = self._last_tool
        itype = item.get("type")
        if ev is None or itype not in ("CommandExecution", "FileChange"):
            return
        if itype == "CommandExecution":
            cmd = item.get("command")
            if isinstance(cmd, list):
                cmd = cmd[-1] if len(cmd) >= 3 and cmd[1] == "-lc" else " ".join(cmd)
            code = item.get("exit_code")
            try:
                code = int(code) if code is not None else None
            except (TypeError, ValueError):
                code = None
            sub = f"$ {cmd}" + (f"  -> exit {code}" if code is not None else "")
            ev.text = sub if ev.text == EXEC_PLACEHOLDER else ev.text + "\n" + sub
            if ev.tool == "exec":
                ev.tool = "exec_command"
            out = item.get("aggregated_output") or ""
            ev.output = (ev.output + "\n" if ev.output else "") + f"{sub}\n{out}"
            if code not in (None, 0):
                ev.is_error = True
        else:
            changes = item.get("changes") or {}
            patches = []
            for path, ch in changes.items() if isinstance(changes, dict) else []:
                ev.files.append(path)
                if not isinstance(ch, dict):
                    continue
                if ch.get("type") == "add":
                    body = "\n".join("+" + ln for ln in str(ch.get("content", "")).splitlines())
                    n = len(str(ch.get("content", "")).splitlines())
                    patches.append(f"--- /dev/null\n+++ b/{path}\n@@ -0,0 +1,{n} @@\n{body}")
                elif ch.get("type") == "delete":
                    patches.append(f"--- a/{path}\n+++ /dev/null")
                else:
                    patches.append(f"--- a/{path}\n+++ b/{path}\n{ch.get('unified_diff', '')}")
            ev.writes = True
            ev.tool = "apply_patch"
            ev.patch = "\n".join(patches) or ev.patch
            if ev.text == EXEC_PLACEHOLDER:
                ev.text = "apply_patch " + ", ".join(changes) if isinstance(changes, dict) else ev.text


def looks_like_codex(first_records: list[dict]) -> bool:
    return any(
        isinstance(r, dict) and r.get("type") in ("session_meta", "response_item", "turn_context")
        for r in first_records
    )
