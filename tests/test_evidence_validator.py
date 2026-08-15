import json

from benchmarks.validate_evidence import validate


def test_current_evidence_paths_are_consistent():
    from pathlib import Path

    result = validate(Path(__file__).resolve().parents[1])
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
