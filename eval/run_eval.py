#!/usr/bin/env python3
"""Comprehension eval: does reading readback's explanation beat reading the raw transcript + diff?

For each recorded session (eval/sessions/sNN) and each token budget B:
  explainer@B  context = readback overview + walkthrough + mechanism (generated once, blind to the
               questions), then readback's evidence pack filling whatever budget is left.
  raw@B        context = the raw transcript rendered as plain text + the raw diff, cut to B
               (diff first, up to 40% of B, then the transcript's head and tail).
  raw@full     the whole raw transcript + diff, no budget (a ceiling, reported for honesty).
A fresh `claude -p` (no tools, no session persistence) answers the 10 questions from the context
alone. A separate fresh judge grades each answer against the key without seeing the condition.

usage: python eval/run_eval.py [--sessions s01,s02] [--budgets 2000,6000] [--answer-model M] [--judge-model M]
Results are cached in eval/results/; delete a file there to recompute it.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import random
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "src"))

from agent_readback import evidence  # noqa: E402
from agent_readback.backends import ClaudeCLI  # noqa: E402
from agent_readback.explain import Explainer, open_session  # noqa: E402

CPT = evidence.CHARS_PER_TOKEN
RESULTS = ROOT / "results" / "v3"


# -- model calls ---------------------------------------------------------------------------
def claude(system: str, prompt: str, model: str, timeout: int = 900) -> dict:
    cmd = [
        "claude",
        "-p",
        "--output-format",
        "json",
        "--tools",
        "",
        "--no-session-persistence",
        "--setting-sources",
        "",
        "--strict-mcp-config",
        "--system-prompt",
        system,
        "--model",
        model,
    ]
    for attempt in range(3):
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, cwd=tmp, timeout=timeout)
        try:
            d = json.loads(r.stdout)
            if not d.get("is_error"):
                u = d.get("usage") or {}
                tokens = sum(
                    u.get(k) or 0
                    for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
                )
                return {
                    "text": d.get("result", ""),
                    "input_tokens": tokens,
                    "output_tokens": u.get("output_tokens"),
                }
        except json.JSONDecodeError:
            pass
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"claude failed: {r.stderr[:300]} {r.stdout[:300]}")


def parse_json_block(text: str):
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    raw = m.group(1) if m else text[text.find("[") : text.rfind("]") + 1]
    return json.loads(raw)


# -- contexts --------------------------------------------------------------------------------
def raw_text(sdir: Path) -> tuple[str, str]:
    """Plain-text rendering of the raw transcript (every message, tool input and output, untrimmed)."""
    lines = []
    for raw in (sdir / "transcript.jsonl").read_text().splitlines():
        r = json.loads(raw)
        if "message" in r:  # Claude Code
            c = r["message"].get("content")
            role = r["message"].get("role", r.get("type"))
            if isinstance(c, str):
                lines.append(f"{role}: {c}")
                continue
            for b in c or []:
                t = b.get("type")
                if t == "text":
                    lines.append(f"{role}: {b['text']}")
                elif t == "thinking":
                    lines.append(f"{role} (thinking): {b['thinking']}")
                elif t == "tool_use":
                    lines.append(f"tool_call {b['name']}: {json.dumps(b.get('input'), ensure_ascii=False)}")
                elif t == "tool_result":
                    cc = b.get("content")
                    if isinstance(cc, list):
                        cc = "\n".join(x.get("text", "") for x in cc if isinstance(x, dict))
                    lines.append(f"tool_result{' (error)' if b.get('is_error') else ''}: {cc}")
        else:  # Codex
            p = r.get("payload") or {}
            pt = p.get("type")
            if pt == "message":
                lines.append(f"{p['role']}: " + "".join(x.get("text", "") for x in p.get("content") or []))
            elif pt == "reasoning":
                lines.append(
                    "assistant (reasoning): " + " ".join(x.get("text", "") for x in p.get("summary") or [])
                )
            elif pt in ("function_call", "custom_tool_call"):
                lines.append(f"tool_call {p.get('name')}: {p.get('arguments') or p.get('input')}")
            elif pt and pt.endswith("_output"):
                lines.append(f"tool_result: {json.dumps(p.get('output'), ensure_ascii=False)}")
            elif pt == "item_completed":
                it = p.get("item") or {}
                if it.get("type") == "CommandExecution":
                    lines.append(
                        f"command {it.get('command')} exit={it.get('exit_code')}: {it.get('aggregated_output')}"
                    )
                elif it.get("type") == "FileChange":
                    lines.append(f"file_change: {json.dumps(it.get('changes'), ensure_ascii=False)}")
    return "\n".join(lines), (sdir / "diff.patch").read_text()


def cut(text: str, chars: int) -> str:
    if len(text) <= chars:
        return text
    head = int(chars * 0.5)
    return text[:head] + "\n…[truncated]…\n" + text[-(chars - head) :]


def raw_context(sdir: Path, budget: int | None) -> str:
    tr, diff = raw_text(sdir)
    if budget is None:
        return f"## RAW TRANSCRIPT\n{tr}\n\n## RAW DIFF\n{diff}"
    total = budget * CPT
    d = cut(diff, min(len(diff), int(total * 0.4)))
    return f"## RAW DIFF\n{d}\n\n## RAW TRANSCRIPT\n{cut(tr, total - len(d) - 40)}"


def explainer_notes(sid: str, sdir: Path) -> dict:
    cache = RESULTS / sid / "explainer.json"
    if cache.exists():
        return json.loads(cache.read_text())
    s = open_session(str(sdir / "transcript.jsonl"), diff_file=str(sdir / "diff.patch"))
    ex = Explainer(s, ClaudeCLI())
    out = {}
    for mode in ("overview", "walkthrough", "mechanism"):
        out[mode] = ex.run(mode).to_dict()
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(out, indent=1))
    return out


def explainer_context(sid: str, sdir: Path, budget: int) -> str:
    notes = explainer_notes(sid, sdir)
    head = "\n\n".join(
        f"## {m.upper()}\n{notes[m]['text']}" for m in ("overview", "walkthrough", "mechanism")
    )
    head = cut(head, budget * CPT)
    room = budget * CPT - len(head) - 60
    if room > 800:
        s = open_session(str(sdir / "transcript.jsonl"), diff_file=str(sdir / "diff.patch"))
        pack = evidence.render(s, room // CPT)[:room]
        head += "\n\n## EVIDENCE (ids cited above)\n" + pack
    return head


# -- answer + judge --------------------------------------------------------------------------
ANSWER_SYS = (
    "You answer factual questions about what a coding agent did in a session, using ONLY the provided "
    'material. If the material does not contain the answer, reply "unknown". Be specific and short.'
)
JUDGE_SYS = "You grade answers against an answer key strictly and consistently. Output only JSON."


def answer(context: str, questions: list[dict], model: str) -> dict:
    qs = "\n".join(f"{q['id']}: {q['question']}" for q in questions)
    prompt = (
        f"<MATERIAL>\n{context}\n</MATERIAL>\n\nAnswer each question in one or two sentences. Output a JSON "
        f'array of objects {{"id":..., "answer":...}} in a ```json block.\n\n{qs}'
    )
    r = claude(ANSWER_SYS, prompt, model)
    r["answers"] = {a["id"]: a["answer"] for a in parse_json_block(r["text"])}
    r["context_tokens_est"] = len(context) // CPT
    return r


def judge(questions: list[dict], answers: dict, model: str) -> dict:
    items = [
        {
            "id": q["id"],
            "question": q["question"],
            "key": q["answer"],
            "must_contain": q.get("accept", ""),
            "answer": answers.get(q["id"], ""),
        }
        for q in questions
    ]
    prompt = (
        "Grade each answer. score 1 = correct (contains the key facts; wording may differ), 0.5 = partially "
        "correct (some key facts, nothing wrong), 0 = wrong, missing, or 'unknown'. Output a ```json array of "
        '{"id":..., "score":..., "why": short}.\n\n' + json.dumps(items, indent=1, ensure_ascii=False)
    )
    r = claude(JUDGE_SYS, prompt, model)
    return {g["id"]: g for g in parse_json_block(r["text"])}


def run_condition(
    sid: str,
    sdir: Path,
    cond: str,
    budget: int | None,
    qs: list[dict],
    a_model: str,
    j_model: str,
    rep: int = 1,
) -> dict:
    tag = f"{cond}@{budget or 'full'}" + (f".r{rep}" if rep > 1 else "")
    cache = RESULTS / sid / f"{tag}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    ctx = explainer_context(sid, sdir, budget) if cond == "explainer" else raw_context(sdir, budget)
    a = answer(ctx, qs, a_model)
    g = judge(qs, a["answers"], j_model)
    res = {
        "session": sid,
        "condition": cond,
        "budget": budget,
        "context_tokens_est": a["context_tokens_est"],
        "answer_input_tokens": a["input_tokens"],
        "answers": a["answers"],
        "grades": g,
        "score": sum(float(g.get(q["id"], {}).get("score", 0)) for q in qs),
        "n": len(qs),
        "rep": rep,
    }
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print(f"{sid} {tag}: {res['score']}/{res['n']} ({res['answer_input_tokens']} tok)", flush=True)
    return res


def main() -> int:
    global RESULTS
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--sessions", default=",".join(sorted(p.name for p in (ROOT / "sessions").glob("s[0-9]*")))
    )
    ap.add_argument("--budgets", default="2000,6000")
    ap.add_argument("--answer-model", default="claude-sonnet-5-5")
    ap.add_argument("--judge-model", default="claude-sonnet-5-5")
    ap.add_argument("--no-full", action="store_true")
    ap.add_argument("--reps", type=int, default=1, help="answer+judge repetitions per condition")
    ap.add_argument("--out", default=str(RESULTS), help="results directory (cache)")
    a = ap.parse_args()
    RESULTS = Path(a.out)
    budgets = [int(b) for b in a.budgets.split(",")]
    jobs = []
    for sid in a.sessions.split(","):
        sdir = ROOT / "sessions" / sid
        qs = json.loads((sdir / "questions.json").read_text())
        for rep in range(1, a.reps + 1):
            for b in budgets:
                jobs += [(sid, sdir, "explainer", b, qs, rep), (sid, sdir, "raw", b, qs, rep)]
            if not a.no_full:
                jobs.append((sid, sdir, "raw", None, qs, rep))
    random.Random(0).shuffle(jobs)
    # generate explainer notes first (one per session), then fan out
    with cf.ThreadPoolExecutor(6) as pool:
        list(pool.map(lambda s: explainer_notes(s, ROOT / "sessions" / s), a.sessions.split(",")))
    with cf.ThreadPoolExecutor(6) as pool:
        futs = [pool.submit(run_condition, *j[:5], a.answer_model, a.judge_model, j[5]) for j in jobs]
        for f in cf.as_completed(futs):
            f.result()
    return 0


if __name__ == "__main__":
    sys.exit(main())
