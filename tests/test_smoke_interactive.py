import os
import subprocess
import sys
import time

import pytest


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
    assert "OK" in out or "ok" in out.lower()


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

    assert "OK" in full_chat_text or "ok" in full_chat_text.lower()

