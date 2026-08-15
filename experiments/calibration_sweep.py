"""Calibration/estimator-shift sweep for the CEGAR-H controller.

This is intentionally a no-API synthetic study.  It measures how systematic
gain/risk calibration errors affect action choice and objective regret against
the pointwise oracle, using paired task streams and seed-level confidence
intervals.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.deliberation import ControllerConfig, MetaAction, choose_meta_action
from experiments.simulate_cegarh import task_actions


def estimate(action: MetaAction, rng: random.Random, gain_bias: float,
             risk_bias: float, noise: float) -> MetaAction:
    return MetaAction(
        name=action.name,
        expected_gain=max(0.0, min(1.0, action.expected_gain + gain_bias + rng.gauss(0, noise))),
        cost=action.cost,
        latency=action.latency,
        residual_risk=max(0.0, min(1.0, action.residual_risk + risk_bias + rng.gauss(0, noise))),
        kind=action.kind,
        requires_fresh_scope=action.requires_fresh_scope,
    )


def mean_ci(values: list[float]) -> tuple[float, list[float]]:
    mean = sum(values) / len(values)
    sd = math.sqrt(sum((v - mean) ** 2 for v in values) / max(1, len(values) - 1))
    half = 1.96 * sd / math.sqrt(len(values))
    return mean, [mean - half, mean + half]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--seeds", type=int, default=20)
    p.add_argument("--tasks-per-seed", type=int, default=2000)
    p.add_argument("--noise", type=float, default=0.04)
    p.add_argument("--biases", type=float, nargs="+", default=[-0.12, -0.06, 0.0, 0.06, 0.12])
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    config = ControllerConfig(cost_weight=0.05, risk_weight=1.0)
    rows = []
    for bias in args.biases:
        for homogeneous in (False, True):
            seed_values = []
            oracle_values = []
            selected_optimal = []
            for seed in range(args.seeds):
                rng = random.Random(seed)
                observed = 0.0
                oracle = 0.0
                optimal = 0
                for _ in range(args.tasks_per_seed):
                    difficulty = 0.5 if homogeneous else rng.betavariate(1.4, 1.4)
                    evidence_quality = 0.65 if homogeneous else rng.uniform(0.35, 0.95)
                    actions = task_actions(difficulty, evidence_quality)
                    chosen = choose_meta_action(
                        [estimate(a, rng, bias, bias, args.noise) for a in actions], config
                    ).action
                    true = next(a for a in actions if a.name == chosen.name)
                    best = choose_meta_action(actions, config).action
                    observed += true.expected_gain - config.cost_weight * true.cost - config.risk_weight * true.residual_risk
                    oracle += best.expected_gain - config.cost_weight * best.cost - config.risk_weight * best.residual_risk
                    optimal += int(true.name == best.name)
                seed_values.append(observed / args.tasks_per_seed)
                oracle_values.append(oracle / args.tasks_per_seed)
                selected_optimal.append(optimal / args.tasks_per_seed)
            objective, objective_ci = mean_ci(seed_values)
            oracle_mean, _ = mean_ci(oracle_values)
            optimal_rate, optimal_ci = mean_ci(selected_optimal)
            rows.append({
                "bias": bias,
                "homogeneous": homogeneous,
                "objective": objective,
                "objective_95_ci": objective_ci,
                "oracle_objective": oracle_mean,
                "regret": oracle_mean - objective,
                "optimal_action_rate": optimal_rate,
                "optimal_action_rate_95_ci": optimal_ci,
            })
    payload = {
        "kind": "synthetic_cegarh_calibration_sweep",
        "config": {"controller": vars(config), "seeds": args.seeds,
                    "tasks_per_seed": args.tasks_per_seed, "noise": args.noise,
                    "biases": args.biases},
        "metrics": rows,
        "claim_boundary": "synthetic calibration evidence only; not an external benchmark or competitor result",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
