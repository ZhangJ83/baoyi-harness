"""Verify the final zip contains source and flattened evidence artifacts."""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path


REQUIRED = {
    "agent/harness.py": "source",
    "benchmarks/objective_gate.py": "source",
    "research/PAPER_DRAFT.md": "research",
    "research/ICLR_REVIEW_ALIGNMENT.md": "research",
    "benchmarks/official_swe_verified_v2.json": "source",
    "benchmarks/real_controller_ablation_v1.json": "source",
    "benchmarks/run_real_controller_ablation.py": "source",
    "benchmarks/prepare_pptbench_blind_review.py": "source",
    "benchmarks/lock_pptbench_review_form.py": "source",
    "benchmarks/validate_model_generated_ppt_eval.py": "source",
    "benchmarks/run_pptbench_model_eval_v2.py": "source",
    "benchmarks/validate_pptbench_execution_readiness.py": "source",
    "objective_gate_current.json": "flattened_evidence",
    "evidence_manifest.json": "flattened_evidence",
    "official_swe_verified_v2_validation.json": "flattened_evidence",
    "real_controller_ablation_protocol_validation.json": "flattened_evidence",
    "real_controller_execution_readiness.json": "flattened_evidence",
    "pptbench_model_eval_v2_execution_readiness.json": "flattened_evidence",
    "workspace/results/pptbench_model_eval_v2_execution_dry_run/run_manifest.json": "execution_evidence",
    "workspace/results/controller_evaluator_smoke/common_evaluation/rendered/deck.pdf": "render_evidence",
    "ppt_harness_demo/final-evidence-report.json": "flattened_evidence",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    with zipfile.ZipFile(args.archive) as archive:
        names = {name.replace("\\", "/").rstrip("/") for name in archive.namelist()}
    rows = [{"path": path, "kind": kind, "present": path in names} for path, kind in REQUIRED.items()]
    missing = [row["path"] for row in rows if not row["present"]]
    result = {
        "schema": "submission-archive-verification-v1",
        "archive": str(args.archive),
        "valid": not missing,
        "missing": missing,
        "required": rows,
        "layout_note": "workspace evidence is intentionally flattened by the Windows archive step",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
