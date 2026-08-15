"""Exhaustive finite-grid check of the stated plug-in decision bounds.

This is stronger than a randomized smoke test on the chosen finite grid, but
it is still not a proof over continuous values or an external benchmark.
"""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--epsilon", type=float, default=0.25)
    parser.add_argument("--actions", type=int, default=3)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    e = args.epsilon
    values = [round(-1 + i * e, 10) for i in range(round(2 / e) + 1)]
    errors = [-e, 0.0, e]
    binary_cases = binary_violations = 0
    binary_max = 0.0
    for b, err in itertools.product(values, errors):
        bhat = b + err
        regret = abs(b) if (b > 0) != (bhat > 0) else 0.0
        binary_cases += 1
        binary_max = max(binary_max, regret)
        binary_violations += int(regret > e + 1e-12)

    multi_cases = multi_violations = 0
    multi_max = 0.0
    for true in itertools.product(values, repeat=args.actions):
        for errs in itertools.product(errors, repeat=args.actions):
            estimated = [x + d for x, d in zip(true, errs)]
            chosen = max(range(args.actions), key=lambda i: estimated[i])
            regret = max(true) - true[chosen]
            multi_cases += 1
            multi_max = max(multi_max, regret)
            multi_violations += int(regret > 2 * e + 1e-12)
    result = {
        "kind": "finite_grid_exhaustive_theory_check",
        "epsilon": e,
        "grid_values": values,
        "error_values": errors,
        "binary": {"cases": binary_cases, "max_regret": binary_max, "bound": e, "violations": binary_violations},
        "multi_action": {"actions": args.actions, "cases": multi_cases, "max_regret": multi_max, "bound": 2 * e, "violations": multi_violations},
        "claim_boundary": "exhaustive only on the declared finite grid; not a continuous proof or benchmark evidence",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    if binary_violations or multi_violations:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
