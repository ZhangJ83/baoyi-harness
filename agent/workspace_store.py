"""Persistent workspace registry for the GUI (and later TUI/CLI)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from . import config


@dataclass
class WorkspaceRecord:
    path: str
    name: str
    last_used: str


def _registry_path() -> Path:
    return config.state_home() / "workspaces.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def list_workspaces() -> list[WorkspaceRecord]:
    path = _registry_path()
    if not path.is_file():
        return []
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    records = [WorkspaceRecord(**row) for row in rows if row.get("path")]
    records.sort(key=lambda r: r.last_used, reverse=True)
    return records


def _save(records: list[WorkspaceRecord]) -> None:
    payload = [{"path": r.path, "name": r.name, "last_used": r.last_used} for r in records]
    _registry_path().write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def register_workspace(path) -> WorkspaceRecord:
    path = Path(path).expanduser().resolve()
    if not path.is_dir():
        raise ValueError(f"workspace does not exist: {path}")
    records = {r.path: r for r in list_workspaces()}
    records[str(path)] = WorkspaceRecord(path=str(path), name=path.name, last_used=_now())
    _save(list(records.values()))
    return records[str(path)]


def touch_workspace(path) -> None:
    path = Path(path).expanduser().resolve()
    records = {r.path: r for r in list_workspaces()}
    if str(path) in records:
        records[str(path)].last_used = _now()
        _save(list(records.values()))


def remove_workspace(path) -> bool:
    path = Path(path).expanduser().resolve()
    records = [r for r in list_workspaces() if Path(r.path) != path]
    before = len(list_workspaces())
    _save(records)
    return len(records) < before
