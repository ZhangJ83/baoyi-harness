import copy
import hashlib
import json
from pathlib import Path

from benchmarks.validate_real_controller_ablation_results import ARTIFACTS, CHECKS, validate

ROOT = Path(__file__).resolve().parents[1]


def _fixture(tmp_path: Path):
    protocol_path = ROOT / "benchmarks/real_controller_ablation_v1.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    cells = []
    for task in protocol["tasks"]:
        for policy in protocol["policies"]:
            artifacts = {}
            for kind in ARTIFACTS:
                path = tmp_path / f"{task['id']}__{policy}__{kind}.txt"
                path.write_text(f"{task['id']} {policy} {kind}", encoding="utf-8")
                artifacts[kind] = {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            cells.append({
                "task_id": task["id"], "policy": policy, "infrastructure_valid": True,
                "policy_manifest": {"policy": policy, "policy_runtime_sha256": protocol["policy_runtime"]["sha256"], "max_model_steps": protocol["generation_step_caps"][policy]},
                "usage": {"authoritative": True, "generated_output_tokens": 1000, "covered_local_tool_calls": 10, "wall_seconds": 10},
                "artifacts": artifacts, "evaluation": {name: True for name in CHECKS}, "artifact_success": True,
            })
    raw = {"schema":"real-controller-ablation-raw-v1", "protocol_sha256":hashlib.sha256(protocol_path.read_bytes()).hexdigest(), "protocol_frozen_before_run":True, "cells":cells}
    return protocol, raw["protocol_sha256"], raw


def test_complete_artifact_backed_matrix_is_recomputed(tmp_path: Path):
    protocol, sha, raw = _fixture(tmp_path)
    result = validate(protocol, sha, raw, tmp_path)
    assert result["valid"] is True
    assert result["all_48_cells_valid"] is True
    assert result["statistics"]["n_tasks"] == 12
    assert result["statistics"]["contrasts"]["cegar_h_minus_direct"]["exact_mcnemar_p"] == 1.0


def test_missing_cell_and_over_budget_fail_closed(tmp_path: Path):
    protocol, sha, raw = _fixture(tmp_path)
    raw["cells"].pop()
    raw["cells"][0]["usage"]["generated_output_tokens"] = 4501
    result = validate(protocol, sha, raw, tmp_path)
    assert result["valid"] is False
    assert any("complete_unique_48_cell_matrix_required" in error for error in result["errors"])
    assert any("over_budget" in error for error in result["errors"])


def test_forged_success_and_artifact_hash_fail_closed(tmp_path: Path):
    protocol, sha, raw = _fixture(tmp_path)
    raw["cells"][0]["evaluation"]["fresh_evidence"] = False
    raw["cells"][1]["artifacts"]["pptx"]["sha256"] = "0" * 64
    result = validate(protocol, sha, raw, tmp_path)
    assert result["valid"] is False
    assert any("reported_success_disagrees" in error for error in result["errors"])
    assert any("artifact_set_missing_or_hash_invalid" in error for error in result["errors"])
