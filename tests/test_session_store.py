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


def test_save_session_preserves_prior_history_after_task_reset(tmp_path, monkeypatch):
    monkeypatch.setenv("XIAOPU_HOME", str(tmp_path))
    from types import SimpleNamespace

    h = DummyHarness()
    h.session = SimpleNamespace(id="sess-keep-history")
    h.messages = [
        {"role": "user", "content": "旧任务"},
        {"role": "assistant", "content": "旧回复"},
    ]
    first = session_store.save_session(h)

    # A new task package resets model-local messages; the durable file must not
    # lose the earlier user-visible turns.
    h.messages = [
        {"role": "user", "content": "新任务"},
        {"role": "assistant", "content": "新回复"},
    ]
    second = session_store.save_session(h)

    assert second.id == first.id
    assert second.created_at == first.created_at
    assert second.turn_count == 2
    payload = session_store.load_session(second.id)
    assert [m["content"] for m in payload["messages"]] == [
        "旧任务", "旧回复", "新任务", "新回复",
    ]

    # Same-task continuation (current messages still contain the prior prefix)
    # appends only the new tail instead of duplicating history.
    h.messages = [
        {"role": "user", "content": "旧任务"},
        {"role": "assistant", "content": "旧回复"},
        {"role": "user", "content": "新任务"},
        {"role": "assistant", "content": "新回复"},
        {"role": "user", "content": "继续"},
        {"role": "assistant", "content": "好的"},
    ]
    third = session_store.save_session(h)
    payload = session_store.load_session(third.id)
    assert [m["content"] for m in payload["messages"]] == [
        "旧任务", "旧回复", "新任务", "新回复", "继续", "好的",
    ]


def test_session_lifecycle_archive_trash_restore_rename_pin(tmp_path, monkeypatch):
    monkeypatch.setenv("XIAOPU_HOME", str(tmp_path))
    from types import SimpleNamespace

    h = DummyHarness()
    h.session = SimpleNamespace(id="sess-lifecycle")
    h.messages = [{"role": "user", "content": "原始任务"}, {"role": "assistant", "content": "好的"}]
    record = session_store.save_session(h)

    # Rename locks the title against later auto-derivation.
    assert session_store.rename_session(record.id, "手动标题")
    assert session_store.list_sessions()[0].title == "手动标题"
    h.messages = [{"role": "user", "content": "继续"}]
    session_store.save_session(h)
    assert session_store.list_sessions()[0].title == "手动标题"

    # Pin survives save_session.
    assert session_store.set_session_pinned(record.id, True)
    assert session_store.list_sessions()[0].pinned is True
    session_store.save_session(h)
    assert session_store.list_sessions()[0].pinned is True

    # Archive hides from active and moves to the archive view.
    assert session_store.archive_session(record.id)
    assert session_store.list_sessions(view="active") == []
    archived = session_store.list_sessions(view="archive")
    assert [s.id for s in archived] == [record.id]
    assert archived[0].status == "archive"

    # Trash moves archive/active into the recoverable trash.
    assert session_store.trash_session(record.id)
    assert session_store.list_sessions(view="archive") == []
    trashed = session_store.list_sessions(view="trash")
    assert [s.id for s in trashed] == [record.id]
    assert session_store.load_session(record.id)["trashed_at"]

    # Restore returns to active and clears lifecycle stamps.
    assert session_store.restore_session(record.id)
    active = session_store.list_sessions(view="active")
    assert [s.id for s in active] == [record.id]
    assert "trashed_at" not in session_store.load_session(record.id)

    # Purge permanently deletes.
    assert session_store.purge_session(record.id)
    assert session_store.load_session(record.id) is None


def test_session_batch_and_expired_purge(tmp_path, monkeypatch):
    monkeypatch.setenv("XIAOPU_HOME", str(tmp_path))
    from types import SimpleNamespace

    ids = []
    for i in range(3):
        h = DummyHarness()
        h.session = SimpleNamespace(id=f"sess-batch-{i}")
        h.messages = [{"role": "user", "content": f"task {i}"}]
        ids.append(session_store.save_session(h).id)

    result = session_store.batch_session_action(ids, "archive")
    assert len(result["ok"]) == 3
    assert not session_store.list_sessions(view="active")

    result = session_store.batch_session_action(ids, "restore")
    assert len(result["ok"]) == 3
    assert len(session_store.list_sessions(view="active")) == 3

    # An old trash entry is purged; a fresh one survives.
    session_store.trash_session(ids[0])
    old_path = session_store._locate_session_file(ids[0])
    payload = session_store._read_payload(old_path)
    payload["trashed_at"] = "2000-01-01T00:00:00+00:00"
    session_store._write_payload(old_path, payload)
    session_store.trash_session(ids[1])

    assert session_store.purge_expired_sessions(days=30) == 1
    assert session_store.load_session(ids[0]) is None
    assert session_store.load_session(ids[1]) is not None


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
    from agent.cli import HybridCompleter
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
