"""Paired seed-level CIs for the synthetic CEGAR-H component ablation.

Every policy is evaluated on the same generated task stream within each seed.
This is synthetic evidence only; the unit is a seed, not an external task.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments.run_cegarh_ablation import run_seed
from agent.deliberation import ControllerConfig


def bootstrap_ci(values: list[float], samples: int = 20_000, seed: int = 0) -> list[float]:
    rng = random.Random(seed)
    n = len(values)
    draws = [sum(values[rng.randrange(n)] for _ in range(n)) / n for _ in range(samples)]
    draws.sort()
    return [draws[int(0.025 * (samples - 1))], draws[int(0.975 * (samples - 1))]]


def sign_test_p(wins: int, losses: int) -> float:
    n = wins + losses
    if n == 0:
        return 1.0
    k = min(wins, losses)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2**n)
    return min(1.0, 2 * tail)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--tasks-per-seed", type=int, default=2000)
    parser.add_argument("--noise", type=float, default=0.0)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    config = ControllerConfig(cost_weight=0.05, risk_weight=1.0)
    comparisons: list[dict] = []
    for homogeneous in (False, True):
        by_policy: dict[str, list[float]] = {}
        for seed in range(args.seeds):
            rows = run_seed(seed, args.tasks_per_seed, homogeneous, config, args.noise)
            for row in rows:
                by_policy.setdefault(row.policy, []).append(row.objective)
        cegar = by_policy["cegarh"]
        for baseline, values in sorted(by_policy.items()):
            if baseline == "cegarh":
                continue
            deltas = [a - b for a, b in zip(cegar, values)]
            wins = sum(d > 0 for d in deltas)
            losses = sum(d < 0 for d in deltas)
            mean = sum(deltas) / len(deltas)
            comparisons.append({
                "family": "homogeneous" if homogeneous else "heterogeneous",
                "treatment": "cegarh",
                "baseline": baseline,
                "n_seeds": len(deltas),
                "paired_delta": mean,
                "paired_delta_bootstrap_95_ci": bootstrap_ci(deltas),
                "wins": wins,
                "losses": losses,
                "ties": len(deltas) - wins - losses,
                "exact_two_sided_sign_test_p": sign_test_p(wins, losses),
                "unit": "seed-level paired task-family mean",
            })
    payload = {
        "kind": "paired_synthetic_cegarh_ablation",
        "config": {
            "seeds": args.seeds,
            "tasks_per_seed": args.tasks_per_seed,
            "estimator_noise": args.noise,
            "cost_weight": config.cost_weight,
            "risk_weight": config.risk_weight,
        },
        "comparisons": comparisons,
        "claim_boundary": "synthetic paired ablation evidence only; not benchmark or competitor evidence",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
