import copy
import json
from pathlib import Path

from benchmarks.validate_real_controller_ablation_protocol import validate

ROOT = Path(__file__).resolve().parents[1]


def load():
    return json.loads((ROOT / "benchmarks/real_controller_ablation_v1.json").read_text(encoding="utf-8"))


def test_real_controller_protocol_is_frozen_and_paired():
    result = validate(load(), ROOT)
    assert result["valid"] is True
    assert result["expected_cells"] == 48
    assert result["result_available"] is False


def test_real_controller_protocol_rejects_budget_and_task_drift():
    protocol = copy.deepcopy(load())
    protocol["budget"]["max_generated_output_tokens"] += 1
    protocol["tasks"].pop()
    result = validate(protocol, ROOT)
    assert result["valid"] is False
    assert "budget_contract_invalid" in result["errors"]
    assert "paired_12_by_4_contract_invalid" in result["errors"]


def test_real_controller_protocol_rejects_policy_runtime_drift():
    protocol = copy.deepcopy(load())
    protocol["policy_runtime"]["sha256"] = "0" * 64
    result = validate(protocol, ROOT)
    assert result["valid"] is False
    assert "policy_runtime_missing_or_drifted" in result["errors"]


def test_real_controller_protocol_rejects_generation_step_drift():
    protocol = copy.deepcopy(load())
    protocol["generation_step_caps"]["cegar_h"] = 25
    result = validate(protocol, ROOT)
    assert result["valid"] is False
    assert "generation_step_caps_do_not_match_runtime" in result["errors"]
