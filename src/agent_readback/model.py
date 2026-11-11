"""Core data model: a session is a list of transcript events plus diff hunks.

Every event and hunk gets a short stable id (E12, H3). Explanations cite these
ids, and the web view turns them into links.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Event:
    """One step of the agent session.

    A tool call and its result are folded into a single event, so a citation
    like [E7] points at "ran pytest -> 2 failed" rather than at two records.
    """

    id: str
    kind: str  # user | assistant | reasoning | tool
    text: str  # user/assistant text, or the tool input rendered as text
    line: int  # 1-based line in the source transcript where the event starts
    tool: str | None = None
    output: str | None = None  # tool result text (possibly long)
    is_error: bool = False
    files: list[str] = field(default_factory=list)
    ts: str | None = None
    call_id: str | None = None
    result_line: int | None = None
    writes: bool = False  # the tool call modified files
    patch: str | None = None  # unified diff of this edit, when the transcript carries one

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Hunk:
    id: str
    file: str
    header: str  # the "@@ -a,b +c,d @@ ctx" line
    text: str  # hunk body including the header line
    old_start: int = 0
    new_start: int = 0
    added: int = 0
    removed: int = 0
    status: str = "modified"  # modified | added | deleted | renamed

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Session:
    agent: str  # claude-code | codex
    path: str
    session_id: str | None = None
    cwd: str | None = None
    started: str | None = None
    ended: str | None = None
    model: str | None = None
    events: list[Event] = field(default_factory=list)
    hunks: list[Hunk] = field(default_factory=list)
    diff_source: str = "none"  # git | file | transcript | none

    def event(self, eid: str) -> Event | None:
        for e in self.events:
            if e.id == eid:
                return e
        return None

    def ids(self) -> set[str]:
        return {e.id for e in self.events} | {h.id for h in self.hunks}

    def files_touched(self) -> list[str]:
        seen: dict[str, None] = {}
        for e in self.events:
            for f in e.files:
                seen.setdefault(f, None)
        for h in self.hunks:
            seen.setdefault(h.file, None)
        return list(seen)
