"""Verify the observable budget contract for a matched run.

This is intentionally conservative: missing usage or ledger fields are an
ineligible system, never silently treated as zero.  It checks observable
provider tokens, terminal tool events and agent turns only.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def _rows(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8-sig")).get("results", [])


def _ledger_candidates(results_path: Path, row: dict[str, Any]) -> list[Path]:
    task = row.get("task_id")
    trial = row.get("trial_name")
    root = results_path.parent
    return [
        root / str(task) / str(trial) / "budget_ledger.json",
        root / str(trial) / "budget_ledger.json",
        root / "budget_ledger.json",
    ]


def _duration_seconds(row: dict[str, Any]) -> float | None:
    start, end = row.get("agent_started_at"), row.get("agent_ended_at")
    if not isinstance(start, str) or not isinstance(end, str):
        return None
    try:
        value = (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()
    except ValueError:
        return None
    return value if value >= 0 else None


def verify(
    path: Path,
    *,
    max_total_tokens: int,
    max_tool_calls: int,
    max_steps: int,
    max_wall_seconds: float,
) -> dict[str, Any]:
    rows = _rows(path)
    failures: list[dict[str, Any]] = []
    totals = {"input_tokens": 0, "output_tokens": 0, "tool_calls": 0, "steps": 0, "wall_seconds": 0.0}
    task_ids = [row.get("task_id") for row in rows]
    duplicates = sorted({task for task in task_ids if task_ids.count(task) > 1 and task is not None})
    for task in duplicates:
        failures.append({"task_id": task, "reason": "duplicate_task_id"})
    per_task: list[dict[str, Any]] = []
    for row in rows:
        task_id = row.get("task_id")
        task_failures: list[str] = []

        def reject(reason: str) -> None:
            failures.append({"task_id": task_id, "reason": reason})
            task_failures.append(reason)

        if not isinstance(row.get("is_resolved"), bool):
            reject("invalid_trial")
            continue
        required = ("total_input_tokens", "total_output_tokens")
        if any(not isinstance(row.get(key), int) for key in required):
            reject("missing_provider_usage")
            continue
        usage = {
            "input_tokens": int(row["total_input_tokens"]),
            "output_tokens": int(row["total_output_tokens"]),
        }
        if usage["input_tokens"] < 0 or usage["output_tokens"] < 0:
            reject("negative_provider_usage")
        ledger_path = next((p for p in _ledger_candidates(path, row) if p.is_file()), None)
        if ledger_path is None:
            reject("missing_budget_ledger")
            continue
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        for key in ("input_tokens", "output_tokens", "tool_calls", "steps"):
            if not isinstance(ledger.get(key), int):
                reject(f"missing_ledger_{key}")
                break
            usage[key] = int(ledger[key])
        else:
            if ledger["input_tokens"] != row["total_input_tokens"] or ledger["output_tokens"] != row["total_output_tokens"]:
                reject("provider_ledger_token_mismatch")
            expected_caps = {
                "max_total_tokens": max_total_tokens,
                "max_tool_calls": max_tool_calls,
                "max_steps": max_steps,
            }
            for key, expected in expected_caps.items():
                if ledger.get(key) != expected:
                    reject(f"ledger_{key}_mismatch")
            if ledger.get("within_budget") is not True:
                reject("ledger_not_within_budget")
            if usage["input_tokens"] + usage["output_tokens"] > max_total_tokens:
                reject("token_budget_exceeded")
            if usage["tool_calls"] > max_tool_calls:
                reject("tool_budget_exceeded")
            if usage["steps"] > max_steps:
                reject("step_budget_exceeded")
            wall = _duration_seconds(row)
            if wall is None:
                reject("missing_or_invalid_agent_wall_time")
            elif wall > max_wall_seconds:
                reject("wall_time_budget_exceeded")
            usage["wall_seconds"] = wall
            if not task_failures:
                for key in totals:
                    totals[key] += usage[key]
            per_task.append({"task_id": task_id, "eligible": not task_failures, "usage": usage, "ledger": str(ledger_path)})
    return {
        "path": str(path),
        "tasks": len(rows),
        "task_ids": sorted(str(task) for task in task_ids if task is not None),
        "eligible": bool(rows) and not failures,
        "failures": failures,
        "per_task": per_task,
        "totals": totals,
        "caps": {
            "max_total_tokens": max_total_tokens,
            "max_tool_calls": max_tool_calls,
            "max_steps": max_steps,
            "max_wall_seconds": max_wall_seconds,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--system", action="append", nargs=2, metavar=("NAME", "RESULTS"), required=True)
    parser.add_argument("--max-total-tokens", type=int, default=12_000)
    parser.add_argument("--max-tool-calls", type=int, default=60)
    parser.add_argument("--max-steps", type=int, default=3)
    parser.add_argument("--max-wall-seconds", type=float, default=180.0)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    systems = {
        name: verify(
            Path(path),
            max_total_tokens=args.max_total_tokens,
            max_tool_calls=args.max_tool_calls,
            max_steps=args.max_steps,
            max_wall_seconds=args.max_wall_seconds,
        )
        for name, path in args.system
    }
    task_sets = {tuple(value["task_ids"]) for value in systems.values()}
    task_parity = len(task_sets) == 1 and bool(task_sets)
    result = {
        "kind": "matched_budget_parity",
        "budget_parity_verified": bool(systems) and task_parity and all(v["eligible"] for v in systems.values()),
        "task_set_parity": task_parity,
        "systems": systems,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["budget_parity_verified"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
