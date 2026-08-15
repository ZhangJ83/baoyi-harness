"""Build a deterministic SHA-256 manifest for paper-facing evidence files."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


DEFAULT_PATHS = [
    "agent/controller_policies.py",
    "research/PAPER_DRAFT.md",
    "research/CLAIM_EVIDENCE_MAP.json",
    "research/BEST_PAPER_GAP_MATRIX.md",
    "research/paper_experiment_matrix.json",
    "research/NEXT_EVIDENCE_PLAN.md",
    "research/ICLR_REVIEW_ALIGNMENT.md",
    "research/PPT_VISUAL_REVIEW.md",
    "research/PPT_HARNESS_EVAL_CONTRACT.md",
    "benchmarks/pptbench_model_eval_v2.json",
    "benchmarks/pptbench_review_rubric.md",
    "benchmarks/prepare_pptbench_blind_review.py",
    "benchmarks/lock_pptbench_review_form.py",
    "benchmarks/validate_model_generated_ppt_eval.py",
    "benchmarks/run_pptbench_model_eval_v2.py",
    "benchmarks/validate_pptbench_execution_readiness.py",
    "benchmarks/controller_evaluator_smoke_task.json",
    "benchmarks/official_swe_verified_v2.json",
    "benchmarks/real_controller_ablation_v1.json",
    "benchmarks/validate_real_controller_ablation_results.py",
    "benchmarks/run_real_controller_ablation.py",
    "benchmarks/evaluate_real_controller_cell.py",
    "research/ONE_HOUR_SPRINT_REPORT.md",
    "research/LEDGER_COMPLETENESS_FIX.md",
    "research/BUDGET_PARITY_GATE.md",
    "research/COMPETITOR_STREAM_OBSERVABILITY.md",
    "research/MATCHED_PROTOCOL_V3_DECISION.json",
    "research/DEADLINE_0600_STATUS.md",
    "research/review/EXTERNAL_REVIEW_PACKET.md",
    "research/review/external_review_attestation.example.json",
    "workspace/results/provider_preflight.json",
    "workspace/results/paired_synthetic_ablation_latest.json",
    "workspace/results/offline_budget_sensitivity_20260811.json",
    "workspace/results/budget_parity_current.json",
    "workspace/results/claims_gate_current.json",
    "workspace/results/competitor_stream_observability.json",
    "workspace/results/matched_protocol_v3_validation.json",
    "workspace/results/matched_v3_live_smoke_validation.json",
    "workspace/results/pptbench_model_eval_v2_validation.json",
    "workspace/results/pptbench_model_eval_v2_execution_readiness.json",
    "workspace/results/pptbench_model_eval_v2_execution_dry_run/run_manifest.json",
    "workspace/results/official_swe_verified_v2_validation.json",
    "workspace/results/real_controller_ablation_protocol_validation.json",
    "workspace/results/real_controller_execution_readiness.json",
    "workspace/results/controller_evaluator_smoke/common_evaluation/cell_evaluation.json",
    "workspace/results/controller_evaluator_smoke/common_evaluation/slide_pngs_manifest.json",
    "workspace/results/controller_evaluator_smoke/common_evaluation/rendered/deck.pdf",
    "workspace/results/objective_gate_current.json",
    "workspace/results/one_hour_ppt_score.json",
    "workspace/results/one_hour_ppt_render_audit.json",
    "workspace/results/ppt_harness_demo/final-evidence-report.json",
    "workspace/results/ppt_mutation_coverage.json",
    "workspace/results/claim_evidence_map_validation.json",
    "workspace/results/completion_audit_current.json",
    "workspace/results/evidence_validation_current.json",
]


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    rows = []
    missing = []
    for relative in DEFAULT_PATHS:
        path = root / relative
        if not path.is_file():
            missing.append(relative)
            continue
        rows.append({"path": relative, "bytes": path.stat().st_size, "sha256": digest(path)})
    report = {
        "schema": "evidence-manifest-v1",
        "algorithm": "sha256",
        "valid": not missing,
        "missing": missing,
        "files": rows,
        "boundary": "integrity and presence only; does not validate scientific truth",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    raise SystemExit(0 if report["valid"] else 1)


if __name__ == "__main__":
    main()
