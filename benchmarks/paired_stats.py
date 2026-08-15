"""Small, dependency-free statistics for paired benchmark comparisons.

The unit of analysis is a task, not a model call.  This prevents repeated
attempts on one task from being mistaken for independent benchmark evidence.
"""
from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path


def wilson(successes: int, total: int, z: float = 1.96) -> list[float]:
    if total <= 0:
        return [0.0, 0.0]
    p = successes / total
    den = 1 + z * z / total
    center = (p + z * z / (2 * total)) / den
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / den
    return [max(0.0, center - half), min(1.0, center + half)]


def exact_mcnemar_two_sided(wins: int, losses: int) -> float:
    """Two-sided exact McNemar/sign-test p-value for discordant pairs."""
    discordant = wins + losses
    if discordant == 0:
        return 1.0
    lower_tail = sum(math.comb(discordant, i) for i in range(min(wins, losses) + 1))
    return min(1.0, 2.0 * lower_tail / (2**discordant))


def paired_bootstrap_delta(
    treatment: list[int], control: list[int], *, samples: int = 20_000, seed: int = 0
) -> dict:
    if len(treatment) != len(control) or not treatment:
        raise ValueError("paired outcome arrays must have equal non-zero length")
    rng = random.Random(seed)
    n = len(treatment)
    observed = sum(treatment) / n - sum(control) / n
    wins = sum(1 for t, c in zip(treatment, control) if t > c)
    losses = sum(1 for t, c in zip(treatment, control) if t < c)
    ties = n - wins - losses
    deltas = []
    for _ in range(samples):
        idx = [rng.randrange(n) for _ in range(n)]
        deltas.append(sum(treatment[i] - control[i] for i in idx) / n)
    deltas.sort()
    lo = deltas[int(0.025 * (samples - 1))]
    hi = deltas[int(0.975 * (samples - 1))]
    return {
        "n_tasks": n,
        "treatment_rate": sum(treatment) / n,
        "control_rate": sum(control) / n,
        "delta": observed,
        "discordant": {"wins": wins, "losses": losses, "ties": ties},
        "exact_mcnemar_two_sided_p": exact_mcnemar_two_sided(wins, losses),
        "discordant_win_rate_wilson_95_ci": wilson(wins, wins + losses),
        "bootstrap_95_ci": [lo, hi],
        "seed": seed,
        "samples": samples,
        "unit": "task",
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--treatment", type=Path, required=True, help="JSON list of 0/1 outcomes")
    p.add_argument("--control", type=Path, required=True, help="JSON list of 0/1 outcomes")
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    treatment = json.loads(args.treatment.read_text(encoding="utf-8"))
    control = json.loads(args.control.read_text(encoding="utf-8"))
    result = paired_bootstrap_delta(treatment, control)
    result["treatment_wilson_95_ci"] = wilson(sum(treatment), len(treatment))
    result["control_wilson_95_ci"] = wilson(sum(control), len(control))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
