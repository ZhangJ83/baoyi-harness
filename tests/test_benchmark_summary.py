import json

from benchmarks.summarize import summarize


def test_summarize_counts_completed_stopped_and_overrun(tmp_path):
    path = tmp_path / "result.json"
    path.write_text(json.dumps({
        "manifest": "v1",
        "suite": "pptbench",
        "rows": [
            {"stdout": json.dumps({"status": "completed", "total_tokens": 10, "tool_calls": 2, "elapsed_seconds": 1})},
            {"stdout": json.dumps({"status": "completed", "budget_overrun": True, "total_tokens": 20, "tool_calls": 3, "elapsed_seconds": 2})},
            {"stdout": json.dumps({"status": "stopped", "total_tokens": 30, "tool_calls": 4, "elapsed_seconds": 3})},
        ],
    }), encoding="utf-8")
    result = summarize(path)
    assert result["attempted"] == 3
    assert result["completed"] == 2
    assert result["budget_overrun"] == 1
    assert result["stopped"] == 1
    assert result["total_tokens"] == 60
