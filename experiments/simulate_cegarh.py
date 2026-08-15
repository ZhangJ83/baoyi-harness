"""Deterministic falsification-oriented simulator for CEGAR-H.

No API calls are made. Results are printed as JSON so the caller decides where
to persist them.
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import asdict, dataclass

from agent.deliberation import ControllerConfig, MetaAction, choose_meta_action


@dataclass
class Aggregate:
    policy: str
    tasks: int = 0
    expected_success: float = 0.0
    cost: float = 0.0
    residual_risk: float = 0.0
    objective: float = 0.0


def task_actions(difficulty: float, evidence_quality: float) -> list[MetaAction]:
    direct_success = 0.93 - 0.62 * difficulty
    deliberate_success = min(0.98, direct_success + 0.06 + 0.35 * difficulty)
    verify_success = min(0.985, direct_success + 0.03 + 0.24 * difficulty * evidence_quality)
    joint_success = min(0.995, deliberate_success + 0.12 * difficulty * evidence_quality)
    base_risk = 0.02 + 0.28 * difficulty
    return [
        MetaAction("direct", direct_success, 1.0, residual_risk=base_risk, kind="direct"),
        MetaAction("deliberate", deliberate_success, 3.3, residual_risk=0.72 * base_risk, kind="compute"),
        MetaAction("verify", verify_success, 2.4, residual_risk=(1.0 - 0.65 * evidence_quality) * base_risk, kind="evidence"),
        MetaAction("joint", joint_success, 5.0, residual_risk=(1.0 - 0.82 * evidence_quality) * base_risk, kind="joint"),
    ]


def select(policy: str, actions: list[MetaAction], config: ControllerConfig) -> MetaAction:
    if policy == "direct":
        return actions[0]
    if policy == "always_joint":
        return actions[-1]
    if policy == "compute_only":
        return choose_meta_action(actions[:2], config).action
    if policy == "evidence_only":
        return choose_meta_action([actions[0], actions[2]], config).action
    if policy == "cegarh":
        return choose_meta_action(actions, config).action
    raise ValueError(policy)


def run(seed: int, tasks: int, homogeneous: bool, config: ControllerConfig) -> list[Aggregate]:
    rng = random.Random(seed)
    policies = ["direct", "always_joint", "compute_only", "evidence_only", "cegarh"]
    output = {name: Aggregate(name) for name in policies}
    for _ in range(tasks):
        difficulty = 0.5 if homogeneous else rng.betavariate(1.4, 1.4)
        evidence_quality = 0.65 if homogeneous else rng.uniform(0.35, 0.95)
        actions = task_actions(difficulty, evidence_quality)
        for policy in policies:
            action = select(policy, actions, config)
            row = output[policy]
            row.tasks += 1
            row.expected_success += action.expected_gain
            row.cost += action.cost
            row.residual_risk += action.residual_risk
            row.objective += (
                action.expected_gain
                - config.cost_weight * action.cost
                - config.risk_weight * action.residual_risk
            )
    for row in output.values():
        for field in ("expected_success", "cost", "residual_risk", "objective"):
            setattr(row, field, getattr(row, field) / tasks)
    return list(output.values())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--tasks", type=int, default=5000)
    parser.add_argument("--homogeneous", action="store_true")
    parser.add_argument("--cost-weight", type=float, default=0.05)
    parser.add_argument("--risk-weight", type=float, default=1.0)
    args = parser.parse_args()
    config = ControllerConfig(cost_weight=args.cost_weight, risk_weight=args.risk_weight)
    payload = {
        "seed": args.seed,
        "tasks": args.tasks,
        "homogeneous": args.homogeneous,
        "config": asdict(config),
        "results": [asdict(row) for row in run(args.seed, args.tasks, args.homogeneous, config)],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
