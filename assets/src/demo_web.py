#!/usr/bin/env python3
"""Record docs/img/demo.gif: a Playwright capture of the real web view on a recorded eval session.

usage: uv run --with playwright python assets/src/demo_web.py [--session s05] [--backend claude]
Starts `readback web`, pre-warms overview + mechanism (the server caches them), then captures
frames while clicking citations, opening the diagram and asking a follow-up question.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]


def post(base, path, body):
    req = urllib.request.Request(
        base + path, json.dumps(body).encode(), {"X-Readback": "1", "Content-Type": "application/json"}
    )
    return json.load(urllib.request.urlopen(req, timeout=600))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", default="s05")
    ap.add_argument("--backend", default="claude")
    ap.add_argument("--question", default="Why is the default roundingMode undefined instead of 'round'?")
    ap.add_argument("--port", type=int, default=8792)
    a = ap.parse_args()
    sdir = ROOT / "eval" / "sessions" / a.session
    state = tempfile.mkdtemp(prefix="readback-demo-state-")
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"), READBACK_STATE_DIR=state)
    srv = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "agent_readback",
            "web",
            "-s",
            str(sdir / "transcript.jsonl"),
            "--diff-file",
            str(sdir / "diff.patch"),
            "--backend",
            a.backend,
            "--no-open",
            "--port",
            str(a.port),
        ],
        env=env,
    )
    base = f"http://127.0.0.1:{a.port}"
    frames = Path(tempfile.mkdtemp(prefix="readback-frames-"))
    shots: list[tuple[Path, float]] = []
    try:
        time.sleep(1.5)
        for mode in ("overview", "mechanism"):
            post(base, "/api/explain", {"mode": mode})

        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome")
            pg = b.new_page(
                viewport={"width": 1280, "height": 760}, device_scale_factor=1, color_scheme="dark"
            )

            def shot(hold: float):
                f = frames / f"{len(shots):03d}.png"
                pg.screenshot(path=str(f))
                shots.append((f, hold))

            pg.goto(base)
            pg.wait_for_selector("a.cite", timeout=60000)
            pg.wait_for_timeout(600)
            shot(2.6)
            chips = pg.locator("a.cite")
            # click an event citation and a hunk citation
            for want in ("E", "H"):
                for i in range(chips.count()):
                    c = chips.nth(i)
                    if (c.inner_text() or "").startswith(want) and c.is_visible():
                        c.hover()
                        pg.wait_for_timeout(500)
                        shot(1.4)
                        c.click()
                        pg.wait_for_timeout(700)
                        shot(2.4)
                        break
            pg.keyboard.press("3")
            pg.wait_for_timeout(2500)
            shot(3.2)
            pg.keyboard.press("4")
            pg.wait_for_timeout(400)
            box = pg.locator(".askform textarea").first
            box.click()
            for ch in a.question:
                box.type(ch)
            shot(1.2)
            pg.keyboard.press("Enter")
            t0 = time.time()
            pg.wait_for_timeout(1500)
            shot(1.0)
            while time.time() - t0 < 240:
                pg.wait_for_timeout(2000)
                # answered when the thread shows a new answer with citation chips
                if pg.locator(".thread a.cite").count() > 0:
                    break
            pg.wait_for_timeout(800)
            shot(4.5)
            b.close()
    finally:
        srv.terminate()
        shutil.rmtree(state, ignore_errors=True)

    # build the GIF with per-frame durations (concat demuxer) and a shared palette
    lst = frames / "list.txt"
    lst.write_text("".join(f"file '{f}'\nduration {d}\n" for f, d in shots) + f"file '{shots[-1][0]}'\n")
    out = ROOT / "docs" / "img" / "demo.gif"
    vf = "scale=1100:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=128[p];[s1][p]paletteuse=dither=bayer:bayer_scale=4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(lst),
            "-vf",
            vf,
            "-loop",
            "0",
            str(out),
        ],
        check=True,
    )
    print(out, out.stat().st_size // 1024, "KiB,", len(shots), "frames")
    return 0


if __name__ == "__main__":
    sys.exit(main())
