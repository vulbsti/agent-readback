#!/usr/bin/env python3
"""Render docs/img/architecture-{light,dark}.svg from one template (python assets/src/architecture.py)."""

from pathlib import Path

THEMES = {
    "light": dict(
        bg="#ffffff",
        fg="#1f2328",
        muted="#59636e",
        line="#8c959f",
        box="#f6f8fa",
        stroke="#d1d9e0",
        accent="#0969da",
        accent_bg="#ddf4ff",
        warn="#9a6700",
        warn_bg="#fff8c5",
        ro="#1a7f37",
        ro_bg="#dafbe1",
    ),
    "dark": dict(
        bg="#0d1117",
        fg="#e6edf3",
        muted="#9198a1",
        line="#656c76",
        box="#151b23",
        stroke="#3d444d",
        accent="#4493f8",
        accent_bg="#0c2d6b",
        warn="#d29922",
        warn_bg="#3b2e00",
        ro="#3fb950",
        ro_bg="#0f2d1a",
    ),
}

W, H = 1200, 560


def box(x, y, w, h, title, sub="", kind="box"):
    fill, stroke, tcol = {
        "box": ("box", "stroke", "fg"),
        "accent": ("accent_bg", "accent", "fg"),
        "warn": ("warn_bg", "warn", "fg"),
        "ro": ("ro_bg", "ro", "fg"),
    }[kind]
    s = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{{{fill}}}" stroke="{{{stroke}}}" stroke-width="1.5"/>'
    ty = y + (h / 2 if not sub else h / 2 - 9)
    s += f'<text x="{x + w / 2}" y="{ty + 5}" text-anchor="middle" class="t" fill="{{{tcol}}}">{title}</text>'
    for i, line in enumerate(sub.split("|") if sub else []):
        s += f'<text x="{x + w / 2}" y="{ty + 24 + i * 17}" text-anchor="middle" class="s" fill="{{muted}}">{line}</text>'
    return s


def arrow(x1, y1, x2, y2, label="", dashed=False, lx=None, ly=None):
    d = ' stroke-dasharray="5 4"' if dashed else ""
    s = f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{{line}}" stroke-width="1.6" marker-end="url(#a)"{d}/>'
    if label:
        s += f'<text x="{lx if lx is not None else (x1 + x2) / 2}" y="{ly if ly is not None else (y1 + y2) / 2 - 7}" text-anchor="middle" class="l" fill="{{muted}}">{label}</text>'
    return s


def svg() -> str:
    p = []
    # executor side
    p.append('<text x="40" y="44" class="h" fill="{fg}">executor (untouched)</text>')
    p.append(box(40, 64, 220, 70, "coding agent", "Claude Code · Codex CLI", "warn"))
    p.append(box(90, 190, 170, 64, "transcript .jsonl", "growing while it runs"))
    p.append(box(40, 300, 220, 64, "worktree + .git", "the agent's changes"))
    p.append(arrow(175, 134, 175, 186, "appends", lx=215, ly=166))
    p.append(arrow(62, 134, 62, 296, "edits", lx=40, ly=226))
    # read-only boundary
    p.append(
        '<rect x="300" y="24" width="640" height="420" rx="12" fill="none" stroke="{ro}" stroke-width="1.6" stroke-dasharray="7 5"/>'
    )
    p.append(
        '<text x="318" y="48" class="h" fill="{ro}">readback: read-only (open "rb", git on a throwaway index copy)</text>'
    )
    p.append(box(330, 180, 170, 84, "parser", "incremental tail|Claude · Codex", "box"))
    p.append(box(330, 296, 170, 76, "git diff", "auto base · untracked|or transcript patches", "box"))
    p.append(arrow(260, 222, 326, 222, "read", lx=293, ly=214))
    p.append(arrow(260, 332, 326, 332, "read", lx=293, ly=324))
    p.append(box(540, 230, 160, 84, "session", "events E1…En|hunks H1…Hm", "accent"))
    p.append(arrow(500, 222, 536, 256))
    p.append(arrow(500, 334, 536, 292))
    p.append(box(740, 230, 170, 84, "evidence pack", "id-tagged, budgeted|errors + diffs first", "box"))
    p.append(arrow(700, 272, 736, 272))
    p.append(box(740, 80, 170, 84, "citation check", "unknown ids stripped|1 repair pass", "box"))
    p.append(box(540, 80, 160, 84, "explanation", "cites [E#] / [H#]|coverage checked", "accent"))
    p.append(arrow(740, 122, 704, 122))
    # model, outside the boundary
    p.append(box(990, 230, 180, 84, "LLM backend", "claude -p · codex exec|Anthropic · OpenAI · cmd", "box"))
    p.append(arrow(910, 262, 986, 262, "prompt", lx=948, ly=254))
    p.append(arrow(986, 290, 912, 290, "answer", lx=948, ly=306))
    p.append(
        '<text x="1080" y="340" text-anchor="middle" class="s" fill="{muted}">no tools (codex: tools disabled)</text>'
    )
    p.append(arrow(825, 230, 825, 168))
    # outputs
    p.append('<text x="330" y="484" class="h" fill="{fg}">you</text>')
    for i, (t, s) in enumerate(
        [
            ("CLI", "overview · walkthrough|mechanism · ask · watch"),
            ("Claude Code plugin", "/agent-readback:readback|in a second window"),
            ("web view", "click [E12] → event|click [H3] → diff hunk"),
        ]
    ):
        x = 330 + i * 205
        p.append(box(x, 470 + 0, 185, 70, t, s, "box"))
    p.append('<path d="M540,140 H520 V454 M422,454 H832" fill="none" stroke="{line}" stroke-width="1.6"/>')
    for x in (422, 627, 832):
        p.append(arrow(x, 454, x, 467))
    p.append('<text x="1080" y="376" text-anchor="middle" class="s" fill="{muted}">ask threads →</text>')
    p.append(
        '<text x="1080" y="393" text-anchor="middle" class="s" fill="{muted}">~/.local/state/agent-readback</text>'
    )
    body = "\n".join(p)
    head = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="'
        "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif\">"
        '<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        '<path d="M0,0 L10,5 L0,10 z" fill="{line}"/></marker></defs>'
        "<style>.t{font-size:15px;font-weight:600}.s{font-size:12px}.l{font-size:12px}.h{font-size:14px;font-weight:600}</style>"
        '<rect width="100%" height="100%" fill="{bg}"/>'
    )
    return head + body + "</svg>"


if __name__ == "__main__":
    out = Path(__file__).resolve().parents[2] / "docs" / "img"
    out.mkdir(parents=True, exist_ok=True)
    tpl = svg()
    for name, colors in THEMES.items():
        s = tpl
        for k, v in colors.items():
            s = s.replace("{" + k + "}", v)
        (out / f"architecture-{name}.svg").write_text(s)
        print(out / f"architecture-{name}.svg")
