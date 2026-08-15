"""Workspace-scoped transactional adapter for ordinary files.

This is the first non-PowerPoint domain adapter over :mod:`action_transaction`.
It snapshots exact file bytes (including the fact that a path did not exist),
runs a caller-supplied mutation, verifies a deterministic postcondition, and
either commits or restores every requested path.  Operational events are
observer-only and can never decide whether the mutation succeeds.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Generic, Iterable, TypeVar

from .action_transaction import (
    ActionScope,
    ActionTransaction,
    CancellationToken,
    EventSink,
    ScopeViolation,
    TransactionEvent,
    TransactionResult,
)
from .transaction_journal import TransactionJournal


ResultT = TypeVar("ResultT")


@dataclass(frozen=True)
class FileState:
    """The rollback state of one workspace path."""

    path: Path
    existed: bool
    content: bytes | None


@dataclass(frozen=True)
class FileCheckpoint:
    entries: tuple[FileState, ...]


class LinkedCancellationToken(CancellationToken):
    """Cancellation token optionally linked to an outer run controller."""

    def __init__(self, probe: Callable[[], bool] | None = None) -> None:
        super().__init__()
        self._probe = probe

    @property
    def is_cancelled(self) -> bool:
        return super().is_cancelled or bool(self._probe and self._probe())


class BestEffortFileEventSink:
    """Disable a failing telemetry consumer after its first exception."""

    def __init__(self, sink: EventSink):
        self._sink = sink
        self.disabled = False

    def __call__(self, event: TransactionEvent[Any]) -> None:
        if self.disabled:
            return
        try:
            self._sink(event)
        except Exception:
            self.disabled = True


def recorder_event_sink(recorder: Any) -> EventSink | None:
    """Adapt a RunRecorder-like object without making it a dependency."""

    emit = getattr(recorder, "event", None)
    if not callable(emit):
        return None

    def publish(event: TransactionEvent[Any]) -> None:
        emit(
            "file_transaction",
            transaction_id=event.transaction_id,
            phase=event.phase,
            requested_scope=[str(path) for path in event.requested_scope],
            detail=event.detail or "",
        )

    return BestEffortFileEventSink(publish)


class FileTransactionAdapter(Generic[ResultT]):
    """Bind ActionTransaction to a closed set of workspace file paths."""

    def __init__(
        self,
        *,
        workspace: Path,
        paths: Iterable[str | Path],
        execute: Callable[[tuple[Path, ...], CancellationToken], ResultT],
        postcondition: Callable[[ResultT, tuple[Path, ...]], bool | None],
        commit: Callable[[ResultT, tuple[Path, ...]], None] | None = None,
        cancellation: CancellationToken | None = None,
        event_sink: EventSink | None = None,
        journal: TransactionJournal | None = None,
    ) -> None:
        self.workspace = workspace.resolve()
        resolved: list[Path] = []
        for raw in paths:
            candidate = Path(raw)
            if not candidate.is_absolute():
                candidate = self.workspace / candidate
            candidate = candidate.resolve()
            if candidate not in resolved:
                resolved.append(candidate)
        if not resolved:
            raise ValueError("file transaction requires at least one path")

        self.paths = tuple(resolved)
        allowed = [path for path in self.paths if self._within_workspace(path)]
        self.scope = ActionScope.from_iterables(allowed=allowed, requested=self.paths)
        self.cancellation = cancellation or CancellationToken()
        self._execute_callback = execute
        self._postcondition_callback = postcondition
        self._commit_callback = commit
        wrapped_sink = BestEffortFileEventSink(event_sink) if event_sink is not None else None
        self.transaction = ActionTransaction[
            FileCheckpoint, ResultT, Path
        ](
            scope=self.scope,
            checkpoint=self.checkpoint,
            execute=self.execute,
            postcondition=self.postcondition,
            commit=self.commit,
            rollback=self.rollback,
            cancellation=self.cancellation,
            event_sink=wrapped_sink,
            journal=journal,
        )

    def _within_workspace(self, path: Path) -> bool:
        try:
            path.relative_to(self.workspace)
            return True
        except ValueError:
            return False

    @property
    def denied_paths(self) -> frozenset[Path]:
        return self.scope.denied

    def checkpoint(self) -> FileCheckpoint:
        """Capture exact bytes or a non-existence marker for every path."""

        entries: list[FileState] = []
        for path in self.paths:
            if path.exists():
                if not path.is_file():
                    raise IsADirectoryError(path)
                entries.append(FileState(path=path, existed=True, content=path.read_bytes()))
            else:
                entries.append(FileState(path=path, existed=False, content=None))
        return FileCheckpoint(tuple(entries))

    def execute(self) -> ResultT:
        return self._execute_callback(self.paths, self.cancellation)

    def postcondition(self, value: ResultT) -> bool | None:
        return self._postcondition_callback(value, self.paths)

    def commit(self, value: ResultT) -> None:
        if self._commit_callback is not None:
            self._commit_callback(value, self.paths)

    def rollback(self, checkpoint: FileCheckpoint, _error: BaseException) -> None:
        """Restore existing files byte-for-byte and remove newly created files."""

        for state in checkpoint.entries:
            if state.existed:
                state.path.parent.mkdir(parents=True, exist_ok=True)
                state.path.write_bytes(state.content or b"")
            elif state.path.exists():
                if not state.path.is_file() and not state.path.is_symlink():
                    raise IsADirectoryError(state.path)
                state.path.unlink()

    def run(self) -> TransactionResult[ResultT, Path]:
        return self.transaction.run()


__all__ = [
    "BestEffortFileEventSink",
    "FileCheckpoint",
    "FileState",
    "FileTransactionAdapter",
    "LinkedCancellationToken",
    "ScopeViolation",
    "recorder_event_sink",
]
