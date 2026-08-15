"""Select a preregistered, deterministic Terminal-Bench paired slice.

The selector is deliberately hash-based rather than hand-picked by expected
difficulty.  It creates the minimum 18-task slice needed by the statistical
gate while preserving the pinned task universe and making selection auditable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def select(dataset: Path, n: int, seed: str) -> list[str]:
    ids = sorted(p.name for p in dataset.iterdir() if p.is_dir())
    if n <= 0 or n > len(ids):
        raise ValueError(f"n must be in [1, {len(ids)}]")
    ranked = sorted(
        ids,
        key=lambda task_id: hashlib.sha256(f"{seed}:{task_id}".encode()).hexdigest(),
    )
    return sorted(ranked[:n])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--n", type=int, default=18)
    parser.add_argument("--seed", default="xiaopu-matched-v1")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    task_ids = select(args.dataset, args.n, args.seed)
    payload = {
        "kind": "preregistered_terminal_bench_matched_slice",
        "dataset": str(args.dataset),
        "seed": args.seed,
        "n": len(task_ids),
        "task_ids": task_ids,
        "selection_rule": "lowest SHA-256(seed + ':' + task_id) ranks",
        "claim_scope": "paired pilot slice only; not the full benchmark score",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
