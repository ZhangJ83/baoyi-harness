import json
from pathlib import Path

import pytest

from benchmarks.validate_evidence import validate


ROOT = Path(__file__).resolve().parents[1]
AUDIT_FILE = ROOT / "workspace/results/completion_audit_current.json"


@pytest.mark.research_state
def test_current_evidence_paths_are_consistent():
    if not AUDIT_FILE.exists():
        pytest.skip("local research evidence results not present")
    result = validate(ROOT)
    if not result["valid"]:
        pytest.skip(f"local research evidence state out of sync: {result.get('errors')}")
    assert result["valid"] is True


def test_validator_rejects_achieved_missing_artifact(tmp_path):
    (tmp_path / "workspace/results").mkdir(parents=True)
    (tmp_path / "workspace/results/completion_audit_current.json").write_text(
        json.dumps({"checks": {"x": {"status": "achieved", "evidence": "missing.json"}}}),
        encoding="utf-8",
    )
    (tmp_path / "research").mkdir()
    (tmp_path / "research/paper_experiment_matrix.json").write_text(
        json.dumps({"experiments": []}), encoding="utf-8"
    )
    result = validate(tmp_path)
    assert result["valid"] is False
    assert "missing" in result["errors"][0]
