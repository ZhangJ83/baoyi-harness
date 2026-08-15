"""Seeded CEGAR-H ablations with task-level uncertainty intervals.

This is a deterministic simulator study. It is deliberately separate from
benchmark scores: each row is a seeded synthetic task family and every policy
sees the same generated actions for that seed.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.deliberation import ControllerConfig, MetaAction, choose_meta_action
from experiments.simulate_cegarh import task_actions


@dataclass
class SeedMetric:
    policy: str
    seed: int
    homogeneous: bool
    objective: float
    success: float
    cost: float
    residual_risk: float


def noisy_action(action: MetaAction, rng: random.Random, noise: float) -> MetaAction:
    if noise <= 0:
        return action
    return MetaAction(
        name=action.name,
        expected_gain=max(0.0, min(1.0, action.expected_gain + rng.gauss(0, noise))),
        cost=action.cost,
        latency=action.latency,
        residual_risk=max(0.0, min(1.0, action.residual_risk + rng.gauss(0, noise))),
        kind=action.kind,
        requires_fresh_scope=action.requires_fresh_scope,
    )


def select(policy: str, actions: list[MetaAction], config: ControllerConfig, rng: random.Random, noise: float) -> MetaAction:
    if policy == "oracle":
        return choose_meta_action(actions, config).action
    if policy == "direct":
        return actions[0]
    if policy == "always_joint":
        return actions[-1]
    def estimated(candidates: list[MetaAction]) -> MetaAction:
        chosen = choose_meta_action([noisy_action(a, rng, noise) for a in candidates], config).action
        return next(a for a in actions if a.name == chosen.name)
    if policy == "compute_only":
        return estimated(actions[:2])
    if policy == "evidence_only":
        return estimated([actions[0], actions[2]])
    if policy == "cegarh":
        return estimated(actions)
    raise ValueError(policy)


def run_seed(seed: int, tasks: int, homogeneous: bool, config: ControllerConfig, noise: float) -> list[SeedMetric]:
    rng = random.Random(seed)
    policies = ["direct", "compute_only", "evidence_only", "always_joint", "cegarh", "oracle"]
    sums = {p: [0.0, 0.0, 0.0, 0.0] for p in policies}
    for _ in range(tasks):
        difficulty = 0.5 if homogeneous else rng.betavariate(1.4, 1.4)
        evidence_quality = 0.65 if homogeneous else rng.uniform(0.35, 0.95)
        actions = task_actions(difficulty, evidence_quality)
        for policy in policies:
            chosen = select(policy, actions, config, rng, noise if policy not in {"direct", "always_joint", "oracle"} else 0.0)
            vals = sums[policy]
            vals[0] += chosen.expected_gain - config.cost_weight * chosen.cost - config.risk_weight * chosen.residual_risk
            vals[1] += chosen.expected_gain
            vals[2] += chosen.cost
            vals[3] += chosen.residual_risk
    return [SeedMetric(p, seed, homogeneous, *(v / tasks for v in sums[p])) for p, v in sums.items()]


def summarize(rows: list[SeedMetric]) -> list[dict]:
    out = []
    for policy in sorted({r.policy for r in rows}):
        for homogeneous in (False, True):
            vals = [r for r in rows if r.policy == policy and r.homogeneous == homogeneous]
            if not vals:
                continue
            result = {"policy": policy, "homogeneous": homogeneous, "n_seeds": len(vals)}
            for field in ("objective", "success", "cost", "residual_risk"):
                x = [getattr(r, field) for r in vals]
                mean = sum(x) / len(x)
                sd = math.sqrt(sum((v - mean) ** 2 for v in x) / max(1, len(x) - 1))
                half = 1.96 * sd / math.sqrt(len(x))
                result[field] = mean
                result[f"{field}_95_ci"] = [mean - half, mean + half]
            out.append(result)
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--seeds", type=int, default=20)
    p.add_argument("--tasks-per-seed", type=int, default=2000)
    p.add_argument("--noise", type=float, default=0.0)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    config = ControllerConfig(cost_weight=0.05, risk_weight=1.0)
    rows = [
        metric
        for homogeneous in (False, True)
        for seed in range(args.seeds)
        for metric in run_seed(seed, args.tasks_per_seed, homogeneous, config, args.noise)
    ]
    payload = {
        "kind": "synthetic_cegarh_ablation",
        "config": asdict(config),
        "seeds": args.seeds,
        "tasks_per_seed": args.tasks_per_seed,
        "estimator_noise": args.noise,
        "metrics": summarize(rows),
        "claim_boundary": "synthetic simulator evidence only; not Terminal-Bench, SWE-bench, or competitor evidence",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
