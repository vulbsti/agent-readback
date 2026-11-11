#!/usr/bin/env python3
"""Read-only check against a real worktree with a real backend (complements tests/test_readonly.py,
which uses synthetic data and offline backends).

usage: readonly_check.py TRANSCRIPT REPO [--backend claude]
Hashes every file (bytes + mtime) under the transcript and REPO (including .git), runs
overview / walkthrough / mechanism / ask x2 / events / pack / web explain+ask against them,
hashes again and reports any difference. Exit code 1 if anything changed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))


def snapshot(*roots: Path) -> dict:
    out = {}
    for root in roots:
        for p in [root] if root.is_file() else sorted(root.rglob("*")):
            st = p.lstat()
            out[str(p)] = (
                hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "dir",
                st.st_mtime_ns,
            )
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("transcript")
    ap.add_argument("repo")
    ap.add_argument("--backend", default="claude")
    a = ap.parse_args()
    tr, repo = Path(a.transcript).resolve(), Path(a.repo).resolve()
    state = tempfile.mkdtemp(prefix="readback-check-")
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"), READBACK_STATE_DIR=state)
    before = snapshot(tr, repo)
    print(f"files hashed: {len(before)} (transcript + worktree incl. .git)")
    base = [sys.executable, "-m", "agent_readback"]
    common = ["-s", str(tr), "--repo", str(repo)]
    runs = [
        ["events"],
        ["pack"],
        ["overview"],
        ["walkthrough"],
        ["mechanism"],
        ["ask", "what did the agent change and where?"],
        ["ask", "which tests cover it?"],
    ]
    for r in runs:
        extra = [] if r[0] in ("events", "pack") else ["--backend", a.backend]
        t0 = time.time()
        p = subprocess.run(
            base + [r[0], *common, *extra, *r[1:]], capture_output=True, text=True, env=env, cwd=repo
        )
        meta = (p.stderr.strip().splitlines() or [""])[-1]
        print(
            f"readback {r[0]:<11} exit={p.returncode} {time.time() - t0:5.1f}s stdout={len(p.stdout):5d} chars {meta[:110]}"
        )
        if p.returncode:
            print(p.stderr[-500:])
    # web view API
    port = 8811
    srv = subprocess.Popen(
        base + ["web", *common, "--backend", a.backend, "--no-open", "--port", str(port)],
        env=env,
        cwd=repo,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        time.sleep(1.5)
        u = f"http://127.0.0.1:{port}"
        n = json.load(urllib.request.urlopen(u + "/api/session"))["total_events"]
        for path, body in [
            ("/api/explain", {"mode": "overview"}),
            ("/api/ask", {"question": "what failed first?"}),
        ]:
            req = urllib.request.Request(
                u + path, json.dumps(body).encode(), {"X-Readback": "1", "Content-Type": "application/json"}
            )
            d = json.load(urllib.request.urlopen(req, timeout=600))
            print(f"web {path:<13} events={n} cited={len(d.get('cited', []))} coverage={d.get('coverage')}")
    finally:
        srv.terminate()
    after = snapshot(tr, repo)
    changed = [k for k in before if after.get(k) != before[k]] + [k for k in after if k not in before]
    print(f"files hashed after: {len(after)}; changed or new: {len(changed)}")
    for k in changed[:20]:
        print("  CHANGED", k)
    print("RESULT:", "PASS (nothing modified)" if not changed else "FAIL")
    threading.Event()
    return 1 if changed else 0


if __name__ == "__main__":
    sys.exit(main())
