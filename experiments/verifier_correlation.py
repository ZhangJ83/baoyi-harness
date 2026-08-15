"""Empirical correlation sweep for the verifier-cascade bound."""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


def run(rho: float, trials: int, alpha: float, seed: int) -> dict:
    rng = random.Random(seed)
    all_pass = 0
    for _ in range(trials):
        shared = rng.random() < alpha
        passes = []
        for _ in range(3):
            # With probability rho, verifier errors share the latent event;
            # otherwise draw an independent marginal event.
            passes.append(shared if rng.random() < rho else rng.random() < alpha)
        all_pass += int(all(passes))
    empirical = all_pass / trials
    return {
        "rho": rho,
        "trials": trials,
        "marginal_alpha": alpha,
        "empirical_all_pass_false_accept": empirical,
        "independence_product": alpha**3,
        "robust_upper_bound_min_alpha": alpha,
        "bound_holds": empirical <= alpha,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--trials", type=int, default=200000)
    p.add_argument("--alpha", type=float, default=0.1)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    payload = {
        "kind": "verifier_correlation_sweep",
        "results": [run(r, args.trials, args.alpha, 1000 + i) for i, r in enumerate((0.0, 0.25, 0.5, 0.75, 1.0))],
        "claim_boundary": "synthetic verifier-error model only; no external benchmark claim",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
