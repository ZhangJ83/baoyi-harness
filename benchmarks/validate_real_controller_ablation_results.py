"""Recompute the 48-cell real-controller result from artifact-backed raw cells."""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import random
from pathlib import Path

POLICIES = ("direct", "always_verify", "evidence_only", "cegar_h")
ARTIFACTS = {"pptx", "pdf", "slide_pngs", "structural_report", "pixel_audit", "trace", "usage_ledger", "timing"}
CHECKS = {"pptx_opens", "slide_bounds", "required_text", "pdf_complete", "png_complete", "no_unintended_overlap", "no_overflow", "no_placeholder", "fresh_evidence"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _exact_mcnemar(a: list[bool], b: list[bool]) -> float:
    n10 = sum(x and not y for x, y in zip(a, b))
    n01 = sum(y and not x for x, y in zip(a, b))
    n = n10 + n01
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(0, min(n10, n01) + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def _bootstrap_delta(a: list[bool], b: list[bool], repeats: int = 5000) -> list[float]:
    rng = random.Random(20260811)
    n = len(a)
    values = []
    for _ in range(repeats):
        ix = [rng.randrange(n) for _ in range(n)]
        values.append(sum(float(a[i]) - float(b[i]) for i in ix) / n)
    values.sort()
    return [values[int(0.025 * repeats)], values[min(repeats - 1, int(0.975 * repeats))]]


def _paired_permutation(deltas: list[float]) -> float | None:
    if not deltas:
        return None
    observed = abs(sum(deltas) / len(deltas))
    extreme = 0
    total = 2 ** len(deltas)
    for signs in itertools.product((-1, 1), repeat=len(deltas)):
        value = abs(sum(sign * delta for sign, delta in zip(signs, deltas)) / len(deltas))
        extreme += value >= observed - 1e-12
    return extreme / total


def _safe_artifact(root: Path, item: dict, *, allow_absent: bool = False) -> bool:
    if item.get("present") is False:
        return allow_absent and isinstance(item.get("absence_reason"), str) and bool(item.get("absence_reason"))
    value = item.get("path")
    if not isinstance(value, str) or not value:
        return False
    path = (root / value).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        return False
    return path.is_file() and item.get("sha256") == digest(path)


def validate(protocol: dict, protocol_sha256: str, raw: dict, artifact_root: Path) -> dict:
    errors: list[str] = []
    task_ids = [x["id"] for x in protocol.get("tasks", [])]
    expected = {(task, policy) for task in task_ids for policy in POLICIES}
    cells = raw.get("cells", [])
    keys = [(x.get("task_id"), x.get("policy")) for x in cells]
    if raw.get("schema") != "real-controller-ablation-raw-v1":
        errors.append("raw_schema_invalid")
    if raw.get("protocol_sha256") != protocol_sha256 or raw.get("protocol_frozen_before_run") is not True:
        errors.append("protocol_hash_or_freeze_invalid")
    if len(cells) != 48 or len(keys) != len(set(keys)) or set(keys) != expected:
        errors.append("complete_unique_48_cell_matrix_required")
    derived: dict[tuple[str, str], dict] = {}
    budget = protocol.get("budget", {})
    runtime_hash = protocol.get("policy_runtime", {}).get("sha256")
    for cell in cells:
        key = (cell.get("task_id"), cell.get("policy"))
        prefix = f"{key[0]}:{key[1]}"
        cell_errors: list[str] = []
        if key not in expected:
            cell_errors.append("unexpected_cell")
        if cell.get("infrastructure_valid") is not True:
            cell_errors.append("infrastructure_invalid")
        manifest = cell.get("policy_manifest", {})
        if (manifest.get("policy") != key[1] or manifest.get("policy_runtime_sha256") != runtime_hash
                or manifest.get("max_model_steps") != protocol.get("generation_step_caps", {}).get(key[1])):
            cell_errors.append("policy_manifest_invalid")
        usage = cell.get("usage", {})
        if usage.get("authoritative") is not True:
            cell_errors.append("usage_not_authoritative")
        for name, cap in (("generated_output_tokens", budget.get("max_generated_output_tokens")), ("covered_local_tool_calls", budget.get("max_covered_local_tool_calls")), ("wall_seconds", budget.get("max_agent_wall_seconds"))):
            value = usage.get(name)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0 or value > cap:
                cell_errors.append(f"{name}_invalid_or_over_budget")
        checks = cell.get("evaluation", {})
        if set(checks) != CHECKS or any(not isinstance(checks.get(name), bool) for name in CHECKS):
            cell_errors.append("evaluation_contract_invalid")
            success = False
        else:
            success = all(checks.values())
        artifacts = cell.get("artifacts", {})
        output_artifacts = {"pptx", "pdf", "slide_pngs"}
        if set(artifacts) != ARTIFACTS or not all(
            _safe_artifact(artifact_root, artifacts[name], allow_absent=(not success and name in output_artifacts))
            for name in ARTIFACTS if name in artifacts
        ):
            cell_errors.append("artifact_set_missing_or_hash_invalid")
        if cell.get("artifact_success") is not success:
            cell_errors.append("reported_success_disagrees_with_recomputed_success")
        if cell_errors:
            errors.extend(f"{prefix}:{error}" for error in cell_errors)
        derived[key] = {"success": success, "usage": usage}
    statistics = {}
    if not errors:
        by_policy = {policy: [derived[(task, policy)]["success"] for task in task_ids] for policy in POLICIES}
        contrasts = {}
        for other in ("direct", "always_verify", "evidence_only"):
            a, b = by_policy["cegar_h"], by_policy[other]
            matched_cost = [derived[(task, "cegar_h")]["usage"]["covered_local_tool_calls"] - derived[(task, other)]["usage"]["covered_local_tool_calls"] for task, x, y in zip(task_ids, a, b) if x and y]
            contrasts[f"cegar_h_minus_{other}"] = {
                "success_delta": sum(a) / 12 - sum(b) / 12,
                "paired_bootstrap_ci95": _bootstrap_delta(a, b),
                "exact_mcnemar_p": _exact_mcnemar(a, b),
                "matched_success_cost_delta": sum(matched_cost) / len(matched_cost) if matched_cost else None,
                "paired_cost_permutation_p": _paired_permutation(matched_cost),
            }
        statistics = {"n_tasks": 12, "success_rate": {p: sum(v) / 12 for p, v in by_policy.items()}, "contrasts": contrasts}
    valid = not errors
    return {
        "schema": "real-controller-causal-ablation-v1",
        "valid": valid,
        "artifact_backed": valid,
        "protocol_frozen_before_run": raw.get("protocol_frozen_before_run") is True,
        "protocol_sha256": protocol_sha256,
        "paired_task_set": valid,
        "predefined_outcomes": True,
        "all_48_cells_valid": valid and len(cells) == 48,
        "n_tasks": 12,
        "policies": list(POLICIES),
        "statistics_precomputed_from_cells": valid,
        "statistics": statistics,
        "errors": errors,
        "claim_boundary": "valid means the frozen causal dataset is complete; superiority still depends on the reported estimates and uncertainty",
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--protocol", type=Path, required=True)
    p.add_argument("--raw", type=Path, required=True)
    p.add_argument("--artifact-root", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    protocol = json.loads(a.protocol.read_text(encoding="utf-8"))
    raw = json.loads(a.raw.read_text(encoding="utf-8"))
    result = validate(protocol, digest(a.protocol), raw, a.artifact_root.resolve())
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
