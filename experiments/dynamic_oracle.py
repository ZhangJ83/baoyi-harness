"""Finite-horizon toy MDP for separating myopic and dynamic allocation.

The purpose is falsification: a pointwise action-index oracle is not assumed
to be optimal when planning/checking changes future state. Outputs are
synthetic theory evidence, never benchmark scores.
"""
from __future__ import annotations

import argparse
import json
from functools import lru_cache
from pathlib import Path


State = tuple[int, int, int]  # difficulty, planning_level, verification_level
ACTIONS = ("act", "plan", "verify")


def terminal_utility(state: State, action: str) -> float:
    difficulty, plan, verify = state
    p = min(0.98, 0.38 + 0.18 * plan + 0.14 * verify - 0.20 * difficulty)
    risk = max(0.0, 0.32 - 0.12 * verify)
    cost = {"act": 1.0, "plan": 1.8, "verify": 1.5}[action]
    if action != "act":
        return float("-inf")
    return p - 0.05 * cost - risk


def transition(state: State, action: str) -> State:
    difficulty, plan, verify = state
    if action == "plan":
        return (difficulty, min(2, plan + 1), verify)
    if action == "verify":
        return (difficulty, plan, min(2, verify + 1))
    return state


def greedy_action(state: State) -> str:
    # Myopic policy treats non-terminal actions as having zero immediate gain.
    scores = {a: terminal_utility(state, a) for a in ACTIONS}
    return max(scores, key=scores.get)


def solve(horizon: int) -> tuple[float, list[str]]:
    @lru_cache(None)
    def value(state: State, steps: int) -> tuple[float, tuple[str, ...]]:
        if steps <= 0:
            return float("-inf"), ()
        candidates: list[tuple[float, tuple[str, ...]]] = []
        for action in ACTIONS:
            if action == "act":
                candidates.append((terminal_utility(state, action), (action,)))
            elif steps > 1:
                future, path = value(transition(state, action), steps - 1)
                cost = {"plan": 1.8, "verify": 1.5}[action]
                candidates.append((future - 0.05 * cost, (action,) + path))
        return max(candidates, key=lambda x: x[0])

    return value((1, 0, 0), horizon)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--horizon", type=int, default=3)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    state = (1, 0, 0)
    dp_value, dp_path = solve(args.horizon)
    greedy = greedy_action(state)
    result = {
        "kind": "finite_horizon_dynamic_oracle",
        "initial_state": state,
        "horizon": args.horizon,
        "greedy_action": greedy,
        "dynamic_oracle_value": dp_value,
        "dynamic_oracle_path": dp_path,
        "greedy_terminal_value": terminal_utility(state, greedy),
        "claim_boundary": "synthetic counterexample/evidence only; not benchmark evidence",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
