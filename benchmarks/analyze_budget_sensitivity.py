"""Compare singleton and aggregate offline Terminal-Bench executions.

This is a descriptive real-trace analysis.  The offline reproduction protocol
and repeated tasks are not an official benchmark score or a randomized causal
controller ablation.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path


def load_rows(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8-sig")).get("results", [])


def seconds(row: dict) -> float | None:
    start, end = row.get("agent_started_at"), row.get("agent_ended_at")
    if not start or not end:
        return None
    return (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--singleton", action="append", type=Path, required=True)
    parser.add_argument("--aggregate", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    single = {row["task_id"]: row for path in args.singleton for row in load_rows(path)}
    aggregate = {row["task_id"]: row for row in load_rows(args.aggregate)}
    tasks = sorted(set(single) & set(aggregate))
    rows = []
    for task in tasks:
        a, b = single[task], aggregate[task]
        rows.append({
            "task_id": task,
            "singleton_resolved": a.get("is_resolved"),
            "aggregate_resolved": b.get("is_resolved"),
            "resolution_delta": int(bool(b.get("is_resolved"))) - int(bool(a.get("is_resolved"))),
            "singleton_input_tokens": a.get("total_input_tokens"),
            "singleton_output_tokens": a.get("total_output_tokens"),
            "aggregate_input_tokens": b.get("total_input_tokens"),
            "aggregate_output_tokens": b.get("total_output_tokens"),
            "singleton_agent_seconds": seconds(a),
            "aggregate_agent_seconds": seconds(b),
            "aggregate_failure_mode": b.get("failure_mode"),
        })
    singleton_rate = sum(bool(single[t].get("is_resolved")) for t in tasks) / len(tasks)
    aggregate_rate = sum(bool(aggregate[t].get("is_resolved")) for t in tasks) / len(tasks)
    result = {
        "schema": "offline-budget-sensitivity-v1",
        "tasks": rows,
        "n_tasks": len(tasks),
        "singleton_resolution_rate": singleton_rate,
        "aggregate_resolution_rate": aggregate_rate,
        "resolution_rate_delta": aggregate_rate - singleton_rate,
        "tasks_regressed": [row["task_id"] for row in rows if row["resolution_delta"] < 0],
        "missing_aggregate_token_ledgers": [
            row["task_id"] for row in rows
            if row["aggregate_input_tokens"] is None or row["aggregate_output_tokens"] is None
        ],
        "interpretation": "Aggregate execution regressed under the shared cap; missing token ledgers on truncated trials prevent a precise per-task budget attribution.",
        "claim_boundary": "descriptive offline real-trace analysis only; not official score and not randomized causal evidence",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
