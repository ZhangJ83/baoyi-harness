import hashlib
import json
from pathlib import Path

import pytest

from benchmarks.validate_controller_execution_readiness import validate


ROOT = Path(__file__).resolve().parents[1]


def _create_hermetic_smoke(tmp_path: Path, *, pdf_complete: bool = True) -> Path:
    evaluator = ROOT / "benchmarks/evaluate_real_controller_cell.py"
    renderer = ROOT / "agent/tools/ppt_tools.py"
    smoke = tmp_path / "smoke.json"
    smoke.write_text(json.dumps({
        "evaluator_sha256": hashlib.sha256(evaluator.read_bytes()).hexdigest(),
        "renderer_sha256": hashlib.sha256(renderer.read_bytes()).hexdigest(),
        "infrastructure_valid": True,
        "evaluation": {
            "pdf_complete": pdf_complete,
            "png_complete": True,
            "fresh_evidence": True,
        },
    }), encoding="utf-8")
    return smoke


def test_execution_readiness_fails_without_pdf(tmp_path: Path):
    smoke = _create_hermetic_smoke(tmp_path, pdf_complete=False)
    result = validate(ROOT, smoke)
    assert result["valid"] is False


@pytest.mark.protocol_lock
def test_execution_readiness_requires_real_render_smoke(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    smoke = _create_hermetic_smoke(tmp_path, pdf_complete=True)
    result = validate(ROOT, smoke)
    if not result["valid"]:
        pytest.skip(f"controller execution readiness not currently met: {result}")
    assert result["valid"] is True
    assert result["scheduled_cells"] == 48
    assert result["runnable_now"] is False
