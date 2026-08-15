"""Estimate a bounded token budget from completed official pilot records.

This is a local accounting tool: it never calls a provider and never guesses a
price.  The safety multiplier is explicit so a user can approve an expansion
without turning a pilot into an unbounded spend.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot", type=Path, required=True)
    parser.add_argument("--tasks", type=int, default=12)
    parser.add_argument("--safety-multiplier", type=float, default=4.0)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.pilot.read_text(encoding="utf-8-sig"))
    rows = payload.get("results", [])
    if not rows or args.tasks < 1 or args.safety_multiplier < 1:
        raise SystemExit("pilot must contain rows; tasks >= 1; multiplier >= 1")
    totals = [int(r.get("total_input_tokens", 0)) + int(r.get("total_output_tokens", 0)) for r in rows]
    mean = sum(totals) / len(totals)
    observed_max = max(totals)
    per_task_cap = math.ceil(max(mean, observed_max) * args.safety_multiplier)
    result = {
        "kind": "local_token_budget_estimate",
        "pilot": str(args.pilot),
        "pilot_tasks": len(rows),
        "pilot_total_tokens": sum(totals),
        "pilot_mean_tokens_per_task": mean,
        "pilot_max_tokens_per_task": observed_max,
        "target_tasks": args.tasks,
        "safety_multiplier": args.safety_multiplier,
        "recommended_total_token_cap": per_task_cap * args.tasks,
        "price_estimate": None,
        "interpretation": "planning_only; price must be supplied separately and no API call was made",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
