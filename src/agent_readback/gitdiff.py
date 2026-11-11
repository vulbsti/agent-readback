"""Collect the session's code changes as hunks, without writing to the repo.

Read-only details that matter:
  * every git call runs with --no-optional-locks and GIT_OPTIONAL_LOCKS=0;
  * `git diff` runs against a throwaway copy of the index (GIT_INDEX_FILE): even with
    --no-optional-locks, git 2.43 writes refreshed stat info for stat-dirty files back to the
    index during `git diff <base>`, so the flag alone is not enough;
  * untracked files are rendered as new-file hunks by reading them directly,
    instead of `git add -N` (which would write the index).
"""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import tempfile
from datetime import datetime, timedelta

from .model import Hunk, Session

HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@.*$")
MAX_UNTRACKED_BYTES = 200_000


# Config overrides for every git call. core.fsmonitor and hooks can run commands. git-lfs's clean
# filter stores objects under .git/lfs when git hashes a changed LFS file; with it unset, git hashes
# the raw bytes and writes nothing. Other custom clean filters cannot be disabled by wildcard
# (disclosed in SECURITY.md).
_SAFE_CONFIG = (
    "-c",
    "core.fsmonitor=false",
    "-c",
    "core.hooksPath=/dev/null",  # writing the throwaway index would still run post-index-change hooks
    "-c",
    "filter.lfs.process=",
    "-c",
    "filter.lfs.clean=",
    "-c",
    "filter.lfs.required=false",
)


def _git(repo: str, *args: str, index: str | None = None) -> str:
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0", GIT_PAGER="cat", LC_ALL="C")
    if index:
        env["GIT_INDEX_FILE"] = index
    r = subprocess.run(
        ["git", "--no-optional-locks", *_SAFE_CONFIG, "-C", repo, *args],
        capture_output=True,
        text=True,
        env=env,
        stdin=subprocess.DEVNULL,
        errors="replace",
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or f"git {' '.join(args)} failed")
    return r.stdout


def is_git_repo(path: str) -> bool:
    try:
        return _git(path, "rev-parse", "--is-inside-work-tree").strip() == "true"
    except (RuntimeError, FileNotFoundError, NotADirectoryError):
        return False


def parse_unified(diff: str, start_index: int = 1) -> list[Hunk]:
    """Split a unified diff (git or plain) into Hunk objects with ids H<n>."""
    hunks: list[Hunk] = []
    file, status = "?", "modified"
    cur: list[str] | None = None
    meta: dict = {}

    def flush():
        if cur is not None:
            body = "\n".join(cur)
            added = sum(1 for ln in cur[1:] if ln.startswith("+"))
            removed = sum(1 for ln in cur[1:] if ln.startswith("-"))
            hunks.append(
                Hunk(
                    id=f"H{start_index + len(hunks)}",
                    file=file,
                    header=cur[0],
                    text=body,
                    old_start=meta.get("old", 0),
                    new_start=meta.get("new", 0),
                    added=added,
                    removed=removed,
                    status=status,
                )
            )

    old_path = None
    for ln in diff.splitlines():
        if ln.startswith("diff --git "):
            flush()
            cur = None
            status = "modified"
            m = re.match(r"diff --git a/(.*) b/(.*)$", ln)
            file = m.group(2) if m else ln[11:]
            continue
        if ln.startswith("--- "):
            flush()
            cur = None
            old_path = ln[4:].strip()
            continue
        if ln.startswith("+++ "):
            new = ln[4:].strip()
            if new == "/dev/null":
                status = "deleted"
                file = old_path[2:] if old_path and old_path.startswith("a/") else (old_path or file)
            else:
                file = new[2:] if new.startswith("b/") else new
                if old_path == "/dev/null":
                    status = "added"
            continue
        if ln.startswith("new file mode"):
            status = "added"
            continue
        if ln.startswith("deleted file mode"):
            status = "deleted"
            continue
        if ln.startswith("rename to "):
            status = "renamed"
            file = ln[10:]
            continue
        m = HUNK_RE.match(ln)
        if m or ln.startswith("@@"):
            flush()
            cur = [ln]
            meta = {"old": int(m.group(1)), "new": int(m.group(3))} if m else {}
            continue
        if cur is not None and (ln[:1] in (" ", "+", "-", "\\") or ln == ""):
            cur.append(ln)
    flush()
    return hunks


