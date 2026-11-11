"""Synthetic transcript builders. No real transcript content is used in tests."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest


def claude_records(cwd: str, sid: str = "11111111-2222-3333-4444-555555555555") -> list[dict]:
    base = {"sessionId": sid, "cwd": cwd, "version": "2.0.0", "gitBranch": "main", "isSidechain": False}
    ts = iter(f"2026-01-01T10:00:{i:02d}.000Z" for i in range(60))

    def user(content, **kw):
        return {
            **base,
            "type": "user",
            "timestamp": next(ts),
            "message": {"role": "user", "content": content},
            **kw,
        }

    def asst(*blocks):
        return {
            **base,
            "type": "assistant",
            "timestamp": next(ts),
            "message": {"role": "assistant", "model": "test-model", "content": list(blocks)},
        }

    return [
        {"type": "file-history-snapshot", "snapshot": {}},
        user("Make add() reject booleans and add a test."),
        user("<system-reminder>injected</system-reminder>", isMeta=True),
        asst(
            {"type": "thinking", "thinking": "Need to look at calc.py first."},
            {"type": "tool_use", "id": "t1", "name": "Read", "input": {"file_path": f"{cwd}/calc.py"}},
        ),
        user([{"type": "tool_result", "tool_use_id": "t1", "content": "def add(a, b):\n    return a + b\n"}]),
        asst(
            {
                "type": "tool_use",
                "id": "t2",
                "name": "Edit",
                "input": {
                    "file_path": f"{cwd}/calc.py",
                    "old_string": "    return a + b",
                    "new_string": "    if isinstance(a, bool) or isinstance(b, bool):\n        raise TypeError('bool')\n    return a + b",
                },
            }
        ),
        user(
            [{"type": "tool_result", "tool_use_id": "t2", "content": "The file has been updated."}],
            toolUseResult={
                "filePath": f"{cwd}/calc.py",
                "structuredPatch": [
                    {
                        "oldStart": 1,
                        "oldLines": 2,
                        "newStart": 1,
                        "newLines": 4,
                        "lines": [
                            " def add(a, b):",
                            "+    if isinstance(a, bool) or isinstance(b, bool):",
                            "+        raise TypeError('bool')",
                            "     return a + b",
                        ],
                    }
                ],
            },
        ),
        asst(
            {
                "type": "tool_use",
                "id": "t3",
                "name": "Bash",
                "input": {"command": "python -m pytest -q", "description": "run tests"},
            }
        ),
        user(
            [
                {
                    "type": "tool_result",
                    "tool_use_id": "t3",
                    "is_error": True,
                    "content": "Exit code 1\n1 failed: test_add_bool",
                }
            ]
        ),
        asst({"type": "text", "text": "The test expected ValueError; switching the test to TypeError."}),
        asst(
            {
                "type": "tool_use",
                "id": "t4",
                "name": "Write",
                "input": {"file_path": f"{cwd}/test_calc.py", "content": "def test_add_bool():\n    pass\n"},
            }
        ),
        user([{"type": "tool_result", "tool_use_id": "t4", "content": "File created"}]),
        asst({"type": "text", "text": "add() now raises TypeError for bools; tests pass."}),
    ]


def codex_records(cwd: str) -> list[dict]:
    ts = "2026-01-01T10:00:00.000Z"

    def ri(payload):
        return {"timestamp": ts, "type": "response_item", "payload": payload}

    return [
        {
            "timestamp": ts,
            "type": "session_meta",
            "payload": {"id": "cdx-0001", "cwd": cwd, "cli_version": "0.1"},
        },
        {"timestamp": ts, "type": "turn_context", "payload": {"model": "test-codex", "cwd": cwd}},
        ri(
            {
                "type": "message",
                "role": "developer",
                "content": [{"type": "input_text", "text": "system stuff"}],
            }
        ),
        ri(
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "<environment_context>x</environment_context>"}],
            }
        ),
        ri(
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "Rename slow() to fast()."}],
            }
        ),
        # classic shell call
        ri(
            {
                "type": "function_call",
                "name": "shell",
                "call_id": "c1",
                "arguments": json.dumps({"command": ["bash", "-lc", "grep -n slow *.py"]}),
            }
        ),
        ri(
            {
                "type": "function_call_output",
                "call_id": "c1",
                "output": json.dumps({"output": "app.py:1:def slow():", "metadata": {"exit_code": 0}}),
            }
        ),
        # classic apply_patch
        ri(
            {
                "type": "custom_tool_call",
                "name": "apply_patch",
                "call_id": "c2",
                "input": "*** Begin Patch\n*** Update File: app.py\n@@\n-def slow():\n+def fast():\n*** End Patch",
            }
        ),
        ri({"type": "custom_tool_call_output", "call_id": "c2", "output": "Success"}),
        # code-mode exec with a failing command folded in from item_completed
        ri(
            {
                "type": "custom_tool_call",
                "name": "exec",
                "call_id": "c3",
                "input": 'text(await tools.exec_command({cmd:"node t.js"}))',
            }
        ),
        {
            "timestamp": ts,
            "type": "event_msg",
            "payload": {
                "type": "item_completed",
                "item": {
                    "type": "CommandExecution",
                    "command": ["/bin/bash", "-lc", "node t.js"],
                    "aggregated_output": "boom",
                    "exit_code": 1,
                },
            },
        },
        ri(
            {
                "type": "custom_tool_call_output",
                "call_id": "c3",
                "output": [{"type": "input_text", "text": "Script completed"}],
            }
        ),
        # code-mode exec mixing a web fetch with a shell command: both must stay visible
        ri(
            {
                "type": "custom_tool_call",
                "name": "exec",
                "call_id": "c4",
                "input": 'text(await tools.web__run({open:[{ref_id:"https://example.com/spec"}]})); '
                'text(await tools.exec_command({cmd:"ls"}))',
            }
        ),
        {
            "timestamp": ts,
            "type": "event_msg",
            "payload": {
                "type": "item_completed",
                "item": {
                    "type": "CommandExecution",
                    "command": ["/bin/bash", "-lc", "ls"],
                    "aggregated_output": "app.py",
                    "exit_code": 0,
                },
            },
        },
        ri(
            {
                "type": "custom_tool_call_output",
                "call_id": "c4",
                "output": [
                    {"type": "input_text", "text": "Script completed\nWall time 1.0 seconds\nOutput:\n"},
                    {"type": "input_text", "text": "spec page: functions must be fast"},
                ],
            }
        ),
        ri(
            {
                "type": "reasoning",
                "summary": [{"type": "summary_text", "text": "t.js still imports slow"}],
                "encrypted_content": "",
            }
        ),
        ri(
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "Renamed; t.js still fails."}],
            }
        ),
    ]


def write_jsonl(path: Path, records: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in records))
    return path


def git(repo: Path, *args: str, date: str | None = None) -> str:
    env = dict(os.environ)
    if date:
        env.update(GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, env=env
    ).stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A git repo where the 'agent' committed once and left uncommitted + untracked changes."""
    r = tmp_path / "work"
    r.mkdir()
    git(r, "init", "-q", "-b", "main")
    git(r, "config", "user.email", "t@example.com")
    git(r, "config", "user.name", "t")
    (r / "calc.py").write_text("def add(a, b):\n    return a + b\n")
    (r / "util.py").write_text("X = 1\n")
    # a cached textconv driver: a plain `git diff` would write refs/notes/textconv/up into .git
    (r / ".gitattributes").write_text("notes.txt diff=up\n")
    (r / "notes.txt").write_text("alpha\n")
    git(r, "config", "diff.up.textconv", "tr a-z A-Z <")
    git(r, "config", "diff.up.cachetextconv", "true")
    git(r, "add", "-A")
    git(r, "-c", "commit.gpgsign=false", "commit", "-q", "-m", "init", date="2025-01-01T00:00:00Z")
    (r / "calc.py").write_text(
        "def add(a, b):\n    if isinstance(a, bool) or isinstance(b, bool):\n        raise TypeError('bool')\n    return a + b\n"
    )
    (r / "test_calc.py").write_text("def test_add_bool():\n    pass\n")
    (r / "notes.txt").write_text("beta\n")
    # an untracked link to a file outside the worktree: its target text must never reach the pack
    (tmp_path / "outside-secret.txt").write_text("TOP-SECRET-TOKEN\n")
    (r / "link.txt").symlink_to(tmp_path / "outside-secret.txt")
    # a repo hook that git runs whenever it writes an index, including readback's throwaway copy
    hook = r / ".git" / "hooks" / "post-index-change"
    hook.write_text('#!/bin/sh\necho ran >> "$(git rev-parse --git-dir)/hook-ran"\n')
    hook.chmod(0o755)
    # stat-dirty but content-identical: a plain `git diff` would refresh and rewrite .git/index here
    st = (r / "util.py").stat()
    os.utime(r / "util.py", ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
    return r
