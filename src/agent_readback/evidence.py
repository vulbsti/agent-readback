"""Render a session into a compact, id-tagged evidence pack for the explainer model.

The pack is the only thing the model sees. Every line starts with the id the
model must cite ([E12], [H3]). Long tool outputs and diffs are squeezed to fit
a character budget: user prompts, the agent's own words, failing commands and
diff hunks get the most room; successful noisy outputs get the least.
"""

from __future__ import annotations

from .model import Event, Session

CHARS_PER_TOKEN = 4  # rough, provider-neutral; only used for budgeting


def _clip(text: str, n: int) -> str:
    text = text or ""
    if len(text) <= n:
        return text
    if n < 40:
        return text[:n] + "…"
    head = int(n * 0.65)
    tail = n - head
    return f"{text[:head]}\n…[{len(text) - n} chars omitted]…\n{text[-tail:]}"


def _one_line(text: str, n: int) -> str:
    t = " ".join((text or "").split())
    return t if len(t) <= n else t[: n - 1] + "…"


def _event_block(e: Event, caps: dict) -> str:
    if e.kind == "user":
        return f"[{e.id}] USER: {_clip(e.text, caps['user'])}"
    if e.kind == "assistant":
        return f"[{e.id}] AGENT: {_clip(e.text, caps['assistant'])}"
    if e.kind == "reasoning":
        return f"[{e.id}] AGENT-THINKING: {_clip(e.text, caps['reasoning'])}"
    status = "ERROR" if e.is_error else "ok"
    files = f" files={','.join(e.files)}" if e.files else ""
    head = f"[{e.id}] TOOL {e.tool}{files} -> {status}"
    inp_cap = caps["write_input"] if e.writes else caps["tool_input"]
    body = _clip(e.text, inp_cap)
    out = ""
    if e.output:
        cap = caps["error_output"] if e.is_error else caps["tool_output"]
        if e.writes and not e.is_error:
            cap = min(cap, 160)
        out = "\n  output: " + _clip(e.output, cap).replace("\n", "\n  ")
    return f"{head}\n  input: {body.replace(chr(10), chr(10) + '  ')}{out}"


BASE_CAPS = {
    "user": 4000,
    "assistant": 1800,
    "reasoning": 900,
    "tool_input": 500,
    "write_input": 900,
    "tool_output": 700,
    "error_output": 1600,
    "hunk": 3000,
}


def render(session: Session, budget_tokens: int = 40_000, since: int = 0) -> str:
    """Render the session within ~budget_tokens. `since` skips events before index `since`
    (used for incremental live explanations)."""
    budget = budget_tokens * CHARS_PER_TOKEN
    events = session.events[since:]
    scale = 1.0
    text = ""
    for _ in range(8):
        caps = {k: max(60, int(v * scale)) for k, v in BASE_CAPS.items()}
        text = _render_with(session, events, caps)
        if len(text) <= budget:
            return text
        scale *= 0.6
    # still too long: keep the first and last events, summarise the middle by id range
    caps = {k: max(60, int(v * scale)) for k, v in BASE_CAPS.items()}
    keep = max(10, len(events) // 3)
    while keep > 4:
        head, tail = events[: keep // 2], events[-keep // 2 :]
        text = _render_with(session, head + tail, caps, gap=(head[-1].id, tail[0].id))
        if len(text) <= budget:
            return text
        keep = int(keep * 0.7)
    return text[:budget]


def _render_with(
    session: Session, events: list[Event], caps: dict, gap: tuple[str, str] | None = None
) -> str:
    s = session
    out = [
        "## SESSION",
        f"agent={s.agent} model={s.model or '?'} cwd={s.cwd or '?'} events={len(s.events)} "
        f"started={s.started or '?'} ended={s.ended or '?'} diff_source={s.diff_source}",
        "",
        "## TRANSCRIPT EVENTS",
    ]
    for e in events:
        if gap and e.id == gap[1]:
            out.append(f"[… events after {gap[0]} up to {gap[1]} omitted to fit budget …]")
        out.append(_event_block(e, caps))
    out += ["", "## DIFF HUNKS (final state of the worktree vs. base)"]
    if not s.hunks:
        out.append("(no diff available)")
    for h in s.hunks:
        out.append(f"[{h.id}] {h.file} ({h.status}, +{h.added} -{h.removed})")
        out.append(_clip(h.text, caps["hunk"]))
    return "\n".join(out)


def index_lines(session: Session) -> str:
    """One line per event/hunk: the table of contents the CLI prints with --index."""
    rows = []
    for e in session.events:
        label = e.tool if e.kind == "tool" else e.kind
        flag = " !" if e.is_error else ""
        rows.append(f"{e.id:>5} {label:<12}{flag} {_one_line(e.text, 90)}")
    for h in session.hunks:
        rows.append(f"{h.id:>5} {h.file} {h.header[:60]} (+{h.added} -{h.removed})")
    return "\n".join(rows)
