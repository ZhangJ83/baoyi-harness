import json

from benchmarks.validate_task_manifest import validate


def test_predeclared_manifest_is_valid():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    result = validate(
        root / "benchmarks/matched_12_task_manifest.json",
        root / ".." / "official_refs" / "terminal-bench" / "original-tasks",
    )
    assert result["valid"] is True
    assert result["task_count"] == 12


def test_manifest_rejects_missing_task(tmp_path):
    manifest = {
        "task_ids": ["missing"],
        "strata": {"one": ["missing"]},
        "fixed_protocol": {"n_concurrent": 1, "n_attempts": 1, "temperature": 0.0},
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    result = validate(path, tmp_path)
    assert result["valid"] is False
    assert any("missing" in error for error in result["errors"])
