"""Requirement-by-requirement gate for the full research objective.

This is intentionally stricter than the pilot claim gate. It reports exactly
which requested deliverables are proven by durable artifacts and refuses to
promote slices, fixtures, or local reviews to final evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


def read_json(path: Path, default: dict | list | None = None):
    if not path.is_file():
        return {} if default is None else default
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _external_review(root: Path) -> tuple[bool, list[str]]:
    attestation_path = root / "research/review/external_review_attestation.json"
    attestation = read_json(attestation_path)
    report_value = attestation.get("report_path")
    if not isinstance(report_value, str) or not report_value:
        return False, [str(attestation_path)]
    report = (root / report_value).resolve()
    review_root = (root / "research/review").resolve()
    try:
        report.relative_to(review_root)
    except ValueError:
        return False, [str(attestation_path), str(report)]
    date = attestation.get("review_date")
    achieved = bool(
        attestation.get("schema") == "independent-external-review-attestation-v1"
        and attestation.get("independent") is True
        and attestation.get("reviewer_non_author") is True
        and attestation.get("conflicts_declared") is True
        and isinstance(date, str)
        and re.fullmatch(r"\d{4}-\d{2}-\d{2}", date)
        and report.is_file()
        and attestation.get("report_sha256") == _sha256(report)
    )
    return achieved, [str(attestation_path), str(report)]


def build(root: Path) -> dict:
    audit = read_json(root / "workspace/results/completion_audit_current.json")
    claim = read_json(root / "workspace/results/claims_gate_current.json")
    v3_validation = read_json(root / "workspace/results/matched_protocol_v3_validation.json")
    v3_smoke = read_json(root / "workspace/results/matched_v3_live_smoke_validation.json")
    v3_parity = read_json(root / "workspace/results/budget_parity_v3.json")
    real_ablation = read_json(root / "workspace/results/real_controller_ablation.json")
    real_ablation_protocol = read_json(root / "workspace/results/real_controller_ablation_protocol_validation.json")
    real_ablation_execution = read_json(root / "workspace/results/real_controller_execution_readiness.json")
    real_ablation_protocol_path = root / "benchmarks/real_controller_ablation_v1.json"
    ppt_protocol_path = root / "benchmarks/pptbench_model_eval_v2.json"
    ppt_protocol_validation = read_json(root / "workspace/results/pptbench_model_eval_v2_validation.json")
    ppt_execution_readiness = read_json(root / "workspace/results/pptbench_model_eval_v2_execution_readiness.json")
    ppt_evaluation = read_json(root / "workspace/results/model_generated_ppt_evaluation.json")
    matrix = read_json(root / "research/paper_experiment_matrix.json", {"experiments": []})
    exhaustive = read_json(root / "workspace/results/exhaustive_theory_check.json")
    paired_ablation = root / "workspace/results/paired_synthetic_ablation.json"
    swe_v2 = read_json(root / "workspace/results/official_swe_verified_v2_validation.json")
    external_review_ok, external_review_evidence = _external_review(root)
    real_policies = set(real_ablation.get("policies", []))
    required_policies = {"direct", "always_verify", "evidence_only", "cegar_h"}
    real_ablation_ok = bool(
        real_ablation.get("schema") == "real-controller-causal-ablation-v1"
        and real_ablation.get("valid") is True
        and real_ablation.get("artifact_backed") is True
        and real_ablation.get("protocol_frozen_before_run") is True
        and real_ablation.get("paired_task_set") is True
        and real_ablation.get("n_tasks", 0) >= 12
        and required_policies.issubset(real_policies)
        and real_ablation.get("predefined_outcomes") is True
        and real_ablation.get("all_48_cells_valid") is True
        and real_ablation.get("statistics_precomputed_from_cells") is True
        and real_ablation_protocol_path.is_file()
        and real_ablation.get("protocol_sha256") == _sha256(real_ablation_protocol_path)
        and real_ablation.get("statistics", {}).get("n_tasks") == 12
        and set(real_ablation.get("statistics", {}).get("contrasts", {}))
        == {"cegar_h_minus_direct", "cegar_h_minus_always_verify", "cegar_h_minus_evidence_only"}
    )
    blind = ppt_evaluation.get("blind_review", {})
    ppt_performance = ppt_evaluation.get("performance", {})
    ppt_contrasts = ppt_performance.get("contrasts", {})
    ppt_evaluation_ok = bool(
        ppt_evaluation.get("schema") == "model-generated-ppt-evaluation-v1"
        and ppt_evaluation.get("valid") is True
        and ppt_protocol_path.is_file()
        and ppt_evaluation.get("protocol_sha256") == _sha256(ppt_protocol_path)
        and ppt_evaluation.get("model_generated") is True
        and ppt_evaluation.get("protocol_frozen_before_generation") is True
        and ppt_evaluation.get("paired_task_set") is True
        and ppt_evaluation.get("n_tasks", 0) >= 12
        and ppt_evaluation.get("n_systems", 0) >= 3
        and ppt_evaluation.get("rendered_decks", 0)
        >= ppt_evaluation.get("n_tasks", 0) * ppt_evaluation.get("n_systems", 0)
        and blind.get("complete") is True
        and blind.get("n_reviewers", 0) >= 2
        and isinstance(blind.get("agreement_metric"), (int, float))
        and blind.get("forms_locked_before_adjudication") is True
        and isinstance(blind.get("raw_score_files_sha256"), list)
        and len(blind.get("raw_score_files_sha256")) >= 2
        and ppt_performance.get("unit") == "task"
        and set(ppt_contrasts) == {"xiaopu_minus_claude_code", "xiaopu_minus_codex"}
        and all(value.get("n_tasks") == 12 and isinstance(value.get("paired_bootstrap_ci95"), list)
                and isinstance(value.get("paired_permutation_p"), (int, float))
                and isinstance(value.get("holm_adjusted_p"), (int, float))
                for value in ppt_contrasts.values())
    )
    checks = {
        "infrastructure_readiness": {
            "achieved": audit.get("checks", {}).get("infrastructure_readiness", {}).get("status") == "ready",
            "evidence": audit.get("checks", {}).get("infrastructure_readiness", {}).get("evidence"),
            "required": "post-reboot pagefile and virtual-memory readiness probe passes",
        },
        "official_terminal_bench_full": {
            "achieved": audit.get("checks", {}).get("official_terminal_bench", {}).get("status") == "full_benchmark",
            "evidence": audit.get("checks", {}).get("official_terminal_bench", {}).get("evidence"),
            "required": "all pinned official task IDs scored by the official scorer",
        },
        "official_swe_bench_verified_full": {
            "achieved": audit.get("checks", {}).get("official_swe_bench_verified", {}).get("status") == "official_full_benchmark",
            "evidence": audit.get("checks", {}).get("official_swe_bench_verified", {}).get("evidence"),
            "required": "full declared SWE-bench Verified universe scored by the official evaluator",
        },
        "official_swe_verified_protocol_ready": {
            "achieved": bool(swe_v2.get("valid"))
            and swe_v2.get("n_frozen_instances", 0) >= 10
            and swe_v2.get("official_dataset_size") == 500
            and swe_v2.get("official_evaluator_present") is True
            and swe_v2.get("execution_ready") is True
            and swe_v2.get("checkout_materialization_smoke_valid") is True,
            "evidence": [
                "benchmarks/official_swe_verified_v2.json",
                "workspace/results/official_swe_verified_v2_validation.json",
            ],
            "required": "at least 10 frozen official instances, 500-row metadata, pinned runner/evaluator, and a real image-to-base-commit checkout smoke",
        },
        "matched_protocol_v3_readiness": {
            "achieved": bool(v3_validation.get("valid")) and bool(v3_smoke.get("smoke_valid")),
            "evidence": [
                "workspace/results/matched_protocol_v3_validation.json",
                "workspace/results/matched_v3_live_smoke_validation.json",
            ],
            "required": "valid frozen protocol plus three-system non-scored live hook/gateway smoke",
        },
        "matched_claude_codex_protocol": {
            "achieved": bool(v3_parity.get("budget_parity_verified"))
            and bool(v3_parity.get("task_set_parity")),
            "evidence": [
                "benchmarks/matched_protocol_v3.json",
                "workspace/results/budget_parity_v3.json",
            ],
            "required": "same 18 task IDs plus verified generated-output/tool/wall-time envelope for all systems",
        },
        "competitor_superiority_statistics": {
            "achieved": bool(claim.get("superiority_supported")),
            "evidence": "workspace/results/claims_gate_current.json",
            "required": "paired CI, exact test, and preregistered minimum n all pass",
        },
        "synthetic_component_ablations": {
            "achieved": paired_ablation.is_file() and any(
                e.get("exp_id") == "E8"
                and e.get("status") in {"completed", "completed_synthetic_only"}
                for e in matrix.get("experiments", [])
            ),
            "evidence": str(paired_ablation),
            "required": "same-stream synthetic component ablations with confidence intervals",
        },
        "real_controller_causal_ablation": {
            "achieved": real_ablation_ok,
            "evidence": "workspace/results/real_controller_ablation.json",
            "required": "at least 12 paired real artifact tasks under frozen direct/always-verify/evidence-only/CEGAR-H policies",
        },
        "real_controller_protocol_ready": {
            "achieved": bool(real_ablation_protocol.get("valid"))
            and real_ablation_protocol.get("n_tasks") == 12
            and real_ablation_protocol.get("n_policies") == 4
            and real_ablation_protocol.get("expected_cells") == 48
            and real_ablation_execution.get("valid") is True
            and real_ablation_execution.get("scheduled_cells") == 48
            and real_ablation_execution.get("real_pdf_png_smoke") is True,
            "evidence": [
                "benchmarks/real_controller_ablation_v1.json",
                "workspace/results/real_controller_ablation_protocol_validation.json",
                "workspace/results/real_controller_execution_readiness.json",
            ],
            "required": "frozen 12-task by 4-policy contract plus hash-matched 48-cell runner and real PDF/PNG common-evaluator smoke",
        },
        "theory_and_falsification": {
            "achieved": (
                (root / "research/THEORY_APPENDIX.md").is_file()
                and exhaustive.get("binary", {}).get("violations") == 0
                and exhaustive.get("multi_action", {}).get("violations") == 0
            ),
            "evidence": "research/THEORY_APPENDIX.md; workspace/results/exhaustive_theory_check.json",
            "required": "explicit assumptions, derivations, and falsification checks",
        },
        "model_generated_ppt_evaluation": {
            "achieved": ppt_evaluation_ok,
            "evidence": "workspace/results/model_generated_ppt_evaluation.json",
            "required": "at least 12 paired tasks across 3 systems, all decks rendered, with >=2-reviewer blind scoring and agreement",
        },
        "model_generated_ppt_protocol_ready": {
            "achieved": bool(ppt_protocol_validation.get("valid"))
            and bool(ppt_protocol_validation.get("assets_ready"))
            and bool(ppt_execution_readiness.get("valid"))
            and ppt_execution_readiness.get("scheduled_cells") == 36
            and ppt_execution_readiness.get("real_powerpoint_pdf_png_smoke") is True,
            "evidence": [
                "benchmarks/pptbench_model_eval_v2.json",
                "workspace/results/pptbench_model_eval_v2_validation.json",
                "workspace/results/pptbench_model_eval_v2_execution_readiness.json",
            ],
            "required": "frozen 12-task/3-system protocol, six hash-pinned inputs, 36-cell version-pinned dry-run, and real PowerPoint render smoke",
        },
        "external_independent_review": {
            "achieved": external_review_ok,
            "evidence": external_review_evidence,
            "required": "dated, hash-pinned independent non-author report with conflict declaration",
        },
    }
    return {
        "kind": "xiaopu_full_objective_gate",
        "objective_complete": all(item["achieved"] for item in checks.values()),
        "checks": checks,
        "claim_boundary": "a false check is an evidence gap, not a runtime failure",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = build(args.root.resolve())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
