"""Workspace registry tests."""
from pathlib import Path

from agent import workspace_store


def test_workspace_registry_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("XIAOPU_HOME", str(tmp_path))
    ws = tmp_path / "projects" / "alpha"
    ws.mkdir(parents=True)

    record = workspace_store.register_workspace(ws)
    assert record.name == "alpha"
    records = workspace_store.list_workspaces()
    assert [r.path for r in records] == [str(ws.resolve())]

    assert workspace_store.remove_workspace(ws) is True
    assert workspace_store.list_workspaces() == []


def test_register_rejects_missing_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("XIAOPU_HOME", str(tmp_path))
    try:
        workspace_store.register_workspace(tmp_path / "missing")
    except ValueError as exc:
        assert "does not exist" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_touch_reorders_last_used(tmp_path, monkeypatch):
    monkeypatch.setenv("XIAOPU_HOME", str(tmp_path))
    a = tmp_path / "a"; b = tmp_path / "b"
    a.mkdir(); b.mkdir()
    workspace_store.register_workspace(a)
    workspace_store.register_workspace(b)
    workspace_store.touch_workspace(a)
    records = workspace_store.list_workspaces()
    assert Path(records[0].path).name == "a"
