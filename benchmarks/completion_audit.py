"""Machine-readable completion audit for the research objective."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def exists(root: Path, rel: str) -> bool:
    return (root / rel).is_file()


def evidence_exists(root: Path, evidence: str | list[str]) -> bool:
    paths = evidence if isinstance(evidence, list) else [evidence]
    return all(Path(path).is_file() if Path(path).is_absolute() else exists(root, path) for path in paths)


def official_tb(root: Path) -> dict:
    candidates = sorted(
        (root / "workspace/results/official_tb_xiaopu").glob("**/results.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    path = candidates[0] if candidates else root / "workspace/results/official_tb_xiaopu/results.json"
    if not path.is_file():
        return {"status": "pending", "evidence": str(path)}
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    rows = data.get("results", [])
    dataset_root = root.parent / "official_refs" / "terminal-bench" / "original-tasks"
    dataset_ids = {p.name for p in dataset_root.iterdir() if p.is_dir()} if dataset_root.is_dir() else set()
    result_ids = {r.get("task_id") or r.get("task_name") for r in rows}
    result_ids.discard(None)
    coverage = (len(result_ids & dataset_ids) / len(dataset_ids)) if dataset_ids else None
    full = bool(dataset_ids) and len(result_ids) == len(dataset_ids) and result_ids == dataset_ids
    return {
        "status": "full_benchmark" if full else ("official_slice" if len(rows) >= 12 else "pilot_only"),
        "evidence": str(path),
        "tasks": len(rows),
        "dataset_task_count": len(dataset_ids) if dataset_ids else None,
        "coverage_fraction": coverage,
        "resolved": sum(bool(r.get("is_resolved")) for r in rows),
        "accuracy": data.get("accuracy"),
        "note": "full-benchmark status still requires the declared benchmark task universe",
    }


def official_swe(root: Path) -> dict:
    pilot_reports = sorted(
        root.glob("xiaopu-deepseek-v4-flash*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if pilot_reports:
        reports = [json.loads(p.read_text(encoding="utf-8")) for p in pilot_reports]
        total = sum(int(d.get("total_instances") or 0) for d in reports)
        resolved = sum(int(d.get("resolved_instances") or 0) for d in reports)
        status = "multi_instance_score_eligible" if total >= 10 else "agent_pilot_only"
        local_sample = root / "research/swe_verified_sample.json"
        local_count = None
        if local_sample.is_file():
            try:
                local_count = len(json.loads(local_sample.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                local_count = None
        return {"status": status, "evidence": [str(p) for p in pilot_reports],
                "resolved": resolved, "total": total,
                "local_sample_count": local_count,
                "score_eligible": True,
                "note": "official evaluator reports; full Verified score requires the declared benchmark universe"}
    candidates = sorted(
        (root / "workspace/results/official_swe_verified").glob("oracle_smoke_status_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if candidates:
        data = json.loads(candidates[0].read_text(encoding="utf-8"))
        return {"status": "oracle_infrastructure_validated", "evidence": str(candidates[0]),
                "resolved": data.get("resolved_instances"), "total": data.get("total_instances"),
                "score_eligible": False}
    return {"status": "pending", "evidence": "workspace/results/official_swe_verified/oracle_smoke_status.json",
            "reason": "official Docker evaluator has not reached test execution"}


def pptbench(root: Path) -> dict:
    path = root / "workspace/results/pptbench_structural_smoke_latest.json"
    if not path.is_file():
        path = root / "workspace/results/pptbench_structural_smoke.json"
    if not path.is_file():
        return {"status": "pending", "evidence": str(path)}
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("tasks", [])
    return {
        "status": "structural_smoke_only",
        "evidence": str(path),
        "tasks": len(rows),
        "mean_score": data.get("mean_score"),
        "deterministic": all(r.get("deterministic") is True for r in rows),
        "note": "deterministic fixtures; not model-generated PPTBench performance",
    }


def ppt_controlled_demo(root: Path) -> dict:
    """Report the separate controlled rendered demo without promoting it to PPTBench."""
    path = root / "workspace/results/ppt_harness_demo/final-evidence-report.json"
    if not path.is_file():
        return {"status": "pending", "evidence": str(path)}
    data = json.loads(path.read_text(encoding="utf-8"))
    audit = data.get("rendered_visual_audit", {})
    return {
        "status": "controlled_rendered_demo" if data.get("rendered_png_count") == 4 and audit.get("passed") else "incomplete",
        "evidence": str(path),
        "slides": data.get("slides"),
        "structural_score": data.get("structural_score"),
        "rendered_png_count": data.get("rendered_png_count"),
        "stale_evidence_rejected": data.get("stale_evidence_intervention", {}).get("old_evidence_rejected"),
        "note": "controlled harness demo; not model-generated PPTBench performance",
    }


def infrastructure(root: Path) -> dict:
    path = root / "workspace/results/post_reboot_readiness.json"
    if not path.is_file():
        return {"status": "pending", "evidence": str(path)}
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return {
        "status": "ready" if data.get("ready") is True else "not_ready",
        "evidence": str(path),
        "free_virtual_memory_gb": data.get("free_virtual_memory_gb"),
        "active_pagefile_count": data.get("active_pagefile_count"),
        "note": "official evaluation is forbidden until the readiness probe passes",
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    root = args.root.resolve()
    gate = root / "workspace/results/claims_gate_current.json"
    gate_data = json.loads(gate.read_text(encoding="utf-8")) if gate.is_file() else {}
    protocol_path = root / "benchmarks/official_matched_protocol.json"
    protocol_v3_path = root / "benchmarks/matched_protocol_v3.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8")) if protocol_path.is_file() else {}
    parity = bool(protocol.get("budget_enforcement", {}).get("budget_parity_verified"))
    checks = {
        "official_terminal_bench": official_tb(root),
        "official_swe_bench_verified": official_swe(root),
        "pptbench": pptbench(root),
        "ppt_controlled_rendered_demo": ppt_controlled_demo(root),
        "infrastructure_readiness": infrastructure(root),
        "matched_claude_codex": {
            "status": "achieved" if gate_data.get("claim_allowed") and parity else "pending",
            "evidence": [str(gate), str(protocol_path), str(protocol_v3_path)],
            "reason": None if parity else "no completed matched run has passed the strict parity verifier; v3 enforcement is prospective and not live-smoke-ready",
        },
        "superiority_statistics": {
            "status": "achieved" if gate_data.get("superiority_supported") else "pending",
            "evidence": str(gate),
        },
        "synthetic_ablations": {
            "status": "achieved",
            "evidence": "workspace/results/cegarh_ablation_20seed.json",
        },
        "calibration_shift": {
            "status": "achieved",
            "evidence": "workspace/results/cegarh_calibration_sweep.json",
        },
        "heldout_learned_calibration": {
            "status": "achieved",
            "evidence": "workspace/results/heldout_calibration_metrics.json",
            "note": "20-seed 70/30 held-out bin calibration; synthetic only",
        },
        "theory_bound_check": {
            "status": "achieved",
            "evidence": "workspace/results/theory_bound_check.json",
            "supplementary_evidence": "workspace/results/exhaustive_theory_check.json",
            "note": "randomized plus finite-grid exhaustive consistency checks; not a general proof",
        },
        "skeptical_review": {
            "status": "baseline_only_external_pending",
            "evidence": "research/review/review.md",
        },
    }
    for item in checks.values():
        if "evidence" in item and item["status"] == "achieved" and not evidence_exists(root, item["evidence"]):
            item["status"] = "inconsistent"
    payload = {
        "kind": "xiaopu_completion_audit",
        "objective_complete": all(v["status"] == "achieved" for v in checks.values()),
        "checks": checks,
        "claim_gate": gate_data,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
