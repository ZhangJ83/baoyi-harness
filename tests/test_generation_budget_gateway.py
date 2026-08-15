import json

import pytest

from agent.generation_budget_gateway import (
    BudgetExhausted,
    BudgetIntegrityError,
    abort_reservation,
    commit_usage,
    reserve_request,
)


def test_gateway_rewrites_each_request_to_remaining_cumulative_allowance(tmp_path):
    state = tmp_path / "gateway.json"
    first, first_id = reserve_request(
        provider="openai_responses", body={"max_output_tokens": 600}, state_path=state, cap=1000
    )
    assert first["max_output_tokens"] == 600
    commit_usage(reservation_id=first_id, observed_output_tokens=550, state_path=state, cap=1000)
    second, second_id = reserve_request(
        provider="openai_responses", body={"max_output_tokens": 800}, state_path=state, cap=1000
    )
    assert second["max_output_tokens"] == 450
    final = commit_usage(
        reservation_id=second_id, observed_output_tokens=450, state_path=state, cap=1000
    )
    assert final["committed_output_tokens"] == 1000
    with pytest.raises(BudgetExhausted):
        reserve_request(provider="openai_responses", body={}, state_path=state, cap=1000)


def test_gateway_supports_anthropic_max_tokens_field(tmp_path):
    rewritten, reservation_id = reserve_request(
        provider="anthropic_messages", body={"max_tokens": 99}, state_path=tmp_path / "g.json", cap=50
    )
    assert rewritten["max_tokens"] == 50
    commit_usage(
        reservation_id=reservation_id,
        observed_output_tokens=20,
        state_path=tmp_path / "g.json",
        cap=50,
    )


def test_gateway_reservations_prevent_concurrent_overcommit(tmp_path):
    state = tmp_path / "g.json"
    _, first_id = reserve_request(provider="openai_chat", body={}, state_path=state, cap=100)
    with pytest.raises(BudgetExhausted):
        reserve_request(provider="openai_chat", body={}, state_path=state, cap=100)
    abort_reservation(reservation_id=first_id, state_path=state, cap=100, reason="upstream error")
    rewritten, _ = reserve_request(provider="openai_chat", body={}, state_path=state, cap=100)
    assert rewritten["max_tokens"] == 100


def test_gateway_fails_closed_when_provider_exceeds_reservation(tmp_path):
    state = tmp_path / "g.json"
    _, reservation_id = reserve_request(
        provider="openai_chat", body={"max_tokens": 10}, state_path=state, cap=100
    )
    with pytest.raises(BudgetIntegrityError, match="exceeded"):
        commit_usage(
            reservation_id=reservation_id,
            observed_output_tokens=11,
            state_path=state,
            cap=100,
        )
    saved = json.loads(state.read_text(encoding="utf-8"))
    assert saved["violations"][0]["observed"] == 11


def test_gateway_rejects_corrupt_state_instead_of_resetting_budget(tmp_path):
    state = tmp_path / "g.json"
    state.write_text("not-json", encoding="utf-8")
    with pytest.raises(BudgetIntegrityError, match="invalid"):
        reserve_request(provider="openai_chat", body={}, state_path=state, cap=100)
