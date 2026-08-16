"""Persistent workspace registry for the GUI (and later TUI/CLI).

Workspace removal is a soft registry operation: the directory and its
artifacts are never touched. Renaming edits the display alias only, because
moving a workspace path would break every session's durable workspace link.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from . import config

WORKSPACE_VIEWS = ("active", "archived", "removed", "all")


@dataclass
class WorkspaceRecord:
    path: str
    name: str
    last_used: str
    display_name: str = ""
    pinned: bool = False
    archived: bool = False
    removed_at: str = ""


def _registry_path() -> Path:
    return config.state_home() / "workspaces.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read_rows() -> list[dict]:
    path = _registry_path()
    if not path.is_file():
        return []
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return [row for row in rows if row.get("path")]


def _save_rows(rows: list[dict]) -> None:
    _registry_path().write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def _record_from(row: dict) -> WorkspaceRecord:
    return WorkspaceRecord(
        path=row.get("path", ""),
        name=row.get("name", ""),
        last_used=row.get("last_used", ""),
        display_name=row.get("display_name", ""),
        pinned=bool(row.get("pinned", False)),
        archived=bool(row.get("archived", False)),
        removed_at=row.get("removed_at", ""),
    )


def _record_rows(records: list[WorkspaceRecord]) -> list[dict]:
    return [asdict(record) for record in records]


def list_workspaces(view: str = "active") -> list[WorkspaceRecord]:
    if view not in WORKSPACE_VIEWS:
        view = "active"
    records = [_record_from(row) for row in _read_rows()]
    if view == "active":
        records = [r for r in records if not r.archived and not r.removed_at]
    elif view == "archived":
        records = [r for r in records if r.archived and not r.removed_at]
    elif view == "removed":
        records = [r for r in records if r.removed_at]
    records.sort(key=lambda r: (r.pinned, r.last_used or ""), reverse=True)
    return records


def _all_records() -> list[WorkspaceRecord]:
    return [_record_from(row) for row in _read_rows()]


def register_workspace(path) -> WorkspaceRecord:
    path = Path(path).expanduser().resolve()
    if not path.is_dir():
        raise ValueError(f"workspace does not exist: {path}")
    records = {r.path: r for r in _all_records()}
    existing = records.get(str(path))
    if existing is not None:
        # Re-registering revives a removed/archived workspace without losing
        # its display alias or pin state.
        existing.name = path.name
        existing.last_used = _now()
        existing.archived = False
        existing.removed_at = ""
        record = existing
    else:
        record = WorkspaceRecord(
            path=str(path), name=path.name, last_used=_now(), display_name=path.name
        )
    records[str(path)] = record
    _save_rows(_record_rows(list(records.values())))
    return record


def touch_workspace(path) -> None:
    path = Path(path).expanduser().resolve()
    records = _all_records()
    changed = False
    for record in records:
        if Path(record.path) == path and not record.removed_at:
            record.last_used = _now()
            changed = True
            break
    if changed:
        _save_rows(_record_rows(records))


def _update_workspace(path, mutate) -> bool:
    path = Path(path).expanduser().resolve()
    records = _all_records()
    for record in records:
        if Path(record.path) == path:
            mutate(record)
            _save_rows(_record_rows(records))
            return True
    return False


def rename_workspace(path, display_name: str) -> bool:
    clean = " ".join(str(display_name).split())[:60]
    if not clean:
        return False
    return _update_workspace(path, lambda r: setattr(r, "display_name", clean))


def set_workspace_pinned(path, pinned: bool) -> bool:
    return _update_workspace(path, lambda r: setattr(r, "pinned", bool(pinned)))


def archive_workspace(path) -> bool:
    return _update_workspace(path, lambda r: (
        setattr(r, "archived", True),
        setattr(r, "removed_at", ""),
        setattr(r, "pinned", False),
        setattr(r, "last_used", _now()),
    ))


def restore_workspace(path) -> bool:
    return _update_workspace(path, lambda r: (
        setattr(r, "archived", False),
        setattr(r, "removed_at", ""),
        setattr(r, "last_used", _now()),
    ))


def remove_workspace(path) -> bool:
    """Soft-remove: mark as removed from the sidebar, never touch the disk dir."""
    return _update_workspace(path, lambda r: (
        setattr(r, "removed_at", _now()),
        setattr(r, "archived", False),
        setattr(r, "pinned", False),
    ))


def purge_workspace(path) -> bool:
    """Physically drop the registry row (the directory itself is untouched)."""
    path = Path(path).expanduser().resolve()
    records = _all_records()
    kept = [r for r in records if Path(r.path) != path]
    if len(kept) == len(records):
        return False
    _save_rows(_record_rows(kept))
    return True
