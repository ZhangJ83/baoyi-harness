import hashlib
import json

from benchmarks.verify_budget_parity_v3 import verify


def dump(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def make_system(root, name, tasks, protocol, task_manifest, *, omit_ledger=False):
    system = root / name
    rows = []
    for task in tasks:
        trial = f"{task}.1-of-1.{name}"
        rows.append({
            "task_id": task,
            "trial_name": trial,
            "is_resolved": True,
            "total_input_tokens": 5,
            "total_output_tokens": 3,
        })
        if not omit_ledger:
            enforcement = (
                {
                    "output_tokens": "pre-request cumulative remaining-output rewrite with authoritative provider usage",
                    "covered_local_tools": "pre-execution ledger gate",
                    "wall_time": "Terminal-Bench global agent timeout",
                }
                if name == "xiaopu"
                else {
                    "output_tokens": "pre-request gateway reservation and provider max-output rewrite",
                    "covered_local_tools": "blocking PreToolUse hook",
                    "wall_time": "supervisor deadline",
                }
            )
            ledger = {
                "schema": "matched-budget-ledger-v3",
                "system": name,
                "input_tokens": 5,
                "output_tokens": 3,
                "covered_local_tool_calls": 1,
                "wall_seconds": 1.0,
                "caps": {
                    "max_cumulative_output_tokens": 10,
                    "max_covered_local_tool_calls": 2,
                    "max_agent_wall_seconds": 5,
                },
                "enforcement": enforcement,
                "parse_errors": [],
                "gateway_violations": [],
                "within_budget": True,
            }
            if name == "xiaopu":
                ledger["authoritative_output_matches_result"] = True
            else:
                ledger["gateway_output_matches_cli_stream"] = True
            dump(system / task / trial / "agent-logs" / "budget_ledger_v3.json", ledger)
    dump(system / "results.json", {"results": rows})
    dump(system / "run_manifest_v3.json", {
        "system": name,
        "model": "deepseek-v4-flash",
        "protocol_sha256": hashlib.sha256(protocol.read_bytes()).hexdigest(),
        "task_manifest_sha256": hashlib.sha256(task_manifest.read_bytes()).hexdigest(),
        "benchmark_commit": "d28711d",
    })
    return system / "results.json"


def make_contract(tmp_path):
    protocol = tmp_path / "protocol.json"
    tasks = tmp_path / "tasks.json"
    dump(protocol, {
        "shared_model": "deepseek-v4-flash",
        "benchmark": {"commit": "d28711d"},
        "hard_envelope": {
            "max_cumulative_output_tokens": 10,
            "max_covered_local_tool_calls": 2,
            "max_agent_wall_seconds": 5,
        },
    })
    dump(tasks, {"task_ids": ["a", "b"]})
    return protocol, tasks


def test_v3_verifier_accepts_complete_identical_hard_envelope(tmp_path):
    protocol, tasks = make_contract(tmp_path)
    paths = {
        name: make_system(tmp_path, name, ["a", "b"], protocol, tasks)
        for name in ("xiaopu", "claude_code", "codex")
    }
    result = verify(paths, protocol_path=protocol, task_manifest_path=tasks)
    assert result["budget_parity_verified"] is True


def test_v3_verifier_fails_closed_on_any_missing_ledger(tmp_path):
    protocol, tasks = make_contract(tmp_path)
    paths = {
        name: make_system(
            tmp_path,
            name,
            ["a", "b"],
            protocol,
            tasks,
            omit_ledger=(name == "codex"),
        )
        for name in ("xiaopu", "claude_code", "codex")
    }
    result = verify(paths, protocol_path=protocol, task_manifest_path=tasks)
    assert result["budget_parity_verified"] is False
    assert result["systems"]["codex"]["eligible"] is False
