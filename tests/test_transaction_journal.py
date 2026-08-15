from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from agent.action_transaction import ActionScope, ActionTransaction
from agent.main import _print_incomplete_transaction_notice
from agent.transaction_journal import (
    DurableTransactionJournal,
    list_incomplete_transactions,
)


def _transaction(root: Path, *, execute=lambda: "ok", rollback=lambda _snapshot, _error: None):
    return ActionTransaction(
        scope=ActionScope.from_iterables(allowed={"file:a"}, requested={"file:a"}),
        checkpoint=lambda: "snapshot",
        execute=execute,
        postcondition=lambda _result: True,
        rollback=rollback,
        journal=DurableTransactionJournal(root),
        transaction_id="tx-test",
    )


def test_success_journal_reaches_committed_and_is_not_incomplete() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        assert _transaction(root).run().value == "ok"

        path = root / ".xiaopu" / "transactions" / "tx-test.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["schema"] == "xiaopu-transaction-journal-v1"
        assert payload["status"] == "committed"
        assert payload["requested_scope"] == ["'file:a'"]
        assert list_incomplete_transactions(root) == []
        assert not list(path.parent.glob("*.tmp"))


def test_failure_after_checkpoint_reaches_rolled_back() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)

        def fail():
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            _transaction(root, execute=fail).run()
        payload = json.loads(
            (root / ".xiaopu" / "transactions" / "tx-test.json").read_text(
                encoding="utf-8"
            )
        )
        assert payload["status"] == "rolled_back"
        assert "ValueError" in payload["detail"]
        assert list_incomplete_transactions(root) == []


def test_checkpointed_state_is_discovered_after_simulated_crash() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        journal = DurableTransactionJournal(root)
        journal.transition("crash-candidate", "planned", requested_scope=["slide:2"])
        journal.transition("crash-candidate", "checkpointed", requested_scope=["slide:2"])

        pending = list_incomplete_transactions(root)
        assert [(entry.transaction_id, entry.status) for entry in pending] == [
            ("crash-candidate", "checkpointed")
        ]
        assert "automatic recovery is not supported" in json.loads(
            pending[0].journal_path.read_text(encoding="utf-8")
        )["recovery_policy"]


def test_startup_notice_lists_incomplete_but_does_not_mutate_it(capsys) -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        journal = DurableTransactionJournal(root)
        journal.transition("pending-one", "planned", requested_scope=["file:a"])
        before = journal.path_for("pending-one").read_bytes()

        _print_incomplete_transaction_notice(root)

        error = capsys.readouterr().err
        assert "RECOVERY NOTICE" in error
        assert "did not attempt generic automatic recovery" in error
        assert journal.path_for("pending-one").read_bytes() == before


def test_terminal_journal_write_failure_does_not_undo_a_real_commit() -> None:
    class CommitFailingJournal:
        def __init__(self):
            self.statuses = []

        def transition(self, transaction_id, status, **kwargs):
            self.statuses.append(status)
            if status == "committed":
                raise OSError("disk full at terminal marker")

    state = {"value": "before"}
    journal = CommitFailingJournal()
    result = ActionTransaction(
        scope=ActionScope.from_iterables(allowed={"x"}, requested={"x"}),
        checkpoint=lambda: dict(state),
        execute=lambda: state.update(value="after") or "ok",
        postcondition=lambda _result: True,
        rollback=lambda snapshot, _error: state.update(snapshot),
        journal=journal,
    ).run()

    assert result.status == "committed"
    assert state["value"] == "after"
    assert journal.statuses == ["planned", "checkpointed", "committed"]


def test_checkpointed_journal_write_failure_prevents_user_mutation() -> None:
    class CheckpointMarkerFailingJournal:
        def __init__(self):
            self.statuses = []

        def transition(self, transaction_id, status, **kwargs):
            self.statuses.append(status)
            if status == "checkpointed":
                raise OSError("cannot persist checkpoint boundary")

    state = []
    journal = CheckpointMarkerFailingJournal()
    transaction = ActionTransaction(
        scope=ActionScope.from_iterables(allowed={"x"}, requested={"x"}),
        checkpoint=lambda: list(state),
        execute=lambda: state.append("mutated"),
        postcondition=lambda _result: True,
        rollback=lambda snapshot, _error: state.__setitem__(slice(None), snapshot),
        journal=journal,
    )

    with pytest.raises(OSError, match="checkpoint boundary"):
        transaction.run()
    assert state == []
    assert journal.statuses == ["planned", "checkpointed", "failed"]


def test_invalid_transaction_id_cannot_escape_journal_directory() -> None:
    with TemporaryDirectory() as tmp:
        journal = DurableTransactionJournal(Path(tmp))
        with pytest.raises(ValueError, match="transaction_id"):
            journal.transition("../escape", "planned")


def test_corrupt_or_unrelated_json_does_not_break_startup_scan() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        directory = root / ".xiaopu" / "transactions"
        directory.mkdir(parents=True)
        (directory / "broken.json").write_text("{", encoding="utf-8")
        (directory / "other.json").write_text(
            json.dumps({"schema": "someone-else", "status": "planned"}),
            encoding="utf-8",
        )
        assert list_incomplete_transactions(root) == []
