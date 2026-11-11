"""Transcript loading, format detection, live tailing and session discovery.

All file access here is read-only: files are opened with mode "rb" and never
locked, truncated or touched.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from ..model import Session
from .claude import ClaudeParser, looks_like_claude
from .codex import CodexParser, looks_like_codex

__all__ = ["Tail", "load", "discover", "resolve", "SessionRef"]


def _sniff(path: str) -> str:
    recs = []
    with open(path, "rb") as fh:
        for raw in fh:
            try:
                recs.append(json.loads(raw))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            if len(recs) >= 8:
                break
    if looks_like_codex(recs) and not any(isinstance(r, dict) and "sessionId" in r for r in recs):
        return "codex"
    if looks_like_claude(recs):
        return "claude"
    raise ValueError(f"unrecognised transcript format: {path}")


class Tail:
    """Incrementally parse a growing JSONL transcript.

    `poll()` reads only bytes appended since the last call and only complete
    lines (a partially written trailing line is left for the next poll), so it
    is safe to run against a transcript the agent is still writing.
    """

    def __init__(self, path: str, fmt: str | None = None):
        self.path = str(path)
        self.fmt = fmt or _sniff(self.path)
        self.parser = ClaudeParser(self.path) if self.fmt == "claude" else CodexParser(self.path)
        self.offset = 0
        self.lines = 0

    @property
    def session(self) -> Session:
        return self.parser.session

    def poll(self) -> int:
        """Parse newly appended complete lines; return how many events were added."""
        before = len(self.session.events)
        try:
            size = os.path.getsize(self.path)
        except OSError:
            return 0
        if size < self.offset:  # file replaced/truncated: start over
            self.__init__(self.path, self.fmt)
        with open(self.path, "rb") as fh:
            fh.seek(self.offset)
            data = fh.read()
        end = data.rfind(b"\n")
        if end < 0:
            return 0
        chunk = data[: end + 1]
        self.offset += len(chunk)
        for raw in chunk.splitlines():
            self.lines += 1
            if not raw.strip():
                continue
            try:
                rec = json.loads(raw)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            self.parser.feed(rec, self.lines)
        return len(self.session.events) - before


def load(path: str) -> Session:
    t = Tail(path)
    t.poll()
    # a finished file may lack a trailing newline: parse the last line too
    with open(t.path, "rb") as fh:
        fh.seek(t.offset)
        rest = fh.read().strip()
    if rest:
        try:
            t.parser.feed(json.loads(rest), t.lines + 1)
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
    return t.session


# -- discovery -----------------------------------------------------------------


@dataclass
class SessionRef:
    path: str
    agent: str
    mtime: float
    cwd: str | None
    first_prompt: str


def claude_root() -> Path:
    return Path(os.environ.get("READBACK_CLAUDE_DIR") or Path.home() / ".claude" / "projects")


def codex_root() -> Path:
    return Path(os.environ.get("READBACK_CODEX_DIR") or Path.home() / ".codex" / "sessions")


def _peek(path: Path, agent: str) -> SessionRef:
    cwd, prompt = None, ""
    try:
        with open(path, "rb") as fh:
            for i, raw in enumerate(fh):
                if i > 400 or (cwd and prompt):
                    break
                try:
                    rec = json.loads(raw)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                if not isinstance(rec, dict):
                    continue
                if agent == "claude":
                    cwd = cwd or rec.get("cwd")
                    if rec.get("type") == "user" and not prompt and not rec.get("isMeta"):
                        c = (rec.get("message") or {}).get("content")
                        if isinstance(c, str) and not c.startswith("<"):
                            prompt = c
                else:
                    p = rec.get("payload") or {}
                    if rec.get("type") == "session_meta":
                        cwd = p.get("cwd")
                    if (
                        rec.get("type") == "response_item"
                        and p.get("type") == "message"
                        and p.get("role") == "user"
                    ):
                        txt = "".join(
                            x.get("text", "") for x in p.get("content") or [] if isinstance(x, dict)
                        )
                        if txt and not txt.startswith(("<", "# AGENTS.md")) and not prompt:
                            prompt = txt
    except OSError:
        pass
    return SessionRef(str(path), agent, path.stat().st_mtime, cwd, " ".join(prompt.split())[:100])


def discover(cwd: str | None = None, limit: int = 20) -> list[SessionRef]:
    """Recent Claude Code and Codex sessions, newest first; optionally only those run in `cwd`."""
    cands: list[tuple[float, Path, str]] = []
    cr, xr = claude_root(), codex_root()
    if cr.is_dir():
        cands += [(p.stat().st_mtime, p, "claude") for p in cr.glob("*/*.jsonl")]
    if xr.is_dir():
        cands += [(p.stat().st_mtime, p, "codex") for p in xr.glob("**/rollout-*.jsonl")]
    cands.sort(key=lambda c: c[0], reverse=True)
    own = os.environ.get("CLAUDE_CODE_SESSION_ID")
    out: list[SessionRef] = []
    want = os.path.realpath(cwd) if cwd else None
    for _, p, agent in cands[:2000]:
        if own and p.stem == own:  # never explain the explainer's own session
            continue
        ref = _peek(p, agent)
        if want and (not ref.cwd or os.path.realpath(ref.cwd) != want):
            continue
        out.append(ref)
        if len(out) >= limit:
            break
    return out


def resolve(spec: str | None, cwd: str | None = None) -> str:
    """Turn a user-supplied session spec into a transcript path.

    spec may be a file path, a session id (or unique prefix), or None/"latest"
    for the most recent session in `cwd` (falling back to any directory).
    """
    if spec and os.path.isfile(spec):
        return spec
    if not spec or spec == "latest":
        refs = discover(cwd=cwd, limit=1) or discover(limit=1)
        if not refs:
            raise FileNotFoundError("no Claude Code or Codex sessions found")
        return refs[0].path
    paths = list(claude_root().glob("*/*.jsonl")) if claude_root().is_dir() else []
    paths += list(codex_root().glob("**/rollout-*.jsonl")) if codex_root().is_dir() else []
    # Claude files are named <uuid>.jsonl; Codex files rollout-<timestamp>-<uuid>.jsonl, so a Codex id
    # prefix is matched against the trailing 36-character uuid.
    hits = [
        p for p in paths if p.stem.startswith(spec) or p.stem.endswith(spec) or p.stem[-36:].startswith(spec)
    ]
    if len(hits) == 1:
        return str(hits[0])
    if len(hits) > 1:
        raise FileNotFoundError(f"{spec!r} is ambiguous ({len(hits)} sessions); use a longer id or a path")
    raise FileNotFoundError(f"no session matches {spec!r}")
