"""Claude Code transcript parser (~/.claude/projects/<project>/<session>.jsonl).

The parser is incremental: `feed()` takes one decoded JSONL record at a time,
so the same code serves finished files and live tailing. A tool result arrives
in a later record than its tool_use; it is attached to the earlier event by
tool_use_id.
"""

from __future__ import annotations

import difflib
import json
from typing import Any

from ..model import Event, Session

WRITE_TOOLS = {"Edit", "MultiEdit", "Write", "NotebookEdit"}
SKIP_PREFIXES = ("<local-command-caveat>", "Caveat:", "<system-reminder>")


def _text_of(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(item.get("text", ""))
                elif item.get("type") == "image":
                    parts.append("[image]")
                elif "text" in item:
                    parts.append(str(item["text"]))
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(p for p in parts if p)
    if content is None:
        return ""
    return json.dumps(content, ensure_ascii=False)


def render_tool_input(name: str, inp: dict) -> str:
    """Render a tool call as one compact, human-readable string."""
    if not isinstance(inp, dict):
        return str(inp)
    if name == "Bash":
        cmd = inp.get("command", "")
        desc = inp.get("description")
        return f"$ {cmd}" + (f"  # {desc}" if desc else "")
    if name in ("Read", "NotebookRead"):
        path = inp.get("file_path") or inp.get("notebook_path", "")
        rng = ""
        if inp.get("offset") or inp.get("limit"):
            rng = f" (offset={inp.get('offset')}, limit={inp.get('limit')})"
        return f"{path}{rng}"
    if name == "Edit":
        return f"{inp.get('file_path', '')}\n--- old\n{inp.get('old_string', '')}\n+++ new\n{inp.get('new_string', '')}"
    if name == "MultiEdit":
        chunks = [inp.get("file_path", "")]
        for ed in inp.get("edits", []) or []:
            chunks.append(f"--- old\n{ed.get('old_string', '')}\n+++ new\n{ed.get('new_string', '')}")
        return "\n".join(chunks)
    if name == "Write":
        return f"{inp.get('file_path', '')}\n{inp.get('content', '')}"
    if name in ("Grep", "Glob"):
        bits = [inp.get("pattern", "")]
        for k in ("path", "glob", "type", "output_mode"):
            if inp.get(k):
                bits.append(f"{k}={inp[k]}")
        return " ".join(str(b) for b in bits)
    if name in ("Task", "Agent"):
        return f"{inp.get('description', '')}: {inp.get('prompt', '')}"
    if name == "TodoWrite":
        todos = inp.get("todos") or []
        return "\n".join(
            f"[{t.get('status', '?')}] {t.get('content', '')}" for t in todos if isinstance(t, dict)
        )
    return json.dumps(inp, ensure_ascii=False)


def _edit_patch(path: str, old: str, new: str) -> str:
    diff = difflib.unified_diff(
        old.splitlines(keepends=False),
        new.splitlines(keepends=False),
        f"a/{path}",
        f"b/{path}",
        lineterm="",
        n=2,
    )
    return "\n".join(diff)


def _structured_patch(path: str, sp: list) -> str | None:
    if not isinstance(sp, list) or not sp:
        return None
    out = [f"--- a/{path}", f"+++ b/{path}"]
    for h in sp:
        if not isinstance(h, dict):
            return None
        out.append(
            f"@@ -{h.get('oldStart', 0)},{h.get('oldLines', 0)} +{h.get('newStart', 0)},{h.get('newLines', 0)} @@"
        )
        out.extend(h.get("lines") or [])
    return "\n".join(out)


class ClaudeParser:
    agent = "claude-code"

    def __init__(self, path: str):
        self.session = Session(agent=self.agent, path=path)
        self._calls: dict[str, Event] = {}

    # -- helpers -----------------------------------------------------------
    def _new(self, **kw) -> Event:
        ev = Event(id=f"E{len(self.session.events) + 1}", **kw)
        self.session.events.append(ev)
        return ev

    def feed(self, rec: dict, line: int) -> None:
        if not isinstance(rec, dict):
            return
        s = self.session
        s.session_id = s.session_id or rec.get("sessionId")
        s.cwd = s.cwd or rec.get("cwd")
        ts = rec.get("timestamp")
        kind = rec.get("type")
        if kind not in ("user", "assistant") or rec.get("isSidechain"):
            return
        if ts:
            s.started = s.started or ts
            s.ended = ts
        msg = rec.get("message") or {}
        content = msg.get("content")
        if kind == "assistant":
            s.model = s.model or msg.get("model")
            blocks = content if isinstance(content, list) else [{"type": "text", "text": _text_of(content)}]
            for b in blocks:
                if not isinstance(b, dict):
                    continue
                bt = b.get("type")
                if bt == "text" and b.get("text", "").strip():
                    self._new(kind="assistant", text=b["text"].strip(), line=line, ts=ts)
                elif bt == "thinking" and b.get("thinking", "").strip():
                    self._new(kind="reasoning", text=b["thinking"].strip(), line=line, ts=ts)
                elif bt == "tool_use":
                    self._tool_use(b, line, ts)
            return
        # user record: either a human prompt or tool results
        if rec.get("isMeta") or rec.get("isCompactSummary"):
            return
        if isinstance(content, list) and any(
            isinstance(b, dict) and b.get("type") == "tool_result" for b in content
        ):
            for b in content:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    self._tool_result(b, rec.get("toolUseResult"), line)
            return
        text = _text_of(content).strip()
        if not text or text.startswith(SKIP_PREFIXES):
            return
        self._new(kind="user", text=text, line=line, ts=ts)

    def _tool_use(self, b: dict, line: int, ts: str | None) -> None:
        name = b.get("name") or "tool"
        inp = b.get("input") or {}
        ev = self._new(
            kind="tool", tool=name, text=render_tool_input(name, inp), line=line, ts=ts, call_id=b.get("id")
        )
        path = inp.get("file_path") or inp.get("notebook_path") if isinstance(inp, dict) else None
        if path:
            ev.files.append(path)
        if name in WRITE_TOOLS:
            ev.writes = True
            if name == "Edit":
                ev.patch = _edit_patch(path or "", inp.get("old_string", ""), inp.get("new_string", ""))
            elif name == "MultiEdit":
                ev.patch = "\n".join(
                    _edit_patch(path or "", e.get("old_string", ""), e.get("new_string", ""))
                    for e in inp.get("edits", []) or []
                )
            elif name == "Write":
                ev.patch = _edit_patch(path or "", "", inp.get("content", ""))
        if ev.call_id:
            self._calls[ev.call_id] = ev

    def _tool_result(self, b: dict, tur: Any, line: int) -> None:
        ev = self._calls.get(b.get("tool_use_id", ""))
        out = _text_of(b.get("content"))
        if ev is None:  # result without a visible call (e.g. truncated head while tailing)
            ev = self._new(kind="tool", tool="?", text="(call not in transcript)", line=line)
        ev.output = out
        ev.result_line = line
        ev.is_error = bool(b.get("is_error"))
        if isinstance(tur, dict) and ev.writes:
            sp = _structured_patch(
                tur.get("filePath") or (ev.files[0] if ev.files else ""), tur.get("structuredPatch")
            )
            if sp:
                ev.patch = sp


def looks_like_claude(first_records: list[dict]) -> bool:
    for r in first_records:
        if isinstance(r, dict) and (
            "sessionId" in r or r.get("type") in ("summary", "file-history-snapshot")
        ):
            return True
        if isinstance(r, dict) and r.get("type") in ("user", "assistant") and "message" in r:
            return True
    return False
