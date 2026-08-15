"""Small, domain-independent action transaction primitive.

The model-facing tool layer should not know about this module.  A domain adapter
supplies five ordinary callbacks (checkpoint, execute, postcondition, commit and
rollback); this module supplies the safety envelope around them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Event, Lock
from typing import Any, Callable, Generic, Hashable, Iterable, Literal, TypeVar
from uuid import uuid4

from .transaction_journal import JournalStatus, TransactionJournal


CheckpointT = TypeVar("CheckpointT")
ResultT = TypeVar("ResultT")
ScopeT = TypeVar("ScopeT", bound=Hashable)


class ActionTransactionError(RuntimeError):
    """Base class for failures introduced by the transaction envelope."""


class ScopeViolation(ActionTransactionError):
    """The action requested resources outside its declared permission scope."""


class TransactionCancelled(ActionTransactionError):
    """Cancellation was observed at a safe transaction boundary."""


class PostconditionFailed(ActionTransactionError):
    """The action ran, but its deterministic postcondition did not pass."""


class RollbackFailed(ActionTransactionError):
    """Both the transaction and its compensating rollback failed."""

    def __init__(self, original_error: BaseException, rollback_error: BaseException):
        self.original_error = original_error
        self.rollback_error = rollback_error
        super().__init__(
            f"transaction failed with {type(original_error).__name__}; rollback "
            f"also failed with {type(rollback_error).__name__}: {rollback_error}"
        )


@dataclass(frozen=True)
class ActionScope(Generic[ScopeT]):
    """A closed-world permission declaration for one action.

    Scope values are deliberately opaque and hashable.  A PPT adapter may use
    ("slide", 4), while a file adapter may use a normalized path.  The core does
    not infer hierarchy or silently widen access.
    """

    allowed: frozenset[ScopeT] = field(default_factory=frozenset)
    requested: frozenset[ScopeT] = field(default_factory=frozenset)

    @classmethod
    def from_iterables(
        cls, *, allowed: Iterable[ScopeT], requested: Iterable[ScopeT]
    ) -> "ActionScope[ScopeT]":
        return cls(frozenset(allowed), frozenset(requested))

    @property
    def denied(self) -> frozenset[ScopeT]:
        return self.requested.difference(self.allowed)

    def require_permitted(self) -> None:
        denied = self.denied
        if denied:
            rendered = ", ".join(sorted((repr(item) for item in denied)))
            raise ScopeViolation(f"requested scope is not permitted: {rendered}")


class CancellationToken:
    """Thread-safe cooperative cancellation shared by a caller and transaction."""

    def __init__(self) -> None:
        self._event = Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self, phase: str) -> None:
        if self.is_cancelled:
            raise TransactionCancelled(f"transaction cancelled during {phase}")


TransactionPhase = Literal[
    "permission_checked",
    "permission_denied",
    "checkpoint_started",
    "checkpoint_created",
    "execute_started",
    "execute_completed",
    "postcondition_started",
    "postcondition_passed",
    "commit_started",
    "committed",
    "cancelled",
    "failed",
    "rollback_started",
    "rolled_back",
    "rollback_failed",
]


@dataclass(frozen=True)
class TransactionEvent(Generic[ScopeT]):
    transaction_id: str
    phase: TransactionPhase
    timestamp: str
    requested_scope: tuple[ScopeT, ...]
    detail: str | None = None


EventSink = Callable[[TransactionEvent[Any]], None]


@dataclass(frozen=True)
class TransactionResult(Generic[ResultT, ScopeT]):
    transaction_id: str
    status: Literal["committed"]
    value: ResultT
    requested_scope: frozenset[ScopeT]


class ActionTransaction(Generic[CheckpointT, ResultT, ScopeT]):
    """Execute one scoped action atomically through caller-provided callbacks."""

    def __init__(
        self,
        *,
        scope: ActionScope[ScopeT],
        checkpoint: Callable[[], CheckpointT],
        execute: Callable[[], ResultT],
        postcondition: Callable[[ResultT], bool | None],
        rollback: Callable[[CheckpointT, BaseException], None],
        commit: Callable[[ResultT], None] | None = None,
        permission: Callable[[ActionScope[ScopeT]], bool] | None = None,
        cancellation: CancellationToken | None = None,
        event_sink: EventSink | None = None,
        journal: TransactionJournal | None = None,
        transaction_id: str | None = None,
    ) -> None:
        self.scope = scope
        self._checkpoint = checkpoint
        self._execute = execute
        self._postcondition = postcondition
        self._rollback = rollback
        self._commit = commit
        self._permission = permission
        self.cancellation = cancellation or CancellationToken()
        self._event_sink = event_sink
        self._journal = journal
        self.transaction_id = transaction_id or uuid4().hex
        self._run_lock = Lock()
        self._has_run = False

    def _emit(self, phase: TransactionPhase, detail: str | None = None) -> None:
        if self._event_sink is None:
            return
        event = TransactionEvent(
            transaction_id=self.transaction_id,
            phase=phase,
            timestamp=datetime.now(timezone.utc).isoformat(),
            requested_scope=tuple(sorted(self.scope.requested, key=repr)),
            detail=detail,
        )
        try:
            self._event_sink(event)
        except Exception:
            # Telemetry must never decide whether a user mutation commits.
            pass

    def _journal_transition(
        self, status: JournalStatus, detail: str | None = None
    ) -> None:
        if self._journal is None:
            return
        self._journal.transition(
            self.transaction_id,
            status,
            requested_scope=tuple(sorted(self.scope.requested, key=repr)),
            detail=detail,
        )

    def _journal_terminal_best_effort(
        self, status: JournalStatus, detail: str | None = None
    ) -> None:
        """Do not mask the real outcome if a terminal write itself fails.

        A failed terminal write intentionally leaves the last durable state as
        incomplete, so startup discovery errs on the safe side and asks for
        inspection.  Pre-mutation ``planned``/``checkpointed`` writes remain
        strict and must succeed before execution may continue.
        """

        try:
            self._journal_transition(status, detail)
        except Exception:
            pass

    def _check_permission(self) -> None:
        try:
            self.scope.require_permitted()
            if self._permission is not None and not self._permission(self.scope):
                raise ScopeViolation("permission policy rejected the requested scope")
        except ScopeViolation as exc:
            self._emit("permission_denied", str(exc))
            raise
        self._emit("permission_checked")

    def _cancel_point(self, phase: str) -> None:
        try:
            self.cancellation.raise_if_cancelled(phase)
        except TransactionCancelled as exc:
            self._emit("cancelled", str(exc))
            raise

    def run(self) -> TransactionResult[ResultT, ScopeT]:
        """Run exactly once; rollback every failure after checkpoint creation."""

        with self._run_lock:
            if self._has_run:
                raise ActionTransactionError("an ActionTransaction instance can run only once")
            self._has_run = True

        # Journal writes are strict when durability is explicitly enabled.
        # In particular, no user checkpoint or mutation runs unless the
        # planned state reached stable storage.  Existing callers that do not
        # provide a journal retain exactly the previous behavior.
        self._journal_transition("planned")

        try:
            self._cancel_point("permission check")
            self._check_permission()
            self._cancel_point("checkpoint")
        except BaseException as exc:
            self._journal_terminal_best_effort(
                "failed", f"{type(exc).__name__}: {exc}"
            )
            raise

        try:
            self._emit("checkpoint_started")
            snapshot = self._checkpoint()
            self._emit("checkpoint_created")
            self._journal_transition("checkpointed")
        except BaseException as exc:
            self._journal_terminal_best_effort(
                "failed", f"{type(exc).__name__}: {exc}"
            )
            raise

        try:
            self._cancel_point("execution")
            self._emit("execute_started")
            value = self._execute()
            self._emit("execute_completed")

            self._cancel_point("postcondition")
            self._emit("postcondition_started")
            passed = self._postcondition(value)
            if passed is False:
                raise PostconditionFailed("action postcondition returned false")
            self._emit("postcondition_passed")

            self._cancel_point("commit")
            self._emit("commit_started")
            if self._commit is not None:
                self._commit(value)
            self._journal_terminal_best_effort("committed")
            self._emit("committed")
            return TransactionResult(
                transaction_id=self.transaction_id,
                status="committed",
                value=value,
                requested_scope=self.scope.requested,
            )
        except BaseException as exc:
            if not isinstance(exc, TransactionCancelled):
                self._emit("failed", f"{type(exc).__name__}: {exc}")
            self._emit("rollback_started")
            try:
                self._rollback(snapshot, exc)
            except BaseException as rollback_exc:
                self._emit(
                    "rollback_failed",
                    f"{type(rollback_exc).__name__}: {rollback_exc}",
                )
                self._journal_terminal_best_effort(
                    "failed",
                    f"{type(exc).__name__}: {exc}; rollback "
                    f"{type(rollback_exc).__name__}: {rollback_exc}",
                )
                raise RollbackFailed(exc, rollback_exc) from rollback_exc
            self._emit("rolled_back")
            self._journal_terminal_best_effort(
                "rolled_back", f"{type(exc).__name__}: {exc}"
            )
            raise
