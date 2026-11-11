#!/usr/bin/env python3
"""Turn one finished sandbox run into eval/sessions/<id>/ (sanitized transcript, diff, meta).

usage: collect.py ID --agent claude|codex --transcript PATH --sandbox DIR --repo NAME
                  --repo-url URL --license SPDX --task-file FILE [--venv DIR] [--notes TEXT]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sanitize  # noqa: E402


def git(sb: str, *args: str) -> str:
    return subprocess.run(["git", "-C", sb, *args], capture_output=True, text=True, check=True).stdout


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("id")
    ap.add_argument("--agent", required=True, choices=["claude", "codex"])
    ap.add_argument("--transcript", required=True)
    ap.add_argument("--sandbox", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--repo-url", required=True)
    ap.add_argument("--license", required=True)
    ap.add_argument("--task-file", required=True)
    ap.add_argument("--venv")
    ap.add_argument("--notes", default="")
    a = ap.parse_args()

    out = HERE.parent / "sessions" / a.id
    out.mkdir(parents=True, exist_ok=True)
    sb = str(Path(a.sandbox).resolve())
    subs = [(sb, f"/sandbox/{a.repo}")]
    if a.venv:
        subs.append((str(Path(a.venv).resolve()), "/opt/venv"))
    subs.sort(key=lambda s: -len(s[0]))

    n = sanitize.sanitize(Path(a.transcript), out / "transcript.jsonl", a.agent, subs)
    base = git(sb, "rev-parse", "HEAD").strip()
    # the sandbox is a throwaway copy, so staging there is fine; this captures untracked files too
    git(sb, "add", "-A")
    diff = git(sb, "diff", "--cached", "--no-color", base)
    (out / "diff.patch").write_text(sanitize.rewrite(diff, subs))
    (out / "task.md").write_text(sanitize.rewrite(Path(a.task_file).read_text(), subs))

    recs = [json.loads(x) for x in (out / "transcript.jsonl").read_text().splitlines()]
    if a.agent == "claude":
        model = next((r["message"].get("model") for r in recs if r.get("type") == "assistant"), None)
        version = next((r.get("version") for r in recs if r.get("version")), None)
        tools = sum(
            1
            for r in recs
            if r.get("type") == "assistant"
            for b in r["message"].get("content", [])
            if isinstance(b, dict) and b.get("type") == "tool_use"
        )
    else:
        model = next((r["payload"].get("model") for r in recs if r.get("type") == "turn_context"), None)
        version = next(
            (r["payload"].get("cli_version") for r in recs if r.get("type") == "session_meta"), None
        )
        tools = sum(1 for r in recs if r.get("type") == "event_msg")
    meta = {
        "id": a.id,
        "agent": a.agent,
        "agent_version": version,
        "model": model,
        "repo": a.repo,
        "repo_url": a.repo_url,
        "license": a.license,
        "base_commit": base,
        "task": (out / "task.md").read_text().strip(),
        "recorded_at": time.strftime("%Y-%m-%d"),
        "num_transcript_lines": n,
        "tool_calls": tools,
        "diff_lines": diff.count("\n"),
        "notes": a.notes,
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")
    print(
        json.dumps(
            {
                k: meta[k]
                for k in ("id", "agent", "model", "repo", "num_transcript_lines", "tool_calls", "diff_lines")
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
