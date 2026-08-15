import json
import hashlib
from pathlib import Path

from benchmarks.objective_gate import build


def test_objective_gate_does_not_promote_structural_ppt_or_local_review(tmp_path: Path):
    (tmp_path / "workspace/results").mkdir(parents=True)
    (tmp_path / "research/review").mkdir(parents=True)
    (tmp_path / "research").mkdir(exist_ok=True)
    (tmp_path / "workspace/results/completion_audit_current.json").write_text(
        json.dumps({"checks": {"official_terminal_bench": {"status": "pilot_only"},
                                 "official_swe_bench_verified": {"status": "agent_pilot_only"}}}),
        encoding="utf-8",
    )
    (tmp_path / "workspace/results/claims_gate_current.json").write_text(
        json.dumps({"claim_allowed": True, "superiority_supported": False}), encoding="utf-8"
    )
    (tmp_path / "research/paper_experiment_matrix.json").write_text(
        json.dumps({"experiments": []}), encoding="utf-8"
    )
    (tmp_path / "benchmarks").mkdir()
    (tmp_path / "benchmarks/official_matched_protocol.json").write_text(
        json.dumps({"budget_enforcement": {"budget_parity_verified": False}}),
        encoding="utf-8",
    )
    result = build(tmp_path)
    assert result["objective_complete"] is False
    assert result["checks"]["model_generated_ppt_evaluation"]["achieved"] is False
    assert result["checks"]["external_independent_review"]["achieved"] is False
    assert result["checks"]["matched_claude_codex_protocol"]["achieved"] is False
    assert result["checks"]["real_controller_causal_ablation"]["achieved"] is False


def test_gate_separates_synthetic_ablation_from_real_causality(tmp_path: Path):
    (tmp_path / "workspace/results").mkdir(parents=True)
    (tmp_path / "research/review").mkdir(parents=True)
    (tmp_path / "research").mkdir(exist_ok=True)
    (tmp_path / "research/paper_experiment_matrix.json").write_text(
        json.dumps({"experiments": [{"exp_id": "E8", "status": "completed"}]}), encoding="utf-8"
    )
    (tmp_path / "workspace/results/paired_synthetic_ablation.json").write_text("{}", encoding="utf-8")
    result = build(tmp_path)
    assert result["checks"]["synthetic_component_ablations"]["achieved"] is True
    assert result["checks"]["real_controller_causal_ablation"]["achieved"] is False


def test_gate_can_promote_strict_ppt_report_but_not_review_packet_text(tmp_path: Path):
    (tmp_path / "workspace/results").mkdir(parents=True)
    (tmp_path / "research/review").mkdir(parents=True)
    (tmp_path / "research").mkdir(exist_ok=True)
    (tmp_path / "research/paper_experiment_matrix.json").write_text(
        json.dumps({"experiments": []}), encoding="utf-8"
    )
    (tmp_path / "benchmarks").mkdir()
    protocol = tmp_path / "benchmarks/pptbench_model_eval_v2.json"
    protocol.write_text('{"frozen":true}', encoding="utf-8")
    (tmp_path / "workspace/results/model_generated_ppt_evaluation.json").write_text(
        json.dumps({
            "schema": "model-generated-ppt-evaluation-v1", "valid": True,
            "model_generated": True, "protocol_frozen_before_generation": True,
            "protocol_sha256": hashlib.sha256(protocol.read_bytes()).hexdigest(),
            "paired_task_set": True, "n_tasks": 12, "n_systems": 3, "rendered_decks": 36,
            "blind_review": {"complete": True, "n_reviewers": 2, "agreement_metric": 0.7,
                "forms_locked_before_adjudication": True, "raw_score_files_sha256": ["a", "b"]},
            "performance": {"unit":"task", "contrasts": {
                "xiaopu_minus_claude_code":{"n_tasks":12,"paired_bootstrap_ci95":[0,1],"paired_permutation_p":0.1,"holm_adjusted_p":0.2},
                "xiaopu_minus_codex":{"n_tasks":12,"paired_bootstrap_ci95":[0,1],"paired_permutation_p":0.2,"holm_adjusted_p":0.2},
            }},
        }), encoding="utf-8"
    )
    (tmp_path / "research/review/EXTERNAL_REVIEW_PACKET.md").write_text(
        "external=true", encoding="utf-8"
    )
    result = build(tmp_path)
    assert result["checks"]["model_generated_ppt_evaluation"]["achieved"] is True
    assert result["checks"]["external_independent_review"]["achieved"] is False


