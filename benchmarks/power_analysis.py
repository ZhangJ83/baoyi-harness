"""Predeclared paired-task power/sensitivity analysis for the comparison gate.

This is planning evidence, not benchmark evidence.  It answers how many
discordant task pairs are needed before the current bootstrap gate can exclude
zero, and reports the exact two-sided McNemar p-value for the same pairs.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from benchmarks.paired_stats import paired_bootstrap_delta


def mcnemar_two_sided(wins: int, losses: int) -> float:
    n = wins + losses
    if n == 0:
        return 1.0
    k = min(wins, losses)
    return min(1.0, 2.0 * sum(math.comb(n, i) for i in range(k + 1)) / (2**n))


def scenario(n: int, wins: int, losses: int, samples: int = 20_000) -> dict:
    ties = n - wins - losses
    if ties < 0:
        raise ValueError("wins + losses cannot exceed n")
    treatment = [1] * wins + [0] * losses + [1] * ties
    control = [0] * wins + [1] * losses + [1] * ties
    stats = paired_bootstrap_delta(treatment, control, samples=samples)
    return {
        "n_tasks": n,
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "delta": stats["delta"],
        "bootstrap_95_ci": stats["bootstrap_95_ci"],
        "bootstrap_excludes_zero": stats["bootstrap_95_ci"][0] > 0,
        "mcnemar_two_sided_p": mcnemar_two_sided(wins, losses),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    scenarios = []
    for n in (3, 5, 8, 10, 12, 20, 30, 50):
        # Preserve the observed pilot pattern: one third wins, no losses.
        wins = max(1, n // 3)
        scenarios.append(scenario(n, wins, 0))
    exact_p05_min_n = next(
        n for n in range(3, 101)
        if mcnemar_two_sided(max(1, n // 3), 0) < 0.05
    )
    result = {
        "kind": "paired_task_power_analysis",
        "pilot_observation": {"n_tasks": 3, "wins": 1, "losses": 0, "ties": 2},
        "interpretation": "planning_only_not_external_benchmark_evidence",
        "scenarios": scenarios,
        "decision_thresholds": {
            "bootstrap_lower_ci_positive": 12,
            "exact_mcnemar_two_sided_p_below_0_05_under_same_pattern": exact_p05_min_n,
        },
        "recommendation": (
            "Twelve predeclared paired tasks make the bootstrap lower bound "
            "positive under the optimistic no-loss/one-third-win pattern, but "
            "the exact McNemar test is still above 0.05. Under that same "
            "pattern, at least 18 tasks are needed for exact p<0.05. These "
            "are planning thresholds, not guarantees; realistic power and "
            "task-stratum robustness must be estimated before collection."
        ),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
