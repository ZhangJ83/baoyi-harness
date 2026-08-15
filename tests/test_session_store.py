"""Session-store and UI capability tests."""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

from agent.state import RunState
from agent import session_store


class DummyHarness:
    def __init__(self):
        self.state = RunState()
        self.messages = []
        self.llm = None
        self.session = None
        self.task_spec = None
        self.active_goal = None


def test_snapshot_save_list_load_restore_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("XIAOPU_HOME", str(tmp_path))
    h = DummyHarness()
    h.messages = [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "做一个 PPT"},
        {"role": "assistant", "content": "好的"},
        {"role": "tool", "tool_call_id": "t1", "content": "result"},
    ]
    h.state.record_fact("task_root", "tasks/demo")
    h.state.content_brief = '{"schema":"test"}'
    h.state.record_change("deck:edit")

    record = session_store.save_session(h, title="演示任务")
    records = session_store.list_sessions()
    assert records and records[0].id == record.id
    assert records[0].title == "演示任务"

    payload = session_store.load_session(record.id)
    assert payload["messages"][3]["role"] == "tool"
    assert payload["facts"]["task_root"] == "tasks/demo"

    h2 = DummyHarness()
    report = session_store.restore_harness(h2, payload)
    assert "已恢复" in report
    assert len(h2.messages) == 4
    assert h2.state.facts["task_root"] == "tasks/demo"
    assert h2.state.mutation_epoch == 1


def test_export_session_writes_markdown(tmp_path, monkeypatch):
    monkeypatch.setenv("XIAOPU_HOME", str(tmp_path))
    h = DummyHarness()
    h.messages = [{"role": "user", "content": "hello"}]
    record = session_store.save_session(h)
    target = tmp_path / "out.md"
    exported = session_store.export_session(record.id, target)
    text = exported.read_text(encoding="utf-8")
    assert "hello" in text and exported == target


def test_delete_session(tmp_path, monkeypatch):
    monkeypatch.setenv("XIAOPU_HOME", str(tmp_path))
    h = DummyHarness()
    h.messages = [{"role": "user", "content": "x"}]
    record = session_store.save_session(h)
    assert session_store.delete_session(record.id) is True
    assert session_store.load_session(record.id) is None


def test_cli_lists_sessions_without_credential(tmp_path, monkeypatch):
    monkeypatch.setenv("XIAOPU_HOME", str(tmp_path))
    from agent import main

    with patch.object(main.sys, "argv", ["xiaopu", "--list-sessions", "--workspace", str(tmp_path)]):
        assert main.main() == 0


def test_cli_export_unknown_session_fails(tmp_path, monkeypatch):
    monkeypatch.setenv("XIAOPU_HOME", str(tmp_path))
    from agent import main

    with patch.object(main.sys, "argv", ["xiaopu", "--export", "missing-session", str(tmp_path / "o.md")]), \
         patch.object(main.sys, "stderr", open(os.devnull, "w", encoding="utf-8")):
        assert main.main() == 1


def test_hybrid_completer_routes_slash_and_paths(tmp_path):
    from agent.tui import HybridCompleter
    from prompt_toolkit.document import Document

    completer = HybridCompleter()
    slash = list(completer.get_completions(Document("/sta", 4), None))
    assert any(c.text == "/status" for c in slash)

    old = os.getcwd()
    try:
        os.chdir(tmp_path)
        (tmp_path / "file.txt").write_text("x", encoding="utf-8")
        path = list(completer.get_completions(Document("fi", 2), None))
        assert any(c.text for c in path)
    finally:
        os.chdir(old)
