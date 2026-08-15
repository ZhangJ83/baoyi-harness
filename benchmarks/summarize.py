"""Aggregate persisted mini-pilot JSON without making model calls."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from agent.benchmark import is_provider_unavailable


def summarize(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("rows", [])
    completed = 0
    overrun = 0
    stopped = 0
    provider_unavailable = 0
    totals = {"tokens": 0, "tool_calls": 0, "elapsed_seconds": 0.0}
    for row in rows:
        stdout = row.get("stdout", "")
        try:
            result = json.loads(stdout.strip().splitlines()[-1])
        except (json.JSONDecodeError, IndexError):
            result = {}
        status = result.get("status")
        # Backward-compatible classification for records produced before the
        # explicit provider_unavailable status was introduced.
        if status == "error" and is_provider_unavailable(result.get("answer", "")):
            status = "provider_unavailable"
        completed += status == "completed"
        overrun += bool(result.get("budget_overrun")) or status == "completed_with_budget_overrun"
        stopped += status == "stopped"
        provider_unavailable += status == "provider_unavailable"
        totals["tokens"] += int(result.get("total_tokens", 0) or 0)
        totals["tool_calls"] += int(result.get("tool_calls", 0) or 0)
        totals["elapsed_seconds"] += float(result.get("elapsed_seconds", row.get("elapsed_seconds", 0)) or 0)
    n = len(rows)
    return {
        "manifest": payload.get("manifest"),
        "suite": payload.get("suite"),
        "attempted": n,
        "completed": completed,
        "completed_rate": completed / n if n else 0.0,
        "budget_overrun": overrun,
        "stopped": stopped,
        "provider_unavailable": provider_unavailable,
        "total_tokens": totals["tokens"],
        "mean_tokens": totals["tokens"] / n if n else 0.0,
        "total_tool_calls": totals["tool_calls"],
        "mean_elapsed_seconds": totals["elapsed_seconds"] / n if n else 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()
    print(json.dumps([summarize(path) for path in args.paths], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
