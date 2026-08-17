import os
import subprocess
import sys
import time

import pytest


def _has_display() -> bool:
    if sys.platform == "win32":
        return True
    return bool(os.environ.get("DISPLAY"))


def test_cli_smoke_pipe_ok():
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    p = subprocess.Popen(
        [sys.executable, "-m", "agent.cli"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    out_bytes, err_bytes = p.communicate(
        input="只回答两个字：OK\n/exit\n".encode("utf-8"),
        timeout=30,
    )
    out = out_bytes.decode("utf-8", errors="replace")
    assert p.returncode == 0
    if os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or os.getenv("BAOYI_API_KEY"):
        assert "OK" in out or "ok" in out.lower()
    else:
        assert "CONFIGURATION ERROR" in out or "再见" in out or "报一" in out


@pytest.mark.gui
@pytest.mark.skipif(not _has_display(), reason="GUI tests require an active $DISPLAY or X11/Xvfb environment")
def test_gui_smoke_interaction_ok():
    import customtkinter as ctk
    from agent.gui import AgentGUI

    root = ctk.CTk()
    root.withdraw()  # headless / hidden window
    gui = AgentGUI(root)

    gui.input.insert("1.0", "只回答两个字：OK")
    gui._send()

    start = time.monotonic()
    while gui.running and time.monotonic() - start < 30:
        gui._drain_events()
        gui._drain_approvals()
        root.update()
        time.sleep(0.1)

    # Process remaining event queue
    for _ in range(5):
        gui._drain_events()
        root.update()
        time.sleep(0.05)

    assert gui.running is False

    def get_all_texts(widget) -> list[str]:
        texts = []
        if isinstance(widget, (ctk.CTkLabel, ctk.CTkButton)):
            try:
                t = widget.cget("text")
                if t:
                    texts.append(str(t))
            except Exception:
                pass
        for ch in getattr(widget, "winfo_children", lambda: [])():
            texts.extend(get_all_texts(ch))
        return texts

    collected_texts = get_all_texts(gui.chat)
    full_chat_text = "\n".join(collected_texts)
    root.destroy()

    if os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or os.getenv("BAOYI_API_KEY"):
        assert "OK" in full_chat_text or "ok" in full_chat_text.lower()
    else:
        assert "CONFIGURATION ERROR" in full_chat_text or len(full_chat_text) > 0


def test_gui_workspace_sessions_and_resume(tmp_path):
    from agent.harness import Harness
    from agent.session_store import save_session, list_sessions, load_session, restore_harness

    ws1 = tmp_path / "workspace_a"
    ws2 = tmp_path / "workspace_b"
    ws1.mkdir()
    ws2.mkdir()

    h1 = Harness(interactive=True)
    h1.workspace = str(ws1)
    h1.messages = [
        {"role": "user", "content": "第一轮问题"},
        {"role": "assistant", "content": "第一轮回答", "reasoning_content": "分析中..."},
    ]
    rec1 = save_session(h1, title="会话A")

    h2 = Harness(interactive=True)
    h2.workspace = str(ws2)
    h2.messages = [
        {"role": "user", "content": "B工作区问题"},
        {"role": "assistant", "content": "B工作区回答"},
    ]
    rec2 = save_session(h2, title="会话B")

    # Verify workspace filtering
    sessions_a = list_sessions(workspace=str(ws1))
    sessions_b = list_sessions(workspace=str(ws2))

    assert any(s.id == rec1.id for s in sessions_a)
    assert not any(s.id == rec2.id for s in sessions_a)
    assert any(s.id == rec2.id for s in sessions_b)

    # Test resuming session A into a new harness
    h_resumed = Harness(interactive=True)
    payload = load_session(rec1.id)
    report = restore_harness(h_resumed, payload)

    assert "会话" in report
    assert len(h_resumed.messages) == 2
    assert h_resumed.messages[0]["content"] == "第一轮问题"
    assert h_resumed.messages[1]["reasoning_content"] == "分析中..."
    assert h_resumed.session.id == rec1.id