def test_hash_pinned_independent_review_and_v3_parity_are_separate_gates(tmp_path: Path):
    results = tmp_path / "workspace/results"
    review = tmp_path / "research/review"
    results.mkdir(parents=True)
    review.mkdir(parents=True)
    (tmp_path / "research/paper_experiment_matrix.json").write_text(
        json.dumps({"experiments": []}), encoding="utf-8"
    )
    report = review / "external_review_RETURNED.md"
    report.write_text("Independent review with blocking issues listed.", encoding="utf-8")
    (review / "external_review_attestation.json").write_text(
        json.dumps({
            "schema": "independent-external-review-attestation-v1",
            "independent": True, "reviewer_non_author": True,
            "conflicts_declared": True, "review_date": "2026-08-11",
            "report_path": "research/review/external_review_RETURNED.md",
            "report_sha256": hashlib.sha256(report.read_bytes()).hexdigest(),
        }), encoding="utf-8"
    )
    (results / "matched_protocol_v3_validation.json").write_text(
        json.dumps({"valid": True}), encoding="utf-8"
    )
    (results / "matched_v3_live_smoke_validation.json").write_text(
        json.dumps({"smoke_valid": True}), encoding="utf-8"
    )
    (results / "budget_parity_v3.json").write_text(
        json.dumps({"budget_parity_verified": True, "task_set_parity": True}), encoding="utf-8"
    )
    result = build(tmp_path)
    assert result["checks"]["external_independent_review"]["achieved"] is True
    assert result["checks"]["matched_protocol_v3_readiness"]["achieved"] is True
    assert result["checks"]["matched_claude_codex_protocol"]["achieved"] is True
    assert result["objective_complete"] is False


def test_swe_protocol_readiness_never_promotes_official_results(tmp_path: Path):
    results = tmp_path / "workspace/results"
    (tmp_path / "research/review").mkdir(parents=True)
    (tmp_path / "research").mkdir(exist_ok=True)
    results.mkdir(parents=True)
    (tmp_path / "research/paper_experiment_matrix.json").write_text(
        json.dumps({"experiments": []}), encoding="utf-8"
    )
    (results / "official_swe_verified_v2_validation.json").write_text(json.dumps({
        "valid": True, "n_frozen_instances": 12, "official_dataset_size": 500,
        "official_evaluator_present": True, "execution_ready": True,
        "checkout_materialization_smoke_valid": True, "score_eligible_reports": 0,
    }), encoding="utf-8")
    result = build(tmp_path)
    assert result["checks"]["official_swe_verified_protocol_ready"]["achieved"] is True
    assert result["checks"]["official_swe_bench_verified_full"]["achieved"] is False


def test_real_controller_protocol_readiness_never_promotes_causality(tmp_path: Path):
    results = tmp_path / "workspace/results"
    (tmp_path / "research/review").mkdir(parents=True)
    (tmp_path / "research").mkdir(exist_ok=True)
    results.mkdir(parents=True)
    (tmp_path / "research/paper_experiment_matrix.json").write_text(
        json.dumps({"experiments": []}), encoding="utf-8"
    )
    (results / "real_controller_ablation_protocol_validation.json").write_text(json.dumps({
        "valid": True, "n_tasks": 12, "n_policies": 4, "expected_cells": 48,
    }), encoding="utf-8")
    (results / "real_controller_execution_readiness.json").write_text(json.dumps({
        "valid": True, "scheduled_cells": 48, "real_pdf_png_smoke": True,
    }), encoding="utf-8")
    result = build(tmp_path)
    assert result["checks"]["real_controller_protocol_ready"]["achieved"] is True
    assert result["checks"]["real_controller_causal_ablation"]["achieved"] is False


def test_real_controller_result_requires_recomputed_48_cell_statistics(tmp_path: Path):
    results = tmp_path / "workspace/results"
    benchmarks = tmp_path / "benchmarks"
    (tmp_path / "research/review").mkdir(parents=True)
    (tmp_path / "research").mkdir(exist_ok=True)
    results.mkdir(parents=True)
    benchmarks.mkdir()
    (tmp_path / "research/paper_experiment_matrix.json").write_text(json.dumps({"experiments": []}), encoding="utf-8")
    protocol = benchmarks / "real_controller_ablation_v1.json"
    protocol.write_text("{}", encoding="utf-8")
    base = {
        "schema":"real-controller-causal-ablation-v1", "valid":True,
        "artifact_backed":True, "protocol_frozen_before_run":True,
        "paired_task_set":True, "predefined_outcomes":True, "n_tasks":12,
        "policies":["direct","always_verify","evidence_only","cegar_h"],
    }
    (results / "real_controller_ablation.json").write_text(json.dumps(base), encoding="utf-8")
    assert build(tmp_path)["checks"]["real_controller_causal_ablation"]["achieved"] is False
    base.update({
        "all_48_cells_valid":True, "statistics_precomputed_from_cells":True,
        "protocol_sha256":hashlib.sha256(protocol.read_bytes()).hexdigest(),
        "statistics":{"n_tasks":12, "contrasts":{
            "cegar_h_minus_direct":{}, "cegar_h_minus_always_verify":{}, "cegar_h_minus_evidence_only":{},
        }},
    })
    (results / "real_controller_ablation.json").write_text(json.dumps(base), encoding="utf-8")
    assert build(tmp_path)["checks"]["real_controller_causal_ablation"]["achieved"] is True
