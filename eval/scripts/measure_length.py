#!/usr/bin/env python3
"""Measure explanation length: non-blank lines and terminal rows when wrapped at 80 / 120 columns.

usage: measure_length.py [eval/results/v2] [EXTRA_OUTPUT.txt ...]
"""

from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path


def rows(text: str, width: int) -> int:
    return sum(
        max(1, len(textwrap.wrap(line, width)) if line.strip() else 1) for line in text.strip().splitlines()
    )


def stats(text: str) -> tuple[int, int, int]:
    return len([ln for ln in text.splitlines() if ln.strip()]), rows(text, 120), rows(text, 80)


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "eval/results/v3")
    by_mode: dict[str, list[tuple[str, tuple[int, int, int]]]] = {}
    for p in sorted(root.glob("s*/explainer.json")):
        for mode, d in json.loads(p.read_text()).items():
            by_mode.setdefault(mode, []).append((p.parent.name, stats(d["text"])))
    print("| mode | session | non-blank lines | rows @120 cols | rows @80 cols |")
    print("|---|---|---|---|---|")
    for mode, items in by_mode.items():
        for sid, (n, r120, r80) in items:
            print(f"| {mode} | {sid} | {n} | {r120} | {r80} |")
    print("\n| mode | non-blank lines (min–max) | rows @120 (min–max) | rows @80 (min–max) |")
    print("|---|---|---|---|")
    for mode, items in by_mode.items():
        cols = list(zip(*[s for _, s in items], strict=True))
        print(
            f"| {mode} | {min(cols[0])}–{max(cols[0])} | {min(cols[1])}–{max(cols[1])} | {min(cols[2])}–{max(cols[2])} |"
        )
    for extra in sys.argv[2:]:
        n, r120, r80 = stats(Path(extra).read_text())
        print(f"\n{Path(extra).name}: {n} non-blank lines, {r120} rows @120, {r80} rows @80")
    return 0


if __name__ == "__main__":
    sys.exit(main())
