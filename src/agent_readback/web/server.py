"""Local web view: explanation on the left, transcript events and diff hunks on the right.
Citations such as [E12] / [H3] are links that scroll to and highlight the evidence.

Binds to 127.0.0.1 only. POSTs must carry the `X-Readback: 1` header (a custom header
forces a CORS preflight this server never approves, so other web pages cannot trigger
model calls), and the Host header must be local (blocks DNS rebinding).
"""

from __future__ import annotations

import json
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from urllib.parse import parse_qs, urlparse

from ..backends import BackendError, pick
from ..explain import Explainer
from ..gitdiff import attach_diff
from ..transcripts import Tail

CLIP = 6000
LOCAL_HOSTS = {"127.0.0.1", "localhost", "[::1]"}


def _clip(s: str | None) -> str | None:
    if s is None or len(s) <= CLIP:
        return s
    return s[:CLIP] + f"\n…[{len(s) - CLIP} more chars]"


class State:
    def __init__(
        self, path, repo=None, base=None, diff_file=None, backend_name=None, model=None, budget=40_000
    ):
        self.tail = Tail(path)
        self.repo, self.base, self.diff_file = repo, base, diff_file
        self.backend_name, self.model, self.budget = backend_name, model, budget
        self.lock = threading.Lock()
        self.cache: dict[tuple, dict] = {}
        self._backend = None
        self.refresh()

    def refresh(self):
        with self.lock:
            self.tail.poll()
            attach_diff(self.tail.session, repo=self.repo, base=self.base, diff_file=self.diff_file)
            return self.tail.session

    def backend(self):
        if self._backend is None:
            self._backend = pick(self.backend_name, self.model)
        return self._backend

    def session_json(self, since: int = 0) -> dict:
        s = self.refresh()
        evs = []
        for e in s.events[since:]:
            d = e.to_dict()
            d["text"], d["output"], d["patch"] = _clip(e.text), _clip(e.output), None
            evs.append(d)
        return {
            "meta": {
                k: getattr(s, k)
                for k in ("agent", "model", "cwd", "session_id", "started", "ended", "diff_source", "path")
            },
            "total_events": len(s.events),
            "since": since,
            "events": evs,
            "hunks": [h.to_dict() for h in s.hunks],
        }

    def explain(self, mode: str, question: str | None = None, lines: int | None = None) -> dict:
        s = self.refresh()
        key = (mode, len(s.events), len(s.hunks), lines)
        if mode != "ask" and key in self.cache:
            return self.cache[key]
        ex = Explainer(s, self.backend(), budget_tokens=self.budget).run(mode, question=question, lines=lines)
        d = ex.to_dict()
        if mode != "ask":
            self.cache[key] = d
        return d

    def thread(self) -> list[dict]:
        return Explainer(self.tail.session, backend=_NoBackend()).history()

    def reset(self) -> None:
        Explainer(self.tail.session, backend=_NoBackend()).reset_thread()


class _NoBackend:
    name = "none"

    def complete(self, system, prompt):  # pragma: no cover - never called
        raise BackendError("no backend")


def make_handler(state: State):
    class Handler(BaseHTTPRequestHandler):
        server_version = "readback"

        def log_message(self, fmt, *args):  # quiet
            pass

        def _local(self) -> bool:
            host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
            return host in LOCAL_HOSTS

        def _send(self, code: int, body: bytes, ctype: str = "application/json") -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code: int = 200) -> None:
            self._send(code, json.dumps(obj).encode())

        def do_GET(self):
            if not self._local():
                return self._json({"error": "forbidden host"}, HTTPStatus.FORBIDDEN)
            u = urlparse(self.path)
            if u.path in ("/", "/index.html"):
                html = resources.files("agent_readback.web").joinpath("index.html").read_bytes()
                return self._send(200, html, "text/html; charset=utf-8")
            if u.path == "/api/session":
                since = int((parse_qs(u.query).get("since") or ["0"])[0])
                return self._json(state.session_json(since))
            if u.path == "/api/thread":
                return self._json({"turns": state.thread()})
            return self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)

        def do_POST(self):
            if not self._local() or self.headers.get("X-Readback") != "1":
                return self._json({"error": "forbidden"}, HTTPStatus.FORBIDDEN)
            n = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
            except json.JSONDecodeError:
                return self._json({"error": "bad json"}, HTTPStatus.BAD_REQUEST)
            u = urlparse(self.path)
            try:
                if u.path == "/api/explain":
                    mode = body.get("mode", "overview")
                    if mode not in ("overview", "walkthrough", "mechanism"):
                        return self._json({"error": "bad mode"}, HTTPStatus.BAD_REQUEST)
                    return self._json(state.explain(mode, lines=body.get("lines")))
                if u.path == "/api/ask":
                    q = (body.get("question") or "").strip()
                    if not q:
                        return self._json({"error": "empty question"}, HTTPStatus.BAD_REQUEST)
                    return self._json(state.explain("ask", question=q, lines=body.get("lines")))
                if u.path == "/api/thread/reset":
                    state.reset()
                    return self._json({"ok": True})
            except BackendError as e:
                return self._json({"error": str(e)}, HTTPStatus.BAD_GATEWAY)
            return self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    return Handler


def make_server(path, port=8765, **kw) -> ThreadingHTTPServer:
    state = State(path, **kw)
    return ThreadingHTTPServer(("127.0.0.1", port), make_handler(state))


def serve(
    path,
    repo=None,
    base=None,
    diff_file=None,
    backend_name=None,
    model=None,
    port=8765,
    open_browser=True,
    budget=40_000,
) -> None:
    srv = make_server(
        path,
        port,
        repo=repo,
        base=base,
        diff_file=diff_file,
        backend_name=backend_name,
        model=model,
        budget=budget,
    )
    url = f"http://127.0.0.1:{srv.server_address[1]}/"
    print(f"readback web view: {url}  (Ctrl-C to stop)", flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
