import json

from benchmarks.claim_gate import gate
from benchmarks.paired_stats import exact_mcnemar_two_sided


def write_result(path, task_ids, resolved):
    path.write_text(
        json.dumps(
            {
                "accuracy": sum(resolved) / len(resolved),
                "results": [
                    {"task_id": task, "is_resolved": ok}
                    for task, ok in zip(task_ids, resolved)
                ],
            }
        ),
        encoding="utf-8",
    )


def verified_budget_parity(task_ids):
    return {
        "budget_parity_verified": True,
        "task_set_parity": True,
        "systems": {
            name: {"eligible": True, "task_ids": task_ids}
            for name in ("xiaopu", "claude_code", "codex")
        },
    }


def test_gate_rejects_missing_competitors(tmp_path):
    x = tmp_path / "x.json"
    write_result(x, ["a"], [True])
    result = gate({"xiaopu": x})
    assert result["claim_allowed"] is False
    assert any("missing" in reason for reason in result["reasons"])


def test_gate_rejects_mismatched_tasks(tmp_path):
    paths = {}
    for name, tasks in {"xiaopu": ["a"], "claude_code": ["a"], "codex": ["b"]}.items():
        paths[name] = tmp_path / f"{name}.json"
        write_result(paths[name], tasks, [True])
    result = gate(paths)
    assert result["claim_allowed"] is False
    assert "task IDs" in result["reasons"][0]


def test_gate_rejects_infrastructure_null_as_incomplete(tmp_path):
    paths = {}
    for name in ("xiaopu", "claude_code", "codex"):
        paths[name] = tmp_path / f"{name}.json"
        paths[name].write_text(
            json.dumps(
                {
                    "results": [
                        {
                            "task_id": "a",
                            "is_resolved": None,
                            "failure_mode": "unknown_agent_error",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
    result = gate(paths)
    assert result["claim_allowed"] is False
    assert any("incomplete" in reason for reason in result["reasons"])
    assert result["systems"]["xiaopu"]["invalid_trials"][0]["task_id"] == "a"


def test_gate_allows_complete_files_with_failures(tmp_path):
    paths = {}
    for name in ("xiaopu", "claude_code", "codex"):
        paths[name] = tmp_path / f"{name}.json"
        write_result(paths[name], ["a", "b"], [True, name == "xiaopu"])
    result = gate(paths)
    assert result["claim_allowed"] is True
    assert result["superiority_supported"] is False
    assert result["paired"]["xiaopu_vs_codex"]["delta"] == 0.5


def test_gate_accepts_complete_paired_results(tmp_path):
    paths = {}
    outcomes = {"xiaopu": [True, True], "claude_code": [True, False], "codex": [False, False]}
    for name, resolved in outcomes.items():
        paths[name] = tmp_path / f"{name}.json"
        write_result(paths[name], ["a", "b"], resolved)
    result = gate(paths)
    assert result["claim_allowed"] is True
    assert result["superiority_supported"] is False
    assert result["paired"]["xiaopu_vs_codex"]["delta"] == 1.0


def test_exact_mcnemar_is_conservative_with_ties():
    assert exact_mcnemar_two_sided(1, 0) == 1.0
    assert exact_mcnemar_two_sided(0, 0) == 1.0
    assert exact_mcnemar_two_sided(6, 0) == 0.03125


def test_superiority_gate_records_sample_and_exact_test_requirements(tmp_path):
    paths = {}
    outcomes = {"xiaopu": [True] * 18, "claude_code": [False] * 18, "codex": [False] * 18}
    for name, resolved in outcomes.items():
        paths[name] = tmp_path / f"{name}.json"
        write_result(paths[name], [str(i) for i in range(18)], resolved)
    task_ids = [str(i) for i in range(18)]
    result = gate(paths, budget_parity=verified_budget_parity(task_ids))
    assert result["superiority_gate"]["min_tasks"] == 18
    assert result["superiority_supported"] is True


def test_superiority_gate_fails_closed_without_budget_parity(tmp_path):
    paths = {}
    outcomes = {"xiaopu": [True] * 18, "claude_code": [False] * 18, "codex": [False] * 18}
    task_ids = [str(i) for i in range(18)]
    for name, resolved in outcomes.items():
        paths[name] = tmp_path / f"{name}.json"
        write_result(paths[name], task_ids, resolved)
    result = gate(paths)
    assert result["claim_allowed"] is True
    assert result["superiority_supported"] is False
    assert result["budget_parity"]["verified"] is False
    assert any("budget parity" in reason for reason in result["superiority_reasons"])
