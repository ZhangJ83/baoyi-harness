"""Run a small deterministic multi-seed CEGAR-H mechanism check."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Support both ``python -m experiments.summarize_cegarh`` and direct execution.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.deliberation import ControllerConfig
from experiments.simulate_cegarh import run


def summarize(seeds: range, heterogeneous_tasks: int, homogeneous_tasks: int) -> dict:
    config = ControllerConfig(cost_weight=0.05, risk_weight=1.0)
    margins: list[float] = []
    homogeneous_equal = 0
    for seed in seeds:
        rows = run(seed, heterogeneous_tasks, False, config)
        scores = {row.policy: row.objective for row in rows}
        margins.append(scores["cegarh"] - max(value for key, value in scores.items() if key != "cegarh"))
        rows = run(seed, homogeneous_tasks, True, config)
        scores = {row.policy: row.objective for row in rows}
        best_fixed = max(scores[key] for key in ("direct", "always_joint", "compute_only", "evidence_only"))
        homogeneous_equal += abs(scores["cegarh"] - best_fixed) <= 1e-12
    return {
        "seeds": list(seeds),
        "heterogeneous_wins": sum(margin > 1e-12 for margin in margins),
        "heterogeneous_min_margin": min(margins),
        "heterogeneous_mean_margin": sum(margins) / len(margins),
        "homogeneous_equal_best": homogeneous_equal,
        "config": {"cost_weight": config.cost_weight, "risk_weight": config.risk_weight},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-seed", type=int, default=1)
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--heterogeneous-tasks", type=int, default=2000)
    parser.add_argument("--homogeneous-tasks", type=int, default=1000)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = summarize(range(args.start_seed, args.start_seed + args.count), args.heterogeneous_tasks, args.homogeneous_tasks)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
