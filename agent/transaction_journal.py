"""Durable, domain-neutral transaction state journal.

The journal records *that* a transaction reached a safety boundary.  It does
not serialize arbitrary domain checkpoints and therefore deliberately does not
claim that a PPT, spreadsheet, database, or other resource can be restored by
the generic layer alone.  Domain adapters remain responsible for checkpoint
artifacts and recovery procedures.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from threading import RLock
from typing import Any, Iterable, Literal, Mapping, Protocol
from uuid import uuid4


JournalStatus = Literal[
    "planned",
    "checkpointed",
    "committed",
    "rolled_back",
    "failed",
]

TERMINAL_STATUSES: frozenset[JournalStatus] = frozenset(
    {"committed", "rolled_back", "failed"}
)


class TransactionJournal(Protocol):
    """Minimal interface consumed by :class:`ActionTransaction`."""

    def transition(
        self,
        transaction_id: str,
        status: JournalStatus,
        *,
        requested_scope: Iterable[Any] = (),
        detail: str | None = None,
    ) -> None: ...


@dataclass(frozen=True)
class JournalEntry:
    schema: str
    transaction_id: str
    status: JournalStatus
    created_at: str
    updated_at: str
    requested_scope: tuple[str, ...]
    detail: str | None
    journal_path: Path

    @property
    def incomplete(self) -> bool:
        return self.status not in TERMINAL_STATUSES


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_transaction_id(transaction_id: str) -> str:
    """Keep the journal filename inside its fixed directory."""

    if not transaction_id or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for char in transaction_id):
        raise ValueError("transaction_id may contain only letters, digits, '-' and '_'")
    return transaction_id


def _atomic_json_write(path: Path, payload: Mapping[str, Any]) -> None:
    """Write one JSON document atomically in the destination directory."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


class DurableTransactionJournal:
    """One atomically replaced JSON state file per transaction."""

    SCHEMA = "xiaopu-transaction-journal-v1"

    def __init__(self, workspace: str | Path, directory: str | Path | None = None) -> None:
        self.workspace = Path(workspace).resolve()
        self.directory = (
            Path(directory).resolve()
            if directory is not None
            else self.workspace / ".xiaopu" / "transactions"
        )
        self._lock = RLock()

    def path_for(self, transaction_id: str) -> Path:
        return self.directory / f"{_safe_transaction_id(transaction_id)}.json"

    def transition(
        self,
        transaction_id: str,
        status: JournalStatus,
        *,
        requested_scope: Iterable[Any] = (),
        detail: str | None = None,
    ) -> None:
        if status not in {"planned", "checkpointed", "committed", "rolled_back", "failed"}:
            raise ValueError(f"unsupported journal status: {status!r}")
        target = self.path_for(transaction_id)
        with self._lock:
            existing: dict[str, Any] = {}
            if target.is_file():
                try:
                    existing = json.loads(target.read_text(encoding="utf-8"))
                except (OSError, UnicodeError, json.JSONDecodeError):
                    # Replace a corrupt state atomically.  The new record keeps
                    # the transaction visible rather than making startup fail.
                    existing = {}
            timestamp = _now()
            payload = {
                "schema": self.SCHEMA,
                "transaction_id": transaction_id,
                "status": status,
                "created_at": existing.get("created_at", timestamp),
                "updated_at": timestamp,
                "requested_scope": sorted((repr(item) for item in requested_scope)),
                "detail": detail,
                "recovery_policy": (
                    "inspect the domain checkpoint and adapter before recovery; "
                    "generic automatic recovery is not supported"
                ),
            }
            _atomic_json_write(target, payload)

    def list_incomplete(self) -> list[JournalEntry]:
        return list_incomplete_transactions(self.workspace, directory=self.directory)


def _entry_from_payload(path: Path, payload: Mapping[str, Any]) -> JournalEntry | None:
    status = payload.get("status")
    if payload.get("schema") != DurableTransactionJournal.SCHEMA or status not in {
        "planned",
        "checkpointed",
        "committed",
        "rolled_back",
        "failed",
    }:
        return None
    return JournalEntry(
        schema=str(payload["schema"]),
        transaction_id=str(payload.get("transaction_id", path.stem)),
        status=status,
        created_at=str(payload.get("created_at", "")),
        updated_at=str(payload.get("updated_at", "")),
        requested_scope=tuple(str(item) for item in payload.get("requested_scope", [])),
        detail=str(payload["detail"]) if payload.get("detail") is not None else None,
        journal_path=path,
    )


def list_incomplete_transactions(
    workspace: str | Path,
    *,
    directory: str | Path | None = None,
) -> list[JournalEntry]:
    """List crash candidates without trying to recover their domain state."""

    root = (
        Path(directory).resolve()
        if directory is not None
        else Path(workspace).resolve() / ".xiaopu" / "transactions"
    )
    if not root.is_dir():
        return []
    entries: list[JournalEntry] = []
    for path in root.glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        entry = _entry_from_payload(path, payload)
        if entry is not None and entry.incomplete:
            entries.append(entry)
    return sorted(entries, key=lambda item: (item.updated_at, item.transaction_id))


__all__ = [
    "DurableTransactionJournal",
    "JournalEntry",
    "JournalStatus",
    "TERMINAL_STATUSES",
    "TransactionJournal",
    "list_incomplete_transactions",
]
