import json
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from agent.generation_budget_proxy import ProxyConfig, extract_output_tokens, make_server


def test_usage_extraction_handles_all_preregistered_shapes():
    assert extract_output_tokens("openai_responses", b'{"usage":{"output_tokens":7}}') == 7
    assert extract_output_tokens("openai_chat", b'{"usage":{"completion_tokens":8}}') == 8
    assert extract_output_tokens("anthropic_messages", b'{"usage":{"output_tokens":9}}') == 9
    sse = b'data: {"type":"response.completed","response":{"usage":{"output_tokens":11}}}\n\ndata: [DONE]\n'
    assert extract_output_tokens("openai_responses", sse) == 11


def test_proxy_rewrites_and_commits_against_local_fake_upstream(tmp_path):
    observed = {}

    class Upstream(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            return

        def do_POST(self):
            length = int(self.headers["Content-Length"])
            observed["body"] = json.loads(self.rfile.read(length))
            raw = json.dumps({"usage": {"completion_tokens": 40}, "choices": []}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    upstream = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
    upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    upstream_thread.start()
    state = tmp_path / "gateway.json"
    proxy = make_server(
        "127.0.0.1",
        0,
        ProxyConfig(
            upstream_base=f"http://127.0.0.1:{upstream.server_port}",
            state_path=state,
            cap=50,
        ),
    )
    proxy_thread = threading.Thread(target=proxy.serve_forever, daemon=True)
    proxy_thread.start()
    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{proxy.server_port}/v1/chat/completions",
            data=json.dumps({"model": "fake", "max_tokens": 100}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request) as response:
            assert response.status == 200
        assert observed["body"]["max_tokens"] == 50
        ledger = json.loads(state.read_text(encoding="utf-8"))
        assert ledger["committed_output_tokens"] == 40
        assert ledger["violations"] == []
    finally:
        proxy.shutdown()
        upstream.shutdown()


def test_proxy_fails_closed_when_success_response_has_no_usage(tmp_path):
    class Upstream(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            return

        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            raw = b'{"choices":[]}'
            self.send_response(200)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    upstream = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
    threading.Thread(target=upstream.serve_forever, daemon=True).start()
    state = tmp_path / "gateway.json"
    proxy = make_server(
        "127.0.0.1",
        0,
        ProxyConfig(f"http://127.0.0.1:{upstream.server_port}", state, 25),
    )
    threading.Thread(target=proxy.serve_forever, daemon=True).start()
    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{proxy.server_port}/v1/chat/completions",
            data=b'{"model":"fake"}',
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(request)
            assert False, "expected HTTP 502"
        except urllib.error.HTTPError as exc:
            assert exc.code == 502
        ledger = json.loads(state.read_text(encoding="utf-8"))
        assert ledger["committed_output_tokens"] == 25
        assert ledger["violations"][0]["kind"] == "missing_authoritative_output_usage"
    finally:
        proxy.shutdown()
        upstream.shutdown()
