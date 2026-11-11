"""The API-key backends against a local stub server: request shape (auth header, model, prompt,
cache marker) and reply parsing. No network access and no real keys are used."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from agent_readback.backends import AnthropicAPI, OpenAICompatible

SEEN: list[dict] = []


class Stub(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        SEEN.append(
            {"path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()}, "body": body}
        )
        if self.path == "/v1/messages":
            out = {
                "content": [{"type": "text", "text": "- a [E1]"}],
                "usage": {"input_tokens": 10, "cache_read_input_tokens": 5, "output_tokens": 3},
            }
        else:
            out = {
                "choices": [{"message": {"content": "- b [E1]"}}],
                "usage": {"prompt_tokens": 7, "completion_tokens": 2},
            }
        data = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def test_api_backends_request_shape_and_parsing(monkeypatch):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Stub)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-a")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", base)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-o")
    monkeypatch.setenv("OPENAI_BASE_URL", base + "/v1")
    monkeypatch.setenv("READBACK_MODEL", "stub-model")
    try:
        a = AnthropicAPI().complete("SYS", "EVIDENCE")
        o = OpenAICompatible().complete("SYS", "EVIDENCE")
    finally:
        srv.shutdown()

    assert (a.text, a.input_tokens, a.output_tokens) == ("- a [E1]", 15, 3)
    assert (o.text, o.input_tokens, o.output_tokens) == ("- b [E1]", 7, 2)
    ant, oai = SEEN
    assert ant["path"] == "/v1/messages" and ant["headers"]["x-api-key"] == "test-key-a"
    assert ant["body"]["model"] == "stub-model" and ant["body"]["system"][0]["text"] == "SYS"
    assert ant["body"]["messages"][0]["content"][0]["cache_control"] == {"type": "ephemeral"}
    assert oai["path"] == "/v1/chat/completions" and oai["headers"]["authorization"] == "Bearer test-key-o"
    assert [m["role"] for m in oai["body"]["messages"]] == ["system", "user"]
