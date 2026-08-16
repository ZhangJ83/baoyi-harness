"""Unit tests for Xiaopu Web GUI Server & REST/SSE APIs."""
import json
import threading
import time
import urllib.request
import urllib.parse
import pytest

from agent.harness import Harness
from agent.web_server import ThreadingHTTPServer, XiaopuWebHandler


@pytest.fixture(scope="module")
def web_test_server():
    XiaopuWebHandler.harness = Harness(interactive=True)
    server = ThreadingHTTPServer(("127.0.0.1", 8769), XiaopuWebHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.5)
    yield "http://127.0.0.1:8769"
    server.shutdown()


def test_web_static_index_html(web_test_server):
    req = urllib.request.urlopen(f"{web_test_server}/")
    assert req.status == 200
    assert "text/html" in req.headers.get("Content-Type", "")
    content = req.read().decode("utf-8")
    assert "小朴" in content
    assert "activity-drawer" in content
    assert "prompt-input" in content


def test_web_static_css_and_js(web_test_server):
    req_css = urllib.request.urlopen(f"{web_test_server}/style.css")
    assert req_css.status == 200
    assert "text/css" in req_css.headers.get("Content-Type", "")

    req_js = urllib.request.urlopen(f"{web_test_server}/app.js")
    assert req_js.status == 200
    assert "application/javascript" in req_js.headers.get("Content-Type", "")
    content_js = req_js.read().decode("utf-8")
    assert "Thought process" in content_js


def test_web_api_config(web_test_server):
    req = urllib.request.urlopen(f"{web_test_server}/api/config")
    assert req.status == 200
    data = json.loads(req.read().decode("utf-8"))
    assert "known_models" in data
    assert "current_model" in data


def test_web_api_workspaces(web_test_server):
    req = urllib.request.urlopen(f"{web_test_server}/api/workspaces")
    assert req.status == 200
    data = json.loads(req.read().decode("utf-8"))
    assert "workspaces" in data
    assert "current" in data


def test_web_api_sessions_and_chat_stream(web_test_server):
    # Test getting sessions
    req = urllib.request.urlopen(f"{web_test_server}/api/sessions")
    assert req.status == 200
    data = json.loads(req.read().decode("utf-8"))
    assert "sessions" in data

    # Test sending a mock chat request with SSE streaming
    post_data = json.dumps({"task": "只回答两个字：OK"}).encode("utf-8")
    req_chat = urllib.request.Request(
        f"{web_test_server}/api/chat",
        data=post_data,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req_chat, timeout=30) as resp:
        assert resp.status == 200
        assert "text/event-stream" in resp.headers.get("Content-Type", "")
        # Read lines until [DONE] or first events
        collected = []
        for _ in range(50):
            line = resp.readline().decode("utf-8")
            if not line:
                break
            collected.append(line)
            if "[DONE]" in line:
                break
        raw_text = "".join(collected)
        assert "data:" in raw_text

