import json

from benchmarks.verify_budget_parity import verify


def test_parity_rejects_missing_ledger(tmp_path):
    path = tmp_path / "results.json"
    path.write_text(json.dumps({"results": [{
        "task_id": "a", "trial_name": "a.1", "is_resolved": True,
        "total_input_tokens": 1, "total_output_tokens": 1,
    }]}), encoding="utf-8")
    result = verify(path, max_total_tokens=10, max_tool_calls=2, max_steps=1, max_wall_seconds=30)
    assert result["eligible"] is False
    assert result["failures"][0]["reason"] == "missing_budget_ledger"


def test_parity_accepts_complete_ledger(tmp_path):
    trial = tmp_path / "a" / "a.1"
    trial.mkdir(parents=True)
    (tmp_path / "results.json").write_text(json.dumps({"results": [{
        "task_id": "a", "trial_name": "a.1", "is_resolved": True,
        "total_input_tokens": 1, "total_output_tokens": 2,
        "agent_started_at": "2026-01-01T00:00:00+00:00",
        "agent_ended_at": "2026-01-01T00:00:03+00:00",
    }]}), encoding="utf-8")
    (trial / "budget_ledger.json").write_text(json.dumps({
        "input_tokens": 1, "output_tokens": 2, "tool_calls": 1, "steps": 1,
        "max_total_tokens": 10, "max_tool_calls": 2, "max_steps": 1,
        "within_budget": True,
    }), encoding="utf-8")
    result = verify(tmp_path / "results.json", max_total_tokens=10, max_tool_calls=2, max_steps=1, max_wall_seconds=30)
    assert result["eligible"] is True


def test_parity_rejects_token_mismatch_and_cap_drift(tmp_path):
    trial = tmp_path / "a" / "a.1"
    trial.mkdir(parents=True)
    (tmp_path / "results.json").write_text(json.dumps({"results": [{
        "task_id": "a", "trial_name": "a.1", "is_resolved": False,
        "total_input_tokens": 3, "total_output_tokens": 2,
        "agent_started_at": "2026-01-01T00:00:00+00:00",
        "agent_ended_at": "2026-01-01T00:00:02+00:00",
    }]}), encoding="utf-8")
    (trial / "budget_ledger.json").write_text(json.dumps({
        "input_tokens": 1, "output_tokens": 2, "tool_calls": 1, "steps": 1,
        "max_total_tokens": 99, "max_tool_calls": 2, "max_steps": 1,
        "within_budget": True,
    }), encoding="utf-8")
    result = verify(tmp_path / "results.json", max_total_tokens=10, max_tool_calls=2, max_steps=1, max_wall_seconds=30)
    reasons = {item["reason"] for item in result["failures"]}
    assert "provider_ledger_token_mismatch" in reasons
    assert "ledger_max_total_tokens_mismatch" in reasons


def test_parity_rejects_missing_wall_time(tmp_path):
    trial = tmp_path / "a" / "a.1"
    trial.mkdir(parents=True)
    (tmp_path / "results.json").write_text(json.dumps({"results": [{
        "task_id": "a", "trial_name": "a.1", "is_resolved": True,
        "total_input_tokens": 1, "total_output_tokens": 2,
    }]}), encoding="utf-8")
    (trial / "budget_ledger.json").write_text(json.dumps({
        "input_tokens": 1, "output_tokens": 2, "tool_calls": 1, "steps": 1,
        "max_total_tokens": 10, "max_tool_calls": 2, "max_steps": 1,
        "within_budget": True,
    }), encoding="utf-8")
    result = verify(tmp_path / "results.json", max_total_tokens=10, max_tool_calls=2, max_steps=1, max_wall_seconds=30)
    assert any(item["reason"] == "missing_or_invalid_agent_wall_time" for item in result["failures"])
