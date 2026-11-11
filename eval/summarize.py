#!/usr/bin/env python3
"""Summarize eval results into markdown tables (used for docs/eval.md).

usage: python eval/summarize.py [eval/results/v2]
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path


def load(root: Path) -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(root.glob("s*/*@*.json"))]


def explainer_cost(root: Path) -> dict[str, int]:
    out = {}
    for p in sorted(root.glob("s*/explainer.json")):
        d = json.loads(p.read_text())
        out[p.parent.name] = sum(
            (m.get("input_tokens") or 0) + (m.get("output_tokens") or 0) for m in d.values()
        )
    return out


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).parent / "results" / "v3")
    rows = load(root)
    by = defaultdict(list)
    for r in rows:
        by[(r["condition"], r["budget"])].append(r)
    conds = sorted(by, key=lambda k: (k[1] is None, k[1] or 0, k[0]))
    print(f"### Overall ({root.name})\n")
    print(
        "| condition | budget (tokens) | accuracy | per-rep accuracy | answerer input tokens (mean) | n questions |"
    )
    print("|---|---|---|---|---|---|")
    summary = {}
    for k in conds:
        rs = by[k]
        acc = sum(r["score"] for r in rs) / sum(r["n"] for r in rs)
        reps = defaultdict(lambda: [0.0, 0])
        for r in rs:
            reps[r.get("rep", 1)][0] += r["score"]
            reps[r.get("rep", 1)][1] += r["n"]
        rep_acc = [s / n for s, n in (reps[i] for i in sorted(reps))]
        tok = statistics.mean(r["answer_input_tokens"] for r in rs)
        name = f"{k[0]}@{k[1] or 'full'}"
        summary[name] = {
            "accuracy": acc,
            "per_rep": rep_acc,
            "mean_input_tokens": tok,
            "n": sum(r["n"] for r in rs),
        }
        print(
            f"| {k[0]} | {k[1] or 'full (no limit)'} | **{acc:.1%}** | {' / '.join(f'{a:.1%}' for a in rep_acc)} | {tok:,.0f} | {summary[name]['n']} |"
        )

    sessions = sorted({r["session"] for r in rows})
    print("\n### Per session (score out of 10, mean over repetitions)\n")
    print("| session | " + " | ".join(f"{c}@{b or 'full'}" for c, b in conds) + " |")
    print("|---|" + "---|" * len(conds))
    for s in sessions:
        cells = []
        for k in conds:
            rs = [r for r in by[k] if r["session"] == s]
            cells.append(f"{statistics.mean(r['score'] for r in rs):.2f}" if rs else "–")
        print(f"| {s} | " + " | ".join(cells) + " |")

    cost = explainer_cost(root)
    if cost:
        print("\n### One-time explainer cost (overview + walkthrough + mechanism, incl. repair passes)\n")
        print("| session | tokens in+out |")
        print("|---|---|")
        for s, t in cost.items():
            print(f"| {s} | {t:,} |")
    (root / "summary.json").write_text(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
