"""Fail-closed validation for the prospective real-controller ablation."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from agent.controller_policies import POLICIES as RUNTIME_POLICIES

POLICIES = {"direct", "always_verify", "evidence_only", "cegar_h"}
OUTCOMES = {"artifact_success", "verification_count", "generated_output_tokens", "covered_local_tool_calls", "wall_seconds", "failure_mode"}


def digest(path: Path) -> str:
    data = path.read_bytes()
    if path.suffix.lower() in {".py", ".json", ".md", ".txt", ".yml", ".yaml", ".toml"}:
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def validate(protocol: dict, root: Path) -> dict:
    errors: list[str] = []
    source = protocol.get("task_source", {})
    source_path = root / str(source.get("path", ""))
    source_data = {}
    if not source_path.is_file():
        errors.append("task_source_missing")
    else:
        if digest(source_path) != source.get("sha256"):
            errors.append("task_source_hash_mismatch")
        source_data = json.loads(source_path.read_text(encoding="utf-8"))
    tasks = protocol.get("tasks", [])
    ids = [x.get("id") for x in tasks]
    if protocol.get("schema") != "real-controller-ablation-protocol-v1" or protocol.get("status") != "prospective_not_run":
        errors.append("schema_or_status_invalid")
    if not protocol.get("amended_at") or "before any live controller cell" not in protocol.get("amendment_boundary", ""):
        errors.append("pre_run_amendment_boundary_missing")
    if len(tasks) != 12 or protocol.get("n_tasks") != 12 or protocol.get("n_cells") != 48 or len(ids) != len(set(ids)):
        errors.append("paired_12_by_4_contract_invalid")
    if source_data and ids != [x.get("id") for x in source_data.get("tasks", [])]:
        errors.append("task_ids_do_not_match_frozen_source")
    if set(protocol.get("policies", {})) != POLICIES or protocol.get("policy_implementation_required") is not True:
        errors.append("policy_contract_invalid")
    if protocol.get("generation_step_caps") != {name: spec.max_model_steps for name, spec in RUNTIME_POLICIES.items()}:
        errors.append("generation_step_caps_do_not_match_runtime")
    runtime = protocol.get("policy_runtime", {})
    runtime_path = root / str(runtime.get("path", ""))
    harness_path = root / str(runtime.get("harness_path", ""))
    if (not runtime_path.is_file() or digest(runtime_path) != runtime.get("sha256")
            or not harness_path.is_file() or digest(harness_path) != runtime.get("harness_sha256")
            or runtime.get("harness_argument") != "controller_policy"
            or set(protocol.get("policies", {})) != set(RUNTIME_POLICIES)):
        errors.append("policy_runtime_missing_or_drifted")
    budget = protocol.get("budget", {})
    if budget != {"max_generated_output_tokens": 4500, "max_covered_local_tool_calls": 60, "max_agent_wall_seconds": 300}:
        errors.append("budget_contract_invalid")
    if set(protocol.get("predefined_outcomes", {})) != OUTCOMES:
        errors.append("outcome_contract_invalid")
    orders = protocol.get("order_control", {}).get("orders", [])
    if len(orders) != 4 or any(set(order) != POLICIES for order in orders):
        errors.append("order_control_invalid")
    required = set(protocol.get("required_artifacts_per_cell", []))
    if not {"pptx","pdf","slide_pngs","structural_report","pixel_audit","trace","usage_ledger","timing"}.issubset(required):
        errors.append("artifact_contract_incomplete")
    return {"schema":"real-controller-ablation-protocol-validation-v1","valid":not errors,"n_tasks":len(tasks),"n_policies":len(protocol.get("policies", {})),"expected_cells":len(tasks)*len(protocol.get("policies", {})),"errors":errors,"result_available":False,"claim_boundary":"protocol readiness only; no causal result"}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--protocol", type=Path, required=True)
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    result = validate(json.loads(a.protocol.read_text(encoding="utf-8")), a.root.resolve())
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(result))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
