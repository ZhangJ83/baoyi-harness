import json
from pathlib import Path

from benchmarks.completion_audit import official_swe, official_tb, pptbench


def test_pptbench_audit_marks_structural_fixture_as_non_final(tmp_path: Path):
    report = tmp_path / "workspace/results/pptbench_structural_smoke_latest.json"
    report.parent.mkdir(parents=True)
    report.write_text(json.dumps({
        "tasks": [{"deterministic": True}],
        "mean_score": 1.0,
    }), encoding="utf-8")
    result = pptbench(tmp_path)
    assert result["status"] == "structural_smoke_only"
    assert result["deterministic"] is True


def test_swe_audit_aggregates_score_eligible_reports(tmp_path: Path):
    for idx in range(2):
        (tmp_path / f"xiaopu-deepseek-v4-flash.run{idx}.json").write_text(
            json.dumps({"resolved_instances": 1, "total_instances": 1}),
            encoding="utf-8",
        )
    result = official_swe(tmp_path)
    assert result["status"] == "agent_pilot_only"
    assert result["resolved"] == 2
    assert result["total"] == 2


def test_terminal_audit_requires_complete_dataset_coverage(tmp_path: Path):
    dataset = tmp_path.parent / "official_refs/terminal-bench/original-tasks"
    dataset.mkdir(parents=True)
    for name in ("a", "b"):
        (dataset / name).mkdir()
    result_dir = tmp_path / "workspace/results/official_tb_xiaopu/run"
    result_dir.mkdir(parents=True)
    (result_dir / "results.json").write_text(json.dumps({
        "results": [{"task_id": "a", "is_resolved": True}],
        "accuracy": 1.0,
    }), encoding="utf-8")
    result = official_tb(tmp_path)
    assert result["status"] == "pilot_only"
    assert result["dataset_task_count"] == 2
    assert result["coverage_fraction"] == 0.5
