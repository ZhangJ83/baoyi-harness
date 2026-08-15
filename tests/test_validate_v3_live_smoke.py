import json

from benchmarks.validate_v3_live_smoke import SYSTEMS, validate


def write_smoke(root, system):
    run = root / system
    trial = run / "task" / "trial" / "agent-logs"
    trial.mkdir(parents=True)
    (run / "results.json").write_text(
        json.dumps({"results": [{"task_id": "task", "trial_name": "trial"}]}), encoding="utf-8"
    )
    (run / "run_manifest_v3.json").write_text(
        json.dumps({"non_scored_smoke": True}), encoding="utf-8"
    )
    ledger = {
        "system": system,
        "within_budget": True,
        "covered_local_tool_calls": 1,
        "output_tokens": 3,
        "caps": {
            "max_cumulative_output_tokens": 10,
            "max_covered_local_tool_calls": 2,
            "max_agent_wall_seconds": 5,
        },
        "parse_errors": [],
        "gateway_violations": [],
    }
    if system != "xiaopu":
        ledger["gateway_output_matches_cli_stream"] = True
    (trial / "budget_ledger_v3.json").write_text(json.dumps(ledger), encoding="utf-8")
    return run / "results.json"


def protocol():
    return {"hard_envelope": {
        "max_cumulative_output_tokens": 10,
        "max_covered_local_tool_calls": 2,
        "max_agent_wall_seconds": 5,
    }}


def test_complete_non_scored_smoke_is_transport_ready(tmp_path):
    paths = {system: write_smoke(tmp_path, system) for system in SYSTEMS}
    result = validate(paths, protocol(), credential_present=True)
    assert result["smoke_valid"] is True
    assert result["ready_for_confirmatory_run_now"] is True


def test_credential_is_dynamic_and_missing_hook_observation_fails(tmp_path):
    paths = {system: write_smoke(tmp_path, system) for system in SYSTEMS}
    codex_ledger = tmp_path / "codex" / "task" / "trial" / "agent-logs" / "budget_ledger_v3.json"
    payload = json.loads(codex_ledger.read_text(encoding="utf-8"))
    payload["covered_local_tool_calls"] = 0
    codex_ledger.write_text(json.dumps(payload), encoding="utf-8")
    result = validate(paths, protocol(), credential_present=False)
    assert result["smoke_valid"] is False
    assert result["ready_for_confirmatory_run_now"] is False
    assert {row["reason"] for row in result["failures"]} == {"tool_hook_not_observed"}
