#!/usr/bin/env python3
"""Render docs/img/eval-{light,dark}.svg from eval/results/v3/summary.json (run eval/summarize.py first)."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
S = json.loads((ROOT / "eval" / "results" / "v3" / "summary.json").read_text())
THEMES = {
    "light": dict(
        bg="#ffffff", fg="#1f2328", muted="#59636e", grid="#d1d9e0", a="#0969da", b="#8c959f", ref="#9a6700"
    ),
    "dark": dict(
        bg="#0d1117", fg="#e6edf3", muted="#9198a1", grid="#30363d", a="#4493f8", b="#656c76", ref="#d29922"
    ),
}
W, H = 760, 330
X0, Y0, PH = 70, 50, 210  # plot origin (top-left), plot height


def y(v):  # v in 0..1
    return Y0 + PH * (1 - v)


def render(c):
    o = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
        "font-family=\"-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif\">",
        f'<rect width="100%" height="100%" fill="{c["bg"]}"/>',
        f'<text x="{X0}" y="26" font-size="15" font-weight="600" fill="{c["fg"]}">Answer accuracy at the same reading budget (60 questions × 2 runs)</text>',
    ]
    for t in (0, 0.25, 0.5, 0.75, 1.0):
        o.append(
            f'<line x1="{X0}" x2="{W - 150}" y1="{y(t)}" y2="{y(t)}" stroke="{c["grid"]}" stroke-width="1"/>'
        )
        o.append(
            f'<text x="{X0 - 8}" y="{y(t) + 4}" font-size="12" text-anchor="end" fill="{c["muted"]}">{int(t * 100)}%</text>'
        )
    groups = [("2,000 tokens", "explainer@2000", "raw@2000"), ("6,000 tokens", "explainer@6000", "raw@6000")]
    bw, gap = 64, 10
    for gi, (label, ka, kb) in enumerate(groups):
        gx = X0 + 50 + gi * 250
        for j, (k, col, _name) in enumerate(
            [(ka, c["a"], "readback"), (kb, c["b"], "raw transcript + diff")]
        ):
            v = S[k]["accuracy"]
            x = gx + j * (bw + gap)
            o.append(f'<rect x="{x}" y="{y(v)}" width="{bw}" height="{Y0 + PH - y(v)}" rx="3" fill="{col}"/>')
            o.append(
                f'<text x="{x + bw / 2}" y="{y(v) - 7}" font-size="13" font-weight="600" text-anchor="middle" fill="{c["fg"]}">{v:.0%}</text>'
            )
        o.append(
            f'<text x="{gx + bw + gap / 2}" y="{Y0 + PH + 22}" font-size="13" text-anchor="middle" fill="{c["fg"]}">{label}</text>'
        )
    full = S["raw@full"]
    o.append(
        f'<line x1="{X0}" x2="{W - 150}" y1="{y(full["accuracy"])}" y2="{y(full["accuracy"])}" stroke="{c["ref"]}" stroke-width="1.5" stroke-dasharray="5 4"/>'
    )
    o.append(
        f'<text x="{W - 144}" y="{y(full["accuracy"]) - 2}" font-size="12" fill="{c["ref"]}">whole raw session</text>'
    )
    o.append(
        f'<text x="{W - 144}" y="{y(full["accuracy"]) + 13}" font-size="12" fill="{c["ref"]}">{full["accuracy"]:.0%} · ~{full["mean_input_tokens"] / 1000:.0f}k tokens</text>'
    )
    lx = W - 144
    for i, (col, name) in enumerate([(c["a"], "readback notes"), (c["b"], "raw, truncated")]):
        o.append(f'<rect x="{lx}" y="{Y0 + 110 + i * 22}" width="12" height="12" rx="2" fill="{col}"/>')
        o.append(f'<text x="{lx + 18}" y="{Y0 + 121 + i * 22}" font-size="12" fill="{c["fg"]}">{name}</text>')
    o.append(
        f'<text x="{X0}" y="{H - 14}" font-size="11" fill="{c["muted"]}">6 real Claude Code / Codex sessions · fresh answerer, blind judge · details: docs/eval.md</text>'
    )
    o.append("</svg>")
    return "\n".join(o)


if __name__ == "__main__":
    for name, c in THEMES.items():
        p = ROOT / "docs" / "img" / f"eval-{name}.svg"
        p.write_text(render(c))
        print(p)
