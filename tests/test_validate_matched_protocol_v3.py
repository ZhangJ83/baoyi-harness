from benchmarks.validate_matched_protocol_v3 import validate


def protocol():
    return {
        "status": "prospective_not_run",
        "anti_harking_boundary": "do not pool v2",
        "benchmark": {"n_tasks": 18},
        "hard_envelope": {
            "max_cumulative_output_tokens": 100,
            "max_covered_local_tool_calls": 2,
            "max_agent_wall_seconds": 10,
            "covered_tool_surface": "local only; hosted tools disabled",
            "gateway": "pending implementation",
        },
        "readiness_gates": {
            "tool_hook_unit_tests": True,
            "tool_hook_live_smoke": False,
            "gateway_accounting_core_unit_tests": True,
            "gateway_unit_tests": False,
            "gateway_live_smoke": False,
            "provider_credential_current_process": False,
            "ready_for_confirmatory_run": False,
        },
    }


def test_valid_prospective_protocol_is_not_misreported_as_ready():
    result = validate(protocol(), {"task_ids": [str(i) for i in range(18)]})
    assert result["valid"] is True
    assert result["ready_for_confirmatory_run"] is False
    assert "HTTP gateway transport is not implemented" in result["warnings"]


def test_ready_flag_must_equal_all_readiness_gates():
    payload = protocol()
    payload["readiness_gates"]["ready_for_confirmatory_run"] = True
    result = validate(payload, {"task_ids": [str(i) for i in range(18)]})
    assert result["valid"] is False
    assert any("conjunction" in error for error in result["errors"])
