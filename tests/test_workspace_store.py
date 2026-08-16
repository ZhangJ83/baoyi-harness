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


def test_workspace_lifecycle_rename_pin_archive_remove(tmp_path, monkeypatch):
    monkeypatch.setenv("XIAOPU_HOME", str(tmp_path))
    ws = tmp_path / "projects" / "beta"
    ws.mkdir(parents=True)
    record = workspace_store.register_workspace(ws)

    assert workspace_store.rename_workspace(ws, "Beta 项目")
    renamed = workspace_store.list_workspaces()[0]
    assert renamed.display_name == "Beta 项目"
    assert renamed.path == str(ws.resolve())

    assert workspace_store.set_workspace_pinned(ws, True)
    assert workspace_store.list_workspaces()[0].pinned is True

    assert workspace_store.archive_workspace(ws)
    assert workspace_store.list_workspaces() == []
    assert [r.path for r in workspace_store.list_workspaces(view="archived")] == [str(ws.resolve())]

    # Restore revives the archive entry with its alias intact.
    assert workspace_store.restore_workspace(ws)
    assert workspace_store.list_workspaces()[0].display_name == "Beta 项目"

    # Remove-from-sidebar is soft: registry hidden but directory untouched.
    assert workspace_store.remove_workspace(ws)
    assert workspace_store.list_workspaces() == []
    assert [r.path for r in workspace_store.list_workspaces(view="removed")] == [str(ws.resolve())]
    (ws / "keep.txt").write_text("x", encoding="utf-8")
    assert ws.is_dir()

    # Re-registering revives without losing the alias.
    revived = workspace_store.register_workspace(ws)
    assert revived.display_name == "Beta 项目"
    assert workspace_store.list_workspaces()[0].path == str(ws.resolve())

    # Purge only drops the registry row; the directory survives.
    assert workspace_store.purge_workspace(ws)
    assert workspace_store.list_workspaces(view="all") == []
    assert ws.is_dir()
