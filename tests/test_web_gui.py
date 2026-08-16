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
    # Regression guards for the browser<->server contract discovered by the
    # Playwright flow: the composer posts `prompt`, the server streams token
    # events as event.content, and history needs appendAssistantMessage.
    assert "prompt: prompt," in content_js
    assert "payload.text || directText" in content_js
    assert "function appendAssistantMessage" in content_js


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


def test_web_api_chat_accepts_prompt_field_from_browser(web_test_server, monkeypatch):
    """The web composer posts `prompt` (not `task`); the server must forward it."""
    import agent.web_server as web_server
    from types import SimpleNamespace

    captured = {}

    class FakeHarness:
        def __init__(self):
            self.session = SimpleNamespace(id="fake-session-id")
            self.stream_callback = None
            self.reasoning_callback = None

        def run(self, task):
            captured["task"] = task
            if self.stream_callback:
                self.stream_callback("OK")
            return "OK"

        def subscribe(self, callback):
            return lambda: None

    monkeypatch.setattr(web_server, "save_session",
                        lambda harness: SimpleNamespace(id="fake-session-saved"))
    monkeypatch.setattr(web_server.config, "set_command_policy",
                        lambda value: captured.__setitem__("policy", value))
    monkeypatch.setattr(XiaopuWebHandler, "harness", FakeHarness())

    policy = web_server.config.command_policy()
    post_data = json.dumps({
        "prompt": "只回答两个字：OK",
        "command_policy": policy,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{web_test_server}/api/chat",
        data=post_data,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        assert resp.status == 200
        assert "text/event-stream" in resp.headers.get("Content-Type", "")
        raw_text = ""
        for _ in range(50):
            line = resp.readline().decode("utf-8")
            if not line:
                break
            raw_text += line
            if "[DONE]" in line:
                break

    assert captured["task"] == "只回答两个字：OK"
    assert captured["policy"] == policy
    assert "session_saved" in raw_text


def test_web_api_tree(web_test_server):
    req = urllib.request.urlopen(f"{web_test_server}/api/tree")
    assert req.status == 200
    data = json.loads(req.read().decode("utf-8"))
    assert "projects" in data
    assert "conversations" in data
    assert "current_workspace" in data
    assert len(data["projects"]) >= 1
    p = data["projects"][0]
    assert "name" in p
    assert "path" in p
    assert "sessions" in p


def test_web_api_choose_directory(web_test_server, monkeypatch, tmp_path):
    import agent.web_server
    test_dir = str(tmp_path / "mock_workspace")
    monkeypatch.setattr(agent.web_server, "_pick_directory_native", lambda **kwargs: test_dir)

    req = urllib.request.Request(
        f"{web_test_server}/api/choose_directory",
        data=b"{}",
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["status"] == "ok"
        assert "mock_workspace" in data["path"]


def test_web_api_artifacts(web_test_server):
    req = urllib.request.urlopen(f"{web_test_server}/api/artifacts")
    assert req.status == 200
    data = json.loads(req.read().decode("utf-8"))
    assert "artifacts" in data
    assert "workspace" in data
    assert "count" in data
    assert isinstance(data["artifacts"], list)


def test_web_api_reveal_file(web_test_server, tmp_path):
    f = tmp_path / "test_artifact.pptx"
    f.write_text("dummy", encoding="utf-8")

    req = urllib.request.Request(
        f"{web_test_server}/api/reveal_file",
        data=json.dumps({"path": str(f)}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["status"] == "ok"


def test_web_api_settings(web_test_server):
    # GET settings
    req = urllib.request.urlopen(f"{web_test_server}/api/settings")
    assert req.status == 200
    data = json.loads(req.read().decode("utf-8"))
    assert "provider" in data
    assert "api_base" in data
    assert "model" in data
    assert "reasoning_effort" in data

    # POST settings
    post_req = urllib.request.Request(
        f"{web_test_server}/api/settings",
        data=json.dumps({
            "provider": "openai",
            "model": "deepseek-v4-flash",
            "reasoning_effort": "max",
            "command_policy": "ask"
        }).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(post_req) as resp:
        assert resp.status == 200
        res = json.loads(resp.read().decode("utf-8"))
        assert res["status"] == "ok"

