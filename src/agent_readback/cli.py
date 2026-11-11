"""readback: explain what a coding agent did, without touching its context or repo."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

from . import __version__, evidence
from .backends import BackendError, pick
from .explain import Explainer, live, open_session
from .transcripts import claude_root, codex_root, discover, resolve


def _session_args(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "-s",
        "--session",
        help="transcript path, session id/prefix, or 'latest' (default: latest session run in --repo or the current dir)",
    )
    p.add_argument("--repo", help="worktree the agent changed (default: the session's cwd)")
    p.add_argument(
        "--base",
        default="auto",
        help="git ref to diff against (default: auto = parent of the first commit made between session start "
        "and 10 min after its last record, else HEAD; diffs the current worktree)",
    )
    p.add_argument("--diff-file", help="use this unified diff instead of reading git")


def _llm_args(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--backend",
        help="claude | codex | anthropic | openai | command | fake (default: READBACK_BACKEND or auto-detect)",
    )
    p.add_argument(
        "--model", help="model name passed to the backend (default: READBACK_MODEL or the backend's default)"
    )
    p.add_argument(
        "--budget", type=int, default=40_000, help="max tokens of evidence sent to the model (default 40000)"
    )
    p.add_argument("--lines", type=int, help="target answer length in lines")
    p.add_argument("--json", action="store_true", help="print a JSON object (text, citations, tokens)")
    p.add_argument(
        "--no-repair", action="store_true", help="skip the second pass that fixes missing citations"
    )


def _load(a):
    path = resolve(a.session, cwd=a.repo or os.getcwd())
    return open_session(path, repo=a.repo, base=a.base, diff_file=a.diff_file)


def _print_expl(ex, as_json: bool) -> None:
    if as_json:
        print(json.dumps(ex.to_dict(), indent=1))
        return
    print(ex.text.strip())
    meta = f"[{ex.backend} · {ex.events_seen} events · cites {len(ex.cited)} · coverage {ex.coverage:.0%}"
    if ex.input_tokens:
        meta += f" · {ex.input_tokens}→{ex.output_tokens or '?'} tok"
    print(f"\n{meta} · {ex.seconds}s]", file=sys.stderr)


def cmd_sessions(a) -> int:
    refs = discover(cwd=None if a.all else (a.repo or os.getcwd()), limit=a.n)
    if not refs and not a.all:
        refs = discover(limit=a.n)
        if refs:
            print("no sessions for this directory; showing all directories", file=sys.stderr)
    if not refs:
        print(
            f"no sessions found (looked in {claude_root()} and {codex_root()}); "
            "pass a transcript path with -s, or set READBACK_CLAUDE_DIR / READBACK_CODEX_DIR",
            file=sys.stderr,
        )
        return 1
    for r in refs:
        when = time.strftime("%m-%d %H:%M", time.localtime(r.mtime))
        sid = os.path.basename(r.path).removesuffix(".jsonl")[-36:]
        print(f"{when}  {r.agent:<6} {sid}  {r.cwd or '?'}\n      {r.first_prompt}")
    return 0


def cmd_events(a) -> int:
    s = _load(a)
    print(f"{s.agent} {s.session_id or ''} · {len(s.events)} events · {len(s.hunks)} hunks ({s.diff_source})")
    print(evidence.index_lines(s))
    return 0


def cmd_pack(a) -> int:
    print(evidence.render(_load(a), a.budget))
    return 0


def cmd_mode(a) -> int:
    s = _load(a)
    ex = Explainer(s, pick(a.backend, a.model), budget_tokens=a.budget, repair=not a.no_repair)
    if a.cmd == "ask":
        if a.reset:
            ex.reset_thread()
        if not a.question:
            for t in ex.history():
                print(f"Q: {t['question']}\n{t['answer']}\n")
            return 0
        _print_expl(ex.run("ask", question=" ".join(a.question), lines=a.lines), a.json)
    else:
        _print_expl(ex.run(a.cmd, lines=a.lines), a.json)
    return 0


def cmd_watch(a) -> int:
    path = resolve(a.session, cwd=a.repo or os.getcwd())
    print(f"watching {path} (Ctrl-C to stop)", file=sys.stderr)
    backend = pick(a.backend, a.model) if a.explain_every else None

    def on_event(e):
        label = e.tool if e.kind == "tool" else e.kind
        flag = " !" if e.is_error else ""
        print(f"{e.id:>5} {label:<12}{flag} {' '.join(e.text.split())[:100]}", flush=True)

    def on_delta(ex):
        print("\n" + ex.text + "\n", flush=True)

    t_end = time.time() + a.duration if a.duration else None

    def stop() -> bool:
        return t_end is not None and time.time() >= t_end

    try:
        live(
            path,
            on_event,
            on_delta,
            explainer_factory=lambda s: Explainer(s, backend, a.budget, repair=False),
            every=a.explain_every,
            interval=a.interval,
            repo=a.repo,
            stop=stop,
        )
    except KeyboardInterrupt:
        pass
    return 0


def cmd_web(a) -> int:
    from .web.server import serve

    path = resolve(a.session, cwd=a.repo or os.getcwd())
    serve(
        path,
        repo=a.repo,
        base=a.base,
        diff_file=a.diff_file,
        backend_name=a.backend,
        model=a.model,
        port=a.port,
        open_browser=not a.no_open,
        budget=a.budget,
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="readback", description=__doc__)
    p.add_argument("--version", action="version", version=f"agent-readback {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("sessions", help="list recent Claude Code / Codex sessions")
    sp.add_argument("--all", action="store_true", help="all directories, not just the current one")
    sp.add_argument("--repo", help="directory to filter on (default: current dir)")
    sp.add_argument("-n", type=int, default=10)
    sp.set_defaults(fn=cmd_sessions)

    for name, hlp in [
        ("events", "list transcript events and diff hunks with their ids (no LLM)"),
        ("pack", "print the evidence pack the model would see (no LLM)"),
    ]:
        sp = sub.add_parser(name, help=hlp)
        _session_args(sp)
        sp.add_argument("--budget", type=int, default=40_000)
        sp.set_defaults(fn=cmd_events if name == "events" else cmd_pack)

    for name, hlp in [
        ("overview", "what changed, why, the tests, and the risks"),
        ("walkthrough", "the agent's steps in order"),
        ("mechanism", "data/control flow of the change as a Mermaid diagram"),
    ]:
        sp = sub.add_parser(name, help=hlp)
        _session_args(sp)
        _llm_args(sp)
        sp.set_defaults(fn=cmd_mode)

    sp = sub.add_parser("ask", help="multi-turn follow-up questions (thread kept per session)")
    sp.add_argument("question", nargs="*", help="the question; omit to print the thread so far")
    sp.add_argument("--reset", action="store_true", help="start a new thread")
    _session_args(sp)
    _llm_args(sp)
    sp.set_defaults(fn=cmd_mode)

    sp = sub.add_parser("watch", help="tail a running session; optionally explain every N new events")
    _session_args(sp)
    _llm_args(sp)
    sp.add_argument("--explain-every", type=int, default=0, metavar="N")
    sp.add_argument("--interval", type=float, default=1.0)
    sp.add_argument(
        "--duration", type=float, default=0, help="stop after N seconds (default: run until Ctrl-C)"
    )
    sp.set_defaults(fn=cmd_watch)

    sp = sub.add_parser("web", help="local web view with clickable citations")
    _session_args(sp)
    _llm_args(sp)
    sp.add_argument("--port", type=int, default=8765)
    sp.add_argument("--no-open", action="store_true", help="don't open a browser")
    sp.set_defaults(fn=cmd_web)
    return p


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    try:
        return a.fn(a)
    except (BackendError, FileNotFoundError, ValueError, RuntimeError) as e:
        print(f"readback: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
