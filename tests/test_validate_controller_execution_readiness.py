import json
import hashlib
from pathlib import Path

from benchmarks.validate_controller_execution_readiness import validate

ROOT = Path(__file__).resolve().parents[1]


def test_execution_readiness_requires_real_render_smoke(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    smoke = tmp_path / "smoke.json"
    smoke.write_text(json.dumps({
        "evaluator_sha256": hashlib.sha256((ROOT / "benchmarks/evaluate_real_controller_cell.py").read_bytes()).hexdigest(),
        "renderer_sha256": hashlib.sha256((ROOT / "agent/tools/ppt_tools.py").read_bytes()).hexdigest(),
        "infrastructure_valid": True, "evaluation": {
        "pdf_complete": True, "png_complete": True, "fresh_evidence": True,
    }}), encoding="utf-8")
    result = validate(ROOT, smoke)
    assert result["valid"] is True
    assert result["scheduled_cells"] == 48
    assert result["runnable_now"] is False


def test_execution_readiness_fails_without_pdf(tmp_path: Path):
    smoke = tmp_path / "smoke.json"
    smoke.write_text(json.dumps({
        "evaluator_sha256": hashlib.sha256((ROOT / "benchmarks/evaluate_real_controller_cell.py").read_bytes()).hexdigest(),
        "renderer_sha256": hashlib.sha256((ROOT / "agent/tools/ppt_tools.py").read_bytes()).hexdigest(),
        "infrastructure_valid": True, "evaluation": {
        "pdf_complete": False, "png_complete": True, "fresh_evidence": True,
    }}), encoding="utf-8")
    assert validate(ROOT, smoke)["valid"] is False
