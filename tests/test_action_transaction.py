from __future__ import annotations

import pytest

from agent.action_transaction import (
    ActionScope,
    ActionTransaction,
    ActionTransactionError,
    CancellationToken,
    PostconditionFailed,
    RollbackFailed,
    ScopeViolation,
    TransactionCancelled,
)


def _scope(*requested: str) -> ActionScope[str]:
    return ActionScope.from_iterables(allowed={"slide:2", "slide:3"}, requested=requested)


def test_success_commits_and_emits_ordered_lifecycle() -> None:
    state = {"value": "before"}
    events = []

    tx = ActionTransaction(
        scope=_scope("slide:2"),
        checkpoint=lambda: dict(state),
        execute=lambda: state.update(value="after") or "result",
        postcondition=lambda result: result == "result" and state["value"] == "after",
        commit=lambda _result: state.update(committed=True),
        rollback=lambda snapshot, _error: state.update(snapshot),
        event_sink=events.append,
        transaction_id="tx-success",
    )

    result = tx.run()

    assert result.status == "committed"
    assert result.value == "result"
    assert state == {"value": "after", "committed": True}
    assert [event.phase for event in events] == [
        "permission_checked",
        "checkpoint_started",
        "checkpoint_created",
        "execute_started",
        "execute_completed",
        "postcondition_started",
        "postcondition_passed",
        "commit_started",
        "committed",
    ]


def test_scope_violation_runs_no_user_callback() -> None:
    called = []
    tx = ActionTransaction(
        scope=_scope("slide:9"),
        checkpoint=lambda: called.append("checkpoint"),
        execute=lambda: called.append("execute"),
        postcondition=lambda _result: True,
        rollback=lambda _snapshot, _error: called.append("rollback"),
    )

    with pytest.raises(ScopeViolation, match="slide:9"):
        tx.run()
    assert called == []


def test_false_postcondition_restores_checkpoint() -> None:
    state = {"value": 1}
    tx = ActionTransaction(
        scope=_scope("slide:2"),
        checkpoint=lambda: dict(state),
        execute=lambda: state.update(value=2) or 2,
        postcondition=lambda _result: False,
        rollback=lambda snapshot, _error: state.clear() or state.update(snapshot),
    )

    with pytest.raises(PostconditionFailed):
        tx.run()
    assert state == {"value": 1}


def test_execute_exception_is_reraised_after_rollback() -> None:
    state = []

    def execute() -> None:
        state.append("mutation")
        raise ValueError("bad action")

    tx = ActionTransaction(
        scope=_scope("slide:2"),
        checkpoint=lambda: list(state),
        execute=execute,
        postcondition=lambda _result: True,
        rollback=lambda snapshot, _error: state.__setitem__(slice(None), snapshot),
    )

    with pytest.raises(ValueError, match="bad action"):
        tx.run()
    assert state == []


def test_cancel_after_execute_rolls_back() -> None:
    token = CancellationToken()
    state = []

    def execute() -> str:
        state.append("mutation")
        token.cancel()
        return "done"

    tx = ActionTransaction(
        scope=_scope("slide:2"),
        checkpoint=lambda: list(state),
        execute=execute,
        postcondition=lambda _result: True,
        rollback=lambda snapshot, _error: state.__setitem__(slice(None), snapshot),
        cancellation=token,
    )

    with pytest.raises(TransactionCancelled, match="postcondition"):
        tx.run()
    assert state == []


def test_cancel_before_checkpoint_has_nothing_to_rollback() -> None:
    token = CancellationToken()
    token.cancel()
    called = []
    tx = ActionTransaction(
        scope=_scope("slide:2"),
        checkpoint=lambda: called.append("checkpoint"),
        execute=lambda: None,
        postcondition=lambda _result: True,
        rollback=lambda _snapshot, _error: called.append("rollback"),
        cancellation=token,
    )

    with pytest.raises(TransactionCancelled):
        tx.run()
    assert called == []


def test_rollback_failure_preserves_both_errors() -> None:
    def fail_execute() -> None:
        raise ValueError("primary")

    def fail_rollback(_snapshot: object, _error: BaseException) -> None:
        raise OSError("restore")

    tx = ActionTransaction(
        scope=_scope("slide:2"),
        checkpoint=object,
        execute=fail_execute,
        postcondition=lambda _result: True,
        rollback=fail_rollback,
    )

    with pytest.raises(RollbackFailed) as caught:
        tx.run()
    assert isinstance(caught.value.original_error, ValueError)
    assert isinstance(caught.value.rollback_error, OSError)


def test_transaction_is_single_use_and_event_sink_is_best_effort() -> None:
    tx = ActionTransaction(
        scope=_scope(),
        checkpoint=object,
        execute=lambda: 7,
        postcondition=lambda _result: None,
        rollback=lambda _snapshot, _error: None,
        event_sink=lambda _event: (_ for _ in ()).throw(RuntimeError("telemetry")),
    )
    assert tx.run().value == 7
    with pytest.raises(ActionTransactionError, match="only once"):
        tx.run()

