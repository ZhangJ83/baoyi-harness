import json

from benchmarks.summarize_official_matched import load


def test_null_outcome_is_infrastructure_invalid_not_failure(tmp_path):
    path = tmp_path / "results.json"
    path.write_text(
        json.dumps(
            {
                "accuracy": 0.0,
                "results": [
                    {
                        "task_id": "hello-world",
                        "is_resolved": None,
                        "failure_mode": "unknown_agent_error",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    result = load(path)
    assert result["score_eligible"] is False
    assert result["outcomes"] == {}
    assert result["invalid_trials"] == [
        {
            "task_id": "hello-world",
            "failure_mode": "unknown_agent_error",
            "classification": "infrastructure_invalid",
        }
    ]


def test_boolean_failure_remains_a_valid_scored_trial(tmp_path):
    path = tmp_path / "results.json"
    path.write_text(
        json.dumps({"results": [{"task_id": "a", "is_resolved": False}]}),
        encoding="utf-8",
    )
    result = load(path)
    assert result["score_eligible"] is True
    assert result["outcomes"] == {"a": 0}
