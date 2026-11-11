"""The read-only guarantee: a full explainer session leaves the observed transcripts and the
observed worktree (including .git) byte-for-byte unchanged, with unchanged mtimes.

"Full session" = for a Claude Code transcript AND a Codex transcript: every CLI command and mode,
a multi-turn ask, `watch` (live tail with delta explanations), the web view's page and JSON API,
and a backend that deliberately tries to write into its working directory. The worktree fixture
contains a stat-dirty tracked file, which a plain `git diff`/`git status` would use to rewrite
.git/index (it does so even with --no-optional-locks); this test fails if git_diff stops using a
throwaway copy of the index.

Known exception (disclosed in SECURITY.md, not exercised here): with core.splitIndex=true, git
refreshes the mtime of .git/sharedindex.* whenever it reads the index; the bytes do not change.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
import urllib.request
from pathlib import Path

from conftest import claude_records, codex_records, write_jsonl

from agent_readback import cli
from agent_readback.web.server import make_server


def snapshot(*roots: Path) -> dict[str, tuple[str, int]]:
    """sha256 + mtime_ns of every file under the roots (dirs included as entries)."""
    out = {}
    for root in roots:
        paths = [root] if root.is_file() else sorted(root.rglob("*"))
        for p in paths:
            st = p.lstat()
            digest = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "dir"
            out[str(p)] = (digest, st.st_mtime_ns)
    return out


def exercise(transcript: Path, capsys) -> None:
    run = lambda *a: cli.main([*a, "-s", str(transcript)])  # noqa: E731
    assert run("events") == 0
    assert run("pack") == 0
    for mode in ("overview", "walkthrough", "mechanism"):
        assert run(mode, "--backend", "fake") == 0
    assert run("ask", "--backend", "fake", "why TypeError?") == 0
    assert run("ask", "--backend", "fake", "which test?") == 0
    assert run("ask", "--backend", "fake") == 0  # prints the thread
    assert run("overview", "--backend", "command") == 0  # the backend that tries to write
    assert (
        run("watch", "--backend", "fake", "--explain-every", "2", "--interval", "0.05", "--duration", "0.4")
        == 0
    )
    out = capsys.readouterr().out
    assert "[E1]" in out and "Q: why TypeError?" in out

    srv = make_server(str(transcript), port=0, backend_name="fake")
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        assert b"agent-readback" in urllib.request.urlopen(base + "/").read()
        assert json.load(urllib.request.urlopen(base + "/api/session"))["total_events"] > 3
        for path, body in [
            ("/api/explain", {"mode": "overview"}),
            ("/api/explain", {"mode": "mechanism"}),
            ("/api/ask", {"question": "what?"}),
            ("/api/thread/reset", {}),
        ]:
            req = urllib.request.Request(
                base + path,
                json.dumps(body).encode(),
                {"X-Readback": "1", "Content-Type": "application/json"},
            )
            assert urllib.request.urlopen(req).status == 200
        assert urllib.request.urlopen(base + "/api/thread").status == 200
    finally:
        srv.shutdown()


def test_full_session_changes_nothing(repo, tmp_path, monkeypatch, capsys):
    projects, codex_dir = tmp_path / "claude-projects", tmp_path / "codex-sessions"
    claude_tr = write_jsonl(
        projects / "-work" / "11111111-2222-3333-4444-555555555555.jsonl", claude_records(str(repo))
    )
    codex_tr = write_jsonl(
        codex_dir / "2026" / "01" / "01" / "rollout-x-cdx-0001.jsonl", codex_records(str(repo))
    )
    monkeypatch.setenv("READBACK_CLAUDE_DIR", str(projects))
    monkeypatch.setenv("READBACK_CODEX_DIR", str(codex_dir))
    monkeypatch.setenv("READBACK_STATE_DIR", str(tmp_path / "state"))
    # a "model" that tries to write into whatever directory it runs in
    evil = tmp_path / "evil_model.py"
    evil.write_text(
        "import sys, pathlib\npathlib.Path('PWNED').write_text('x')\nsys.stdin.read()\nprint('- did a thing [E1]')\n"
    )
    monkeypatch.setenv("READBACK_CMD", f"{sys.executable} {evil}")
    monkeypatch.chdir(repo)  # run from inside the observed repo, as the plugin does

    before = snapshot(claude_tr, codex_tr, repo)

    assert cli.main(["sessions"]) == 0
    exercise(claude_tr, capsys)
    exercise(codex_tr, capsys)

    after = snapshot(claude_tr, codex_tr, repo)
    assert after == before
    assert not (repo / "PWNED").exists()
    assert os.path.exists(tmp_path / "state" / "threads")  # explainer state lives in its own dir