def _untracked_diff(repo: str, index: str | None = None) -> str:
    out = []
    names = _git(repo, "ls-files", "--others", "--exclude-standard", "-z", index=index).split("\0")
    for name in filter(None, names):
        path = os.path.join(repo, name)
        try:
            st = os.lstat(path)  # never follow links: a link could point at a secret or at /dev/zero
            if stat.S_ISLNK(st.st_mode):  # render as git does: mode 120000, the link text as the body
                target = os.readlink(path)
                out.append(
                    f"diff --git a/{name} b/{name}\nnew file mode 120000\n--- /dev/null\n+++ b/{name}\n"
                    f"@@ -0,0 +1 @@\n+{target}\n\\ No newline at end of file"
                )
                continue
            if not stat.S_ISREG(st.st_mode):
                continue  # devices, FIFOs, sockets: never read
            if st.st_size > MAX_UNTRACKED_BYTES:
                out.append(
                    f"diff --git a/{name} b/{name}\nnew file mode 100644\n--- /dev/null\n+++ b/{name}\n@@ -0,0 +1 @@\n+(large file omitted)"
                )
                continue
            fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            with os.fdopen(fd, "rb") as fh:
                data = fh.read(MAX_UNTRACKED_BYTES + 1)
        except OSError:
            continue
        if b"\0" in data[:8000]:
            continue  # binary
        lines = data.decode("utf-8", "replace").splitlines()
        body = "\n".join("+" + ln for ln in lines)
        out.append(
            f"diff --git a/{name} b/{name}\nnew file mode 100644\n--- /dev/null\n+++ b/{name}\n@@ -0,0 +1,{len(lines)} @@\n{body}"
        )
    return "\n".join(out)


def auto_base(repo: str, started: str | None, ended: str | None = None, slack_s: int = 600) -> str:
    """Pick the diff base: the parent of the first commit made during the session window
    (started .. ended + slack_s, by committer date), or HEAD if no commit falls inside it.
    Commits made after the session are ignored, so they cannot become the base."""
    if not started:
        return "HEAD"
    try:
        t = datetime.fromisoformat(started.replace("Z", "+00:00"))
        args = ["rev-list", "--reverse", f"--since={t.strftime('%Y-%m-%dT%H:%M:%S%z')}"]
        if ended:
            u = datetime.fromisoformat(ended.replace("Z", "+00:00")) + timedelta(seconds=slack_s)
            args.append(f"--until={u.strftime('%Y-%m-%dT%H:%M:%S%z')}")
        revs = _git(repo, *args, "HEAD").split()
    except (RuntimeError, ValueError):
        return "HEAD"
    if not revs:
        return "HEAD"
    try:
        return _git(repo, "rev-parse", f"{revs[0]}^").strip()
    except RuntimeError:  # first commit of the repo
        return _git(repo, "hash-object", "-t", "tree", "/dev/null").strip()


def git_diff(repo: str, base: str = "HEAD", include_untracked: bool = True) -> str:
    # `git diff` refreshes stat-dirty index entries and, even with --no-optional-locks (git 2.43),
    # writes them back to the index. Run it against a throwaway copy so .git/index is never written.
    with tempfile.TemporaryDirectory(prefix="readback-index-") as tmp:
        index = None
        try:
            real = _git(repo, "rev-parse", "--path-format=absolute", "--git-path", "index").strip()
            if os.path.isfile(real):
                index = os.path.join(tmp, "index")
                # copy2 keeps the index mtime: git's racy-entry check compares it with file mtimes,
                # and a fresh mtime would hide same-size edits made in the second of the last write
                shutil.copy2(real, index)
        except RuntimeError:
            index = None
        # --no-textconv: show real bytes, and never let a cachetextconv driver write refs/notes/textconv
        diff = _git(
            repo, "diff", "--no-color", "--no-ext-diff", "--no-textconv", "--find-renames", base, index=index
        )
        extra = _untracked_diff(repo, index) if include_untracked else ""
    if extra:
        diff = diff + ("\n" if diff and not diff.endswith("\n") else "") + extra
    return diff


def transcript_diff(session: Session) -> str:
    """Fallback when there is no repo: concatenate the patches the transcript carries."""
    return "\n".join(e.patch for e in session.events if e.writes and e.patch)


def attach_diff(
    session: Session,
    repo: str | None = None,
    base: str | None = None,
    diff_file: str | None = None,
) -> Session:
    """Fill session.hunks from (in order of preference) a diff file, the git
    worktree, or the edits recorded in the transcript."""
    text, source = "", "none"
    if diff_file:
        with open(diff_file, "rb") as fh:
            text, source = fh.read().decode("utf-8", "replace"), "file"
    else:
        repo = repo or session.cwd
        if repo and os.path.isdir(repo) and is_git_repo(repo):
            b = base if base and base != "auto" else auto_base(repo, session.started, session.ended)
            text, source = git_diff(repo, b), f"git:{b[:12]}"
        if not text.strip():
            text = transcript_diff(session)
            source = "transcript" if text.strip() else "none"
    session.hunks = parse_unified(text)
    session.diff_source = source
    _link_edits(session)
    return session


def _link_edits(session: Session) -> None:
    """Make file paths relative to the repo so events and hunks name files the same way."""
    root = session.cwd.rstrip("/") + "/" if session.cwd else None
    for e in session.events:
        if root:
            e.files = [f[len(root) :] if f.startswith(root) else f for f in e.files]
            e.text = e.text.replace(root, "")
            if e.output:
                e.output = e.output.replace(root, "")
    for h in session.hunks:
        if root and h.file.startswith(root):
            h.file = h.file[len(root) :]


def hunks_for_event(session: Session, eid: str) -> list[str]:
    """Hunks in files the given event wrote."""
    ev = session.event(eid)
    if not ev or not ev.writes:
        return []
    return [h.id for h in session.hunks if h.file in ev.files]
