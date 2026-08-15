"""Empirically verify the stated plug-in decision bounds.

This finite randomized check is not a proof. It guards against an
implementation/theorem mismatch before a formal appendix is written.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--trials", type=int, default=200_000)
    p.add_argument("--epsilon", type=float, default=0.08)
    p.add_argument("--seed", type=int, default=17)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    rng = random.Random(args.seed)
    max_binary = 0.0
    max_multi = 0.0
    binary_violations = 0
    multi_violations = 0
    for _ in range(args.trials):
        true = [rng.uniform(-1, 1) for _ in range(4)]
        est = [x + rng.uniform(-args.epsilon, args.epsilon) for x in true]
        oracle = max(true)
        chosen = true[max(range(4), key=lambda i: est[i])]
        regret = oracle - chosen
        max_multi = max(max_multi, regret)
        multi_violations += regret > 2 * args.epsilon + 1e-12
        b = rng.uniform(-1, 1)
        b_hat = b + rng.uniform(-args.epsilon, args.epsilon)
        binary_regret = abs(b) if (b > 0) != (b_hat > 0) else 0.0
        max_binary = max(max_binary, binary_regret)
        binary_violations += binary_regret > args.epsilon + 1e-12
    payload = {
        "kind": "finite_theory_bound_check",
        "trials": args.trials,
        "epsilon": args.epsilon,
        "seed": args.seed,
        "binary": {"max_regret": max_binary, "bound": args.epsilon, "violations": binary_violations},
        "multi_action": {"max_regret": max_multi, "bound": 2 * args.epsilon, "violations": multi_violations},
        "claim_boundary": "randomized consistency check, not a formal proof or benchmark evidence",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    if binary_violations or multi_violations:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
