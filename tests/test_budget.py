from agent.budget import BudgetLedger


def test_budget_ledger_counts_observable_events():
    ledger = BudgetLedger(max_total_tokens=10, max_tool_calls=2, max_steps=1)
    assert ledger.begin_step() is True
    assert ledger.begin_step() is False
    assert ledger.record_tokens(3, 4) is True
    assert ledger.record_tool() is True
    assert ledger.record_tool() is True
    assert ledger.record_tool() is False
    assert ledger.snapshot(system="xiaopu")["within_budget"] is True


def test_budget_ledger_marks_token_overrun():
    ledger = BudgetLedger(max_total_tokens=3, max_tool_calls=1, max_steps=1)
    assert ledger.record_tokens(2, 2) is False
    assert ledger.snapshot()["within_budget"] is False
