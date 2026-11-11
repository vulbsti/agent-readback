#!/usr/bin/env python3
"""Render README.md GitHub-style in light and dark (github-markdown-css + prefers-color-scheme) and save
downscaled full-page screenshots to docs/verification/readme-render-{light,dark}.png.

usage: uv run --with markdown --with playwright --with pillow python assets/src/render_readme.py
(uses the system Chrome via Playwright's channel="chrome")
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import markdown
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
CSS = "https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.8.1/github-markdown-{theme}.min.css"


def main() -> None:
    body = markdown.markdown((ROOT / "README.md").read_text(), extensions=["tables", "fenced_code"])
    out = ROOT / "docs" / "verification"
    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome")
        for theme, bg in (("light", "#ffffff"), ("dark", "#0d1117")):
            html = Path(tmp) / f"readme-{theme}.html"
            html.write_text(
                f'<!doctype html><html><head><meta charset="utf-8"><base href="file://{ROOT}/">'
                f'<link rel="stylesheet" href="{CSS.format(theme=theme)}">'
                f"<style>body{{background:{bg};margin:0}}.markdown-body{{max-width:880px;margin:24px auto;padding:0 24px}}</style>"
                f'</head><body><article class="markdown-body">{body}</article></body></html>'
            )
            page = browser.new_page(viewport={"width": 930, "height": 1000}, color_scheme=theme)
            page.goto(html.as_uri())
            page.wait_for_timeout(1500)
            shot = Path(tmp) / f"{theme}.png"
            page.screenshot(path=str(shot), full_page=True)
            im = Image.open(shot).convert("RGB")
            im = im.resize((620, int(im.size[1] * 620 / im.size[0])))
            dest = out / f"readme-render-{theme}.png"
            im.save(dest, optimize=True)
            print(dest, im.size, dest.stat().st_size // 1024, "KiB")
        browser.close()


if __name__ == "__main__":
    main()
