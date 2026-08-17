import copy
import hashlib
import json
from pathlib import Path

import pytest

from agent.controller_policies import POLICIES as RUNTIME_POLICIES
from benchmarks.validate_real_controller_ablation_protocol import digest, validate


ROOT = Path(__file__).resolve().parents[1]


def _create_hermetic_controller_protocol(tmp_path: Path) -> tuple[dict, Path]:
    source_file = tmp_path / "benchmarks/source_protocol.json"
    runtime_file = tmp_path / "agent/controller_policies.py"
    harness_file = tmp_path / "agent/harness.py"

    for f in (source_file, runtime_file, harness_file):
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(f"dummy content for {f.name}", encoding="utf-8")

    task_ids = [f"task-{i+1:02d}" for i in range(12)]
    source_file.write_text(
        json.dumps({"tasks": [{"id": tid, "kind": "create"} for tid in task_ids]}),
        encoding="utf-8",
    )

    protocol = {
        "schema": "real-controller-ablation-protocol-v1",
        "status": "prospective_not_run",
        "registered_at": "2026-08-11T05:59:00+08:00",
        "amended_at": "2026-08-17T12:00:00+08:00",
        "amendment_boundary": "before any live controller cell was run, test boundary",
        "task_source": {
            "path": str(source_file.relative_to(tmp_path)).replace("\\", "/"),
            "sha256": digest(source_file),
        },
        "paired_task_set": True,
        "n_tasks": 12,
        "n_cells": 48,
        "tasks": [{"id": tid, "kind": "create"} for tid in task_ids],
        "policies": ["direct", "always_verify", "evidence_only", "cegar_h"],
        "policy_implementation_required": True,
        "generation_step_caps": {name: spec.max_model_steps for name, spec in RUNTIME_POLICIES.items()},
        "policy_runtime": {
            "path": str(runtime_file.relative_to(tmp_path)).replace("\\", "/"),
            "sha256": digest(runtime_file),
            "harness_path": str(harness_file.relative_to(tmp_path)).replace("\\", "/"),
            "harness_sha256": digest(harness_file),
            "harness_argument": "controller_policy",
        },
        "budget": {
            "max_generated_output_tokens": 4500,
            "max_covered_local_tool_calls": 60,
            "max_agent_wall_seconds": 300,
        },
        "predefined_outcomes": [
            "artifact_success", "verification_count", "generated_output_tokens",
            "covered_local_tool_calls", "wall_seconds", "failure_mode",
        ],
        "order_control": {
            "orders": [
                ["direct", "always_verify", "evidence_only", "cegar_h"],
                ["always_verify", "evidence_only", "cegar_h", "direct"],
                ["evidence_only", "cegar_h", "direct", "always_verify"],
                ["cegar_h", "direct", "always_verify", "evidence_only"],
            ],
        },
        "required_artifacts_per_cell": [
            "pptx", "pdf", "slide_pngs", "structural_report", "pixel_audit", "trace", "usage_ledger", "timing",
        ],
    }
    return protocol, tmp_path


def test_validator_accepts_valid_hermetic_controller_protocol(tmp_path: Path):
    protocol, root = _create_hermetic_controller_protocol(tmp_path)
    result = validate(protocol, root)
    assert result["valid"] is True
    assert result["expected_cells"] == 48
    assert result["result_available"] is False


def test_real_controller_protocol_rejects_budget_and_task_drift(tmp_path: Path):
    protocol, root = _create_hermetic_controller_protocol(tmp_path)
    protocol["budget"]["max_generated_output_tokens"] += 1
    protocol["tasks"].pop()
    result = validate(protocol, root)
    assert result["valid"] is False
    assert "budget_contract_invalid" in result["errors"]
    assert "paired_12_by_4_contract_invalid" in result["errors"]


def test_real_controller_protocol_rejects_policy_runtime_drift(tmp_path: Path):
    protocol, root = _create_hermetic_controller_protocol(tmp_path)
    protocol["policy_runtime"]["sha256"] = "0" * 64
    result = validate(protocol, root)
    assert result["valid"] is False
    assert "policy_runtime_missing_or_drifted" in result["errors"]


def test_real_controller_protocol_rejects_generation_step_drift(tmp_path: Path):
    protocol, root = _create_hermetic_controller_protocol(tmp_path)
    protocol["generation_step_caps"]["cegar_h"] = 25
    result = validate(protocol, root)
    assert result["valid"] is False
    assert "generation_step_caps_do_not_match_runtime" in result["errors"]


@pytest.mark.protocol_lock
def test_canonical_real_controller_protocol_is_frozen_and_paired():
    protocol_path = ROOT / "benchmarks/real_controller_ablation_v1.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    result = validate(protocol, ROOT)
    assert result["valid"] is True
    assert result["expected_cells"] == 48
    assert result["result_available"] is False
