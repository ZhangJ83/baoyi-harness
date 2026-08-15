"""Fail-closed verifier for the prospective matched-budget v3 protocol."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


SYSTEMS = ("xiaopu", "claude_code", "codex")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def verify_system(
    name: str,
    results_path: Path,
    *,
    expected_tasks: list[str],
    protocol: dict,
    protocol_sha256: str,
    task_manifest_sha256: str,
) -> dict:
    failures: list[dict] = []
    payload = load_json(results_path)
    rows = payload.get("results", [])
    ids = [row.get("task_id") for row in rows]
    if len(ids) != len(set(ids)):
        failures.append({"reason": "duplicate_task_ids"})
    if sorted(ids) != sorted(expected_tasks):
        failures.append({"reason": "task_manifest_mismatch"})
    manifest_path = results_path.parent / "run_manifest_v3.json"
    manifest = load_json(manifest_path) if manifest_path.is_file() else {}
    if not manifest:
        failures.append({"reason": "missing_run_manifest_v3"})
    else:
        expected_manifest = {
            "system": name,
            "model": protocol.get("shared_model"),
            "protocol_sha256": protocol_sha256,
            "task_manifest_sha256": task_manifest_sha256,
            "benchmark_commit": protocol.get("benchmark", {}).get("commit"),
        }
        for key, expected in expected_manifest.items():
            if manifest.get(key) != expected:
                failures.append({"reason": f"run_manifest_{key}_mismatch"})
    caps = protocol["hard_envelope"]
    per_task = []
    for row in rows:
        task_id = row.get("task_id")
        trial = row.get("trial_name")
        if not isinstance(row.get("is_resolved"), bool):
            failures.append({"task_id": task_id, "reason": "invalid_outcome"})
            continue
        ledger_path = results_path.parent / str(task_id) / str(trial) / "agent-logs" / "budget_ledger_v3.json"
        if not ledger_path.is_file():
            failures.append({"task_id": task_id, "reason": "missing_budget_ledger_v3"})
            continue
        ledger = load_json(ledger_path)
        if ledger.get("schema") != "matched-budget-ledger-v3":
            failures.append({"task_id": task_id, "reason": "ledger_schema_mismatch"})
            continue
        checks = {
            "system": ledger.get("system") == name,
            "result_input_tokens": ledger.get("input_tokens") == row.get("total_input_tokens"),
            "result_output_tokens": ledger.get("output_tokens") == row.get("total_output_tokens"),
            "output_cap": ledger.get("caps", {}).get("max_cumulative_output_tokens") == caps["max_cumulative_output_tokens"],
            "tool_cap": ledger.get("caps", {}).get("max_covered_local_tool_calls") == caps["max_covered_local_tool_calls"],
            "wall_cap": ledger.get("caps", {}).get("max_agent_wall_seconds") == caps["max_agent_wall_seconds"],
            "within_budget": ledger.get("within_budget") is True,
            "output_enforced": ledger.get("enforcement", {}).get("output_tokens") == (
                "pre-request cumulative remaining-output rewrite with authoritative provider usage"
                if name == "xiaopu"
                else "pre-request gateway reservation and provider max-output rewrite"
            ),
            "tools_enforced": ledger.get("enforcement", {}).get("covered_local_tools") == (
                "pre-execution ledger gate" if name == "xiaopu" else "blocking PreToolUse hook"
            ),
            "wall_enforced": ledger.get("enforcement", {}).get("wall_time") == (
                "Terminal-Bench global agent timeout" if name == "xiaopu" else "supervisor deadline"
            ),
            "authoritative_output_match": (
                ledger.get("authoritative_output_matches_result") is True
                if name == "xiaopu"
                else ledger.get("gateway_output_matches_cli_stream") is True
            ),
            "no_parse_errors": ledger.get("parse_errors") == [],
            "no_gateway_violations": ledger.get("gateway_violations") == [],
        }
        bad = sorted(key for key, ok in checks.items() if not ok)
        if bad:
            failures.append({"task_id": task_id, "reason": "ledger_checks_failed", "checks": bad})
            continue
        per_task.append(
            {
                "task_id": task_id,
                "input_tokens": ledger["input_tokens"],
                "output_tokens": ledger["output_tokens"],
                "covered_local_tool_calls": ledger["covered_local_tool_calls"],
                "wall_seconds": ledger["wall_seconds"],
            }
        )
    return {
        "path": str(results_path),
        "tasks": len(rows),
        "task_ids": sorted(ids),
        "eligible": not failures and len(per_task) == len(expected_tasks),
        "failures": failures,
        "per_task": per_task,
    }


def verify(
    system_paths: dict[str, Path], *, protocol_path: Path, task_manifest_path: Path
) -> dict:
    protocol = load_json(protocol_path)
    task_manifest = load_json(task_manifest_path)
    expected_tasks = task_manifest["task_ids"]
    systems = {
        name: verify_system(
            name,
            system_paths[name],
            expected_tasks=expected_tasks,
            protocol=protocol,
            protocol_sha256=sha256(protocol_path),
            task_manifest_sha256=sha256(task_manifest_path),
        )
        for name in SYSTEMS
    }
    task_set_parity = all(row["task_ids"] == sorted(expected_tasks) for row in systems.values())
    verified = task_set_parity and all(row["eligible"] for row in systems.values())
    return {
        "kind": "matched_budget_parity_v3",
        "budget_parity_verified": verified,
        "task_set_parity": task_set_parity,
        "protocol_sha256": sha256(protocol_path),
        "task_manifest_sha256": sha256(task_manifest_path),
        "systems": systems,
        "claim_boundary": "fairness eligibility only; does not establish performance superiority",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--xiaopu", type=Path, required=True)
    parser.add_argument("--claude-code", type=Path, required=True)
    parser.add_argument("--codex", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, default=Path("benchmarks/matched_protocol_v3.json"))
    parser.add_argument("--tasks", type=Path, default=Path("research/matched_terminal_slice_v1.json"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = verify(
        {"xiaopu": args.xiaopu, "claude_code": args.claude_code, "codex": args.codex},
        protocol_path=args.protocol,
        task_manifest_path=args.tasks,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result["budget_parity_verified"] else 2)


if __name__ == "__main__":
    main()
