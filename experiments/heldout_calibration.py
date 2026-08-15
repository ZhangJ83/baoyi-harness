"""Held-out calibration check for the synthetic CEGAR-H benefit estimator.

No external model/API is used.  The split is by task stream (70/30), and all
reported metrics are computed on the untouched holdout partition.  This is a
calibration sanity experiment, not evidence of external benchmark efficacy.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments.simulate_cegarh import task_actions


def clamp(x: float) -> float:
    return max(1e-6, min(1 - 1e-6, x))


def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, x))))


def brier(pred: list[float], labels: list[int]) -> float:
    return sum((p - y) ** 2 for p, y in zip(pred, labels)) / len(labels)


def ece(pred: list[float], labels: list[int], bins: int = 10) -> float:
    total = len(labels)
    result = 0.0
    for i in range(bins):
        lo, hi = i / bins, (i + 1) / bins
        idx = [j for j, p in enumerate(pred) if lo <= p < hi or (i == bins - 1 and p == hi)]
        if idx:
            result += len(idx) / total * abs(sum(pred[j] for j in idx) / len(idx) - sum(labels[j] for j in idx) / len(idx))
    return result


def fit_bin_calibrator(pred: list[float], labels: list[int], bins: int = 10) -> list[float]:
    rates = []
    global_rate = sum(labels) / max(1, len(labels))
    for i in range(bins):
        idx = [j for j, p in enumerate(pred) if i / bins <= p < (i + 1) / bins]
        rates.append(sum(labels[j] for j in idx) / len(idx) if idx else global_rate)
    return rates


def apply_bin_calibrator(pred: list[float], rates: list[float]) -> list[float]:
    bins = len(rates)
    return [clamp(rates[min(bins - 1, int(p * bins))]) for p in pred]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--tasks", type=int, default=2000)
    parser.add_argument("--noise", type=float, default=0.35)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    rows = []
    for seed in range(args.seeds):
        rng = random.Random(seed)
        raw, labels = [], []
        for _ in range(args.tasks):
            difficulty = rng.betavariate(1.4, 1.4)
            quality = rng.uniform(0.35, 0.95)
            actions = task_actions(difficulty, quality)
            values = [a.expected_gain - 0.05 * a.cost - a.residual_risk for a in actions]
            best = max(values)
            # A noisy monotone score estimates whether the deliberation action
            # beats the direct action; sigmoid gives a probability-like output.
            direct = values[0]
            deliberation = max(values[1:])
            gap = deliberation - direct
            # The observed outcome is noisy: a positive expected gap raises,
            # but does not deterministically imply, success.
            true_p = sigmoid(gap / 0.5)
            raw.append(clamp(sigmoid(gap / args.noise + rng.gauss(0.0, 0.35))))
            labels.append(int(rng.random() < true_p))
        split = int(0.7 * args.tasks)
        train_p, test_p = raw[:split], raw[split:]
        train_y, test_y = labels[:split], labels[split:]
        rates = fit_bin_calibrator(train_p, train_y)
        calibrated = apply_bin_calibrator(test_p, rates)
        rows.append({
            "seed": seed,
            "holdout_tasks": len(test_y),
            "raw_brier": brier(test_p, test_y),
            "calibrated_brier": brier(calibrated, test_y),
            "raw_ece": ece(test_p, test_y),
            "calibrated_ece": ece(calibrated, test_y),
        })
    def mean(key: str) -> float:
        return sum(row[key] for row in rows) / len(rows)
    result = {
        "kind": "synthetic_heldout_calibration",
        "config": {"seeds": args.seeds, "tasks": args.tasks, "train_fraction": 0.7, "noise": args.noise},
        "mean_metrics": {key: mean(key) for key in ("raw_brier", "calibrated_brier", "raw_ece", "calibrated_ece")},
        "rows": rows,
        "claim_boundary": "held-out synthetic calibration only; not external benchmark evidence",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
