import json
from pathlib import Path

from benchmarks.validate_pptbench_execution_readiness import validate


ROOT = Path(__file__).resolve().parents[1]


def test_current_pptbench_execution_assets_are_ready():
    result = validate(
        ROOT,
        ROOT / "workspace/results/pptbench_model_eval_v2_validation.json",
        ROOT / "workspace/results/pptbench_model_eval_v2_execution_dry_run/run_manifest.json",
        ROOT / "workspace/results/controller_evaluator_smoke/common_evaluation/cell_evaluation.json",
    )
    assert result["valid"] is True
    assert result["scheduled_cells"] == result["unique_cells"] == 36
    assert result["real_powerpoint_pdf_png_smoke"] is True


def test_readiness_fails_closed_on_truncated_schedule(tmp_path):
    protocol_validation = tmp_path / "protocol.json"
    protocol_validation.write_text(json.dumps({"valid": True, "assets_ready": True}), encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"cells": [], "dry_run": True}), encoding="utf-8")
    render = tmp_path / "render.json"
    render.write_text(json.dumps({"infrastructure_valid": True, "evaluation": {"pdf_complete": True, "png_complete": True, "fresh_evidence": True}}), encoding="utf-8")
    result = validate(ROOT, protocol_validation, manifest, render)
    assert result["valid"] is False
    assert "dry_run_36_cell_schedule_invalid" in result["errors"]
