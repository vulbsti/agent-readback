import json
import time

from conftest import claude_records, codex_records, git, write_jsonl

from agent_readback.gitdiff import attach_diff, auto_base, git_diff
from agent_readback.transcripts import Tail, load, resolve


def test_claude_folds_tool_results_and_skips_injected(tmp_path):
    s = load(write_jsonl(tmp_path / "c.jsonl", claude_records("/w")))
    kinds = [(e.kind, e.tool) for e in s.events]
    assert kinds == [
        ("user", None),
        ("reasoning", None),
        ("tool", "Read"),
        ("tool", "Edit"),
        ("tool", "Bash"),
        ("assistant", None),
        ("tool", "Write"),
        ("assistant", None),
    ]
    read, edit, bash = s.events[2], s.events[3], s.events[4]
    assert "return a + b" in read.output  # result attached to its call by tool_use_id
    assert (
        edit.writes
        and edit.patch.startswith("--- a//w/calc.py")
        and "+        raise TypeError('bool')" in edit.patch
    )
    assert bash.is_error and bash.result_line > bash.line
    assert s.model == "test-model" and s.cwd == "/w" and s.started.startswith("2026-01-01T10:00")


def test_codex_classic_and_code_mode_calls(tmp_path, monkeypatch):
    uuid = "01a1ab92-0b4a-72f2-a35d-f983bb3d26f7"
    path = write_jsonl(tmp_path / "codex" / f"rollout-2026-01-01T10-00-00-{uuid}.jsonl", codex_records("/w"))
    monkeypatch.setenv("READBACK_CODEX_DIR", str(tmp_path / "codex"))
    monkeypatch.setenv("READBACK_CLAUDE_DIR", str(tmp_path / "none"))
    assert resolve(uuid[:8]) == str(path) == resolve(uuid)  # `-s <id-prefix>` works for Codex files
    s = load(path)
    assert [e.kind for e in s.events] == ["user", "tool", "tool", "tool", "tool", "reasoning", "assistant"]
    user, shell, patch, exec_ = s.events[:4]
    assert user.text == "Rename slow() to fast()."  # developer + environment_context dropped
    assert (
        shell.text == "$ grep -n slow *.py" and shell.output == "app.py:1:def slow():" and not shell.is_error
    )
    assert patch.writes and patch.files == ["app.py"]
    assert exec_.tool == "exec_command" and exec_.text.startswith("$ node t.js") and exec_.is_error
    assert "boom" in exec_.output
    web = s.events[4]
    assert web.text.startswith("web__run(") and "$ ls" in web.text  # non-shell tool call kept
    assert "spec page: functions must be fast" in web.output  # script output not dropped
    assert s.model == "test-codex" and s.session_id == "cdx-0001"


def test_live_tail_sees_only_complete_lines_and_late_results(tmp_path):
    recs = claude_records("/w")
    path = tmp_path / "live.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in recs[:4]))
    tail = Tail(str(path), "claude")
    assert tail.poll() == 3  # user, thinking, Read call
    assert tail.session.events[2].output is None
    with open(path, "a") as fh:  # the agent is mid-write: half a line
        line = json.dumps(recs[4])
        fh.write(line[:25])
    assert tail.poll() == 0
    with open(path, "a") as fh:
        fh.write(line[25:] + "\n" + "".join(json.dumps(r) + "\n" for r in recs[5:]))
    tail.poll()
    assert tail.session.events[2].output.startswith("def add")  # result arrived later, attached to E3
    assert len(tail.session.events) == len(load(path).events)


def test_diff_base_is_parent_of_first_commit_made_during_session(repo, tmp_path):
    init = git(repo, "rev-parse", "HEAD").strip()
    git(repo, "add", "calc.py")
    git(repo, "-c", "commit.gpgsign=false", "commit", "-q", "-m", "agent commit", date="2026-01-01T10:00:30Z")
    s = load(write_jsonl(tmp_path / "c.jsonl", claude_records(str(repo))))
    assert auto_base(str(repo), s.started, s.ended) == init
    attach_diff(s, repo=str(repo))
    files = {h.file: h.status for h in s.hunks}
    assert files == {
        "calc.py": "modified",
        "link.txt": "added",
        "notes.txt": "modified",
        "test_calc.py": "added",
    }
    linked = git_diff(str(repo), init)
    assert "new file mode 120000" in linked and "TOP-SECRET-TOKEN" not in linked  # links are not followed
    assert "+beta" in git_diff(str(repo), init)  # real bytes, not the textconv output ("BETA")
    assert s.events[3].files == ["calc.py"]  # event paths made repo-relative, matching hunks
    (repo / "later.txt").write_text("unrelated\n")
    git(repo, "add", "later.txt")
    git(repo, "-c", "commit.gpgsign=false", "commit", "-q", "-m", "weeks later", date="2026-02-01T09:00:00Z")
    assert auto_base(str(repo), s.started, s.ended) == init  # a post-session commit is not the base
    # a session that committed nothing: the unrelated later commit must not become the base
    assert auto_base(str(repo), "2026-01-01T11:00:00Z", "2026-01-01T11:05:00Z") == "HEAD"
    # racy entry: a same-size edit in the second the index was written must still show up
    git(repo, "-c", "commit.gpgsign=false", "commit", "-q", "-am", "index written now")
    (repo / "later.txt").write_text("UNRELATED\n")
    time.sleep(1.1)
    assert "+UNRELATED" in git_diff(str(repo))


def test_transcript_diff_fallback_without_repo(tmp_path):
    s = load(write_jsonl(tmp_path / "c.jsonl", claude_records(str(tmp_path / "gone"))))
    attach_diff(s)
    assert s.diff_source == "transcript"
    assert any("raise TypeError" in h.text for h in s.hunks)
