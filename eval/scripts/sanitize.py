#!/usr/bin/env python3
"""Sanitize a recorded Claude Code or Codex transcript before committing it.

Allowlist approach: only conversation records (prompts, agent messages, tool
calls/results, file changes) and a few safe fields survive. Account ids,
request blobs, injected instructions/memory, environment context and
encrypted reasoning are dropped. Paths and identities are rewritten.

usage:
  sanitize.py IN OUT --agent claude|codex --sandbox ABS_PATH --repo NAME [--replace OLD=NEW ...]
  sanitize.py --check FILE_OR_DIR...    # exit 1 if any forbidden pattern remains
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

# Generic patterns only. Patterns naming a specific person, machine or private tool belong in an
# untracked file (default: .work/private-patterns.txt, one regex per line; override with
# READBACK_PRIVATE_PATTERNS) so that the repo itself never contains them, encoded or not.
GENERIC = [
    r"/home/(?!user\b)[a-z]",
    r"sk-[A-Za-z0-9_-]{20,}",
    r"ghp_[A-Za-z0-9]{20,}",
    r"eyJ[A-Za-z0-9_-]{20,}\.",
    r"accountUuid",
    r"organizationUuid",
    r"creator_account_id",
    r"[A-Za-z0-9._%+-]+@(?!example\.com|pytest\.)[A-Za-z0-9.-]+\.[A-Za-z]{2,6}\b",
]
PRIVATE_FILE = Path(
    os.environ.get("READBACK_PRIVATE_PATTERNS")
    or Path(__file__).resolve().parents[2] / ".work" / "private-patterns.txt"
)


def private_patterns() -> list[str]:
    if not PRIVATE_FILE.is_file():
        return []
    lines = PRIVATE_FILE.read_text(encoding="utf-8").splitlines()
    return [ln.strip().removeprefix("rewrite:") for ln in lines if ln.strip() and not ln.startswith("#")]


def rewrite_patterns() -> list[str]:
    """Identities to replace with "user" inside transcripts: 'rewrite:' lines of the private file."""
    if not PRIVATE_FILE.is_file():
        return []
    lines = PRIVATE_FILE.read_text(encoding="utf-8").splitlines()
    return [ln.strip()[len("rewrite:") :] for ln in lines if ln.strip().startswith("rewrite:")]


FORBIDDEN = GENERIC + private_patterns()
INJECTED = (
    "<environment_context",
    "<user_instructions",
    "# AGENTS.md instructions",
    "<permissions",
    "<INSTRUCTIONS>",
    "<system-reminder>",
    "<multi_agent",
    "## Memory",
)

CLAUDE_KEEP = {
    "type",
    "uuid",
    "parentUuid",
    "timestamp",
    "sessionId",
    "cwd",
    "gitBranch",
    "version",
    "isSidechain",
    "isMeta",
    "message",
    "toolUseResult",
}
MSG_KEEP = {"role", "content", "model", "id", "type", "stop_reason"}


def rewrite(text: str, subs: list[tuple[str, str]]) -> str:
    for old, new in subs:
        text = text.replace(old, new)
    text = re.sub(r"/home/[A-Za-z0-9_.-]+", "/home/user", text)
    for pat in rewrite_patterns():
        text = re.sub(pat, "user", text, flags=re.I)
    text = re.sub(
        r"[A-Za-z0-9._%+-]+@(?!example\.com|pytest\.)[A-Za-z0-9.-]+\.[A-Za-z]{2,6}\b",
        "user@example.com",
        text,
    )
    return text


def _clean_claude(rec: dict) -> dict | None:
    if rec.get("type") not in ("user", "assistant"):
        return None
    out = {k: v for k, v in rec.items() if k in CLAUDE_KEEP}
    msg = {k: v for k, v in (out.get("message") or {}).items() if k in MSG_KEEP}
    content = msg.get("content")
    if isinstance(content, str) and content.lstrip().startswith(INJECTED):
        return None
    if isinstance(content, list):
        kept = []
        for b in content:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "text" and b.get("text", "").lstrip().startswith(INJECTED):
                continue
            if b.get("type") == "thinking":
                b = {"type": "thinking", "thinking": b.get("thinking", "")}
            kept.append(b)
        if not kept:
            return None
        msg["content"] = kept
    out["message"] = msg
    return out


def _clean_codex(rec: dict) -> dict | None:
    t = rec.get("type")
    p = rec.get("payload") if isinstance(rec.get("payload"), dict) else {}
    keep = {"timestamp": rec.get("timestamp"), "type": t}
    if t == "session_meta":
        keep["payload"] = {
            k: p.get(k)
            for k in (
                "id",
                "session_id",
                "cwd",
                "timestamp",
                "cli_version",
                "originator",
                "model_provider",
                "source",
            )
            if k in p
        }
        return keep
    if t == "turn_context":
        keep["payload"] = {k: p.get(k) for k in ("turn_id", "cwd", "model") if k in p}
        return keep
    if t == "event_msg":
        if p.get("type") == "item_completed" and isinstance(p.get("item"), dict):
            item = p["item"]
            if item.get("type") in ("CommandExecution", "FileChange"):
                keep["payload"] = {"type": "item_completed", "turn_id": p.get("turn_id"), "item": item}
                return keep
        if p.get("type") in ("task_started", "task_complete"):
            keep["payload"] = {k: p.get(k) for k in ("type", "turn_id", "last_agent_message") if k in p}
            return keep
        return None
    if t != "response_item":
        return None
    pt = p.get("type")
    if pt == "message":
        if p.get("role") not in ("user", "assistant"):
            return None
        text = "".join(c.get("text", "") for c in p.get("content") or [] if isinstance(c, dict))
        if text.lstrip().startswith(INJECTED):
            return None
        keep["payload"] = {"type": "message", "role": p["role"], "content": p.get("content")}
        return keep
    if pt == "reasoning":
        keep["payload"] = {"type": "reasoning", "summary": p.get("summary") or [], "encrypted_content": ""}
        return keep
    if pt in (
        "function_call",
        "custom_tool_call",
        "function_call_output",
        "custom_tool_call_output",
        "local_shell_call",
        "local_shell_call_output",
    ):
        keep["payload"] = {k: v for k, v in p.items() if k != "internal_chat_message_metadata_passthrough"}
        return keep
    return None


def sanitize(src: Path, dst: Path, agent: str, subs: list[tuple[str, str]]) -> int:
    clean = _clean_claude if agent == "claude" else _clean_codex
    n = 0
    with open(src, encoding="utf-8") as fh, open(dst, "w", encoding="utf-8") as out:
        for raw in fh:
            try:
                rec = json.loads(raw)
            except json.JSONDecodeError:
                continue
            c = clean(rec)
            if c is None:
                continue
            line = rewrite(json.dumps(c, ensure_ascii=False), subs)
            json.loads(line)  # still valid JSON after rewriting
            out.write(line + "\n")
            n += 1
    return n


def check(paths: list[str]) -> int:
    pat = re.compile("|".join(FORBIDDEN), re.I)
    bad = 0
    for p in paths:
        files = [Path(p)] if Path(p).is_file() else [f for f in Path(p).rglob("*") if f.is_file()]
        for f in files:
            for i, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                m = pat.search(line)
                if m:
                    bad += 1
                    print(f"{f}:{i}: forbidden pattern {m.group(0)!r}")
    src = (
        f"generic + {len(private_patterns())} private"
        if private_patterns()
        else "generic only (no private pattern file)"
    )
    print(f"checked {len(paths)} path(s) [{src} patterns]: {bad} finding(s)")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--agent", choices=["claude", "codex"])
    ap.add_argument("--sandbox")
    ap.add_argument("--repo")
    ap.add_argument(
        "--replace", action="append", default=[], help="OLD=NEW literal replacement (applied first)"
    )
    a = ap.parse_args()
    if a.check:
        return check(a.paths)
    src, dst = map(Path, a.paths)
    subs = [tuple(r.split("=", 1)) for r in a.replace]
    subs.append((a.sandbox.rstrip("/"), f"/sandbox/{a.repo}"))
    subs.sort(key=lambda s: -len(s[0]))  # longest first
    n = sanitize(src, dst, a.agent, subs)
    print(f"{dst}: {n} records")
    return 0


if __name__ == "__main__":
    sys.exit(main())
