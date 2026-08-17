import json
from pathlib import Path

import pytest

from benchmarks.validate_task_manifest import validate


ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_TB_TASKS = ROOT / ".." / "official_refs" / "terminal-bench" / "original-tasks"


@pytest.mark.research_state
@pytest.mark.skipif(not OFFICIAL_TB_TASKS.is_dir(), reason="external official_refs dataset not present")
def test_predeclared_manifest_is_valid():
    result = validate(
        ROOT / "benchmarks/matched_12_task_manifest.json",
        OFFICIAL_TB_TASKS,
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
