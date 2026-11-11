"""Orchestration: session + mode -> cited explanation.

The explainer keeps its own state (ask threads) under the readback state dir.
Nothing is ever written to the observed transcript, repo, or agent config.
"""

from __future__ import annotations

import hashlib
import json
import os
import textwrap
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import citations, evidence, prompts
from .backends import pick
from .gitdiff import attach_diff
from .model import Session
from .transcripts import Tail, load

SCREEN_ROWS, SCREEN_COLS = 48, 120  # "one screen": a 48-row, 120-column terminal


def screen_rows(text: str, width: int = SCREEN_COLS) -> int:
    """Terminal rows the text occupies when wrapped at `width` columns."""
    return sum(max(1, len(textwrap.wrap(ln, width))) for ln in text.strip().splitlines())


def state_dir() -> Path:
    base = os.environ.get("READBACK_STATE_DIR") or os.path.join(
        os.environ.get("XDG_STATE_HOME") or os.path.join(Path.home(), ".local", "state"), "agent-readback"
    )
    return Path(base)


@dataclass
class Explanation:
    mode: str
    text: str
    cited: list[str] = field(default_factory=list)
    unknown_removed: list[str] = field(default_factory=list)
    coverage: float = 1.0
    input_tokens: int | None = None
    output_tokens: int | None = None
    backend: str = ""
    events_seen: int = 0
    seconds: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


def open_session(
    path: str, repo: str | None = None, base: str | None = None, diff_file: str | None = None
) -> Session:
    s = load(path)
    return attach_diff(s, repo=repo, base=base, diff_file=diff_file)


class Explainer:
    def __init__(
        self,
        session: Session,
        backend=None,
        budget_tokens: int = 40_000,
        repair: bool = True,
        screen_rows: int = SCREEN_ROWS,
    ):
        self.session = session
        self.backend = backend or pick()
        self.budget = budget_tokens
        self.repair = repair
        self.screen_rows = screen_rows  # 0 disables the fit-to-screen pass

    # -- threads (ask mode) ------------------------------------------------
    def _thread_path(self) -> Path:
        key = hashlib.sha1(os.path.realpath(self.session.path).encode()).hexdigest()[:16]
        return state_dir() / "threads" / f"{key}.json"

    def history(self) -> list[dict]:
        p = self._thread_path()
        if not p.exists():
            return []
        try:
            return json.loads(p.read_text())["turns"]
        except (json.JSONDecodeError, KeyError):
            return []

    def _save_turn(self, question: str, ans: Explanation) -> None:
        p = self._thread_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        turns = self.history() + [
            {"question": question, "answer": ans.text, "events_seen": ans.events_seen, "at": time.time()}
        ]
        p.write_text(json.dumps({"transcript": self.session.path, "turns": turns}, indent=1))

    def reset_thread(self) -> None:
        p = self._thread_path()
        if p.exists():
            p.write_text(json.dumps({"transcript": self.session.path, "turns": []}))

    # -- core --------------------------------------------------------------
    def run(
        self, mode: str, question: str | None = None, lines: int | None = None, since: int = 0
    ) -> Explanation:
        t0 = time.time()
        valid = self.session.ids()
        extra = None
        if mode == "delta":
            new = self.session.events[since:]
            extra = "NEW EVENTS: " + (", ".join(e.id for e in new) if new else "(none)")
        pack = evidence.render(self.session, self.budget)
        history = self.history() if mode == "ask" else None
        prompt = prompts.build(mode, pack, question=question, history=history, lines=lines, extra=extra)
        reply = self.backend.complete(prompts.SYSTEM, prompt)
        text = reply.text
        chk = citations.check(text, valid)
        in_tok, out_tok = reply.input_tokens, reply.output_tokens
        if self.repair and not chk.ok and mode != "delta":
            problems = []
            if chk.unknown:
                problems.append("unknown ids " + ", ".join(chk.unknown))
            if chk.uncited_lines:
                problems.append(f"{len(chk.uncited_lines)} uncited lines")
            fix = self.backend.complete(
                prompts.SYSTEM,
                f"<EVIDENCE>\n{pack}\n</EVIDENCE>\n\n"
                + prompts.REPAIR.format(problems="; ".join(problems), answer=text),
            )
            chk2 = citations.check(fix.text, valid)
            if chk2.coverage >= chk.coverage and len(chk2.unknown) <= len(chk.unknown):
                text, chk = fix.text, chk2
            in_tok = (in_tok or 0) + (fix.input_tokens or 0) or None
            out_tok = (out_tok or 0) + (fix.output_tokens or 0) or None
        if self.screen_rows and mode != "delta" and screen_rows(text) > self.screen_rows:
            short = self.backend.complete(
                prompts.SYSTEM,
                prompts.SHORTEN.format(rows=self.screen_rows, cols=SCREEN_COLS, answer=text),
            )
            chk3 = citations.check(short.text, valid)
            if short.text.strip() and screen_rows(short.text) < screen_rows(text) and chk3.coverage >= 0.9:
                text, chk = short.text, chk3
            in_tok = (in_tok or 0) + (short.input_tokens or 0) or None
            out_tok = (out_tok or 0) + (short.output_tokens or 0) or None
        removed = chk.unknown
        if removed:
            text = citations.strip_unknown(text, valid)
        ans = Explanation(
            mode=mode,
            text=text,
            cited=sorted(set(chk.cited) - set(removed), key=lambda x: (x[0], int(x[1:]))),
            unknown_removed=removed,
            coverage=round(chk.coverage, 3),
            input_tokens=in_tok,
            output_tokens=out_tok,
            backend=reply.backend,
            events_seen=len(self.session.events),
            seconds=round(time.time() - t0, 1),
        )
        if mode == "ask" and question:
            self._save_turn(question, ans)
        return ans


def live(
    path: str,
    on_event,
    on_delta=None,
    explainer_factory=None,
    every: int = 0,
    interval: float = 1.0,
    stop=lambda: False,
    repo: str | None = None,
) -> None:
    """Tail a running transcript. Calls on_event(event) for each new event; if `every` > 0,
    also produces a delta explanation every `every` new events via on_delta(explanation)."""
    tail = Tail(path)
    emitted = explained = 0
    while not stop():
        if tail.poll():
            events = tail.session.events
            for e in events[emitted:]:
                on_event(e)
            emitted = len(events)
            if every and on_delta and emitted - explained >= every:
                attach_diff(tail.session, repo=repo)
                ex = (explainer_factory or Explainer)(tail.session)
                on_delta(ex.run("delta", since=explained))
                explained = emitted
        time.sleep(interval)
