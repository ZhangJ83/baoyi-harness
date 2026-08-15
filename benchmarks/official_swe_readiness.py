"""Verify the official SWE-bench Verified metadata contract without scoring.

This intentionally stops before Docker evaluation or model inference. It is a
cheap readiness check for the exact dataset, split, instance id, and base
commit that a later official score must use.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from datasets import load_dataset


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance-id", default="astropy__astropy-12907")
    parser.add_argument("--dataset", default="SWE-bench/SWE-bench_Verified")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.dataset.endswith(".json"):
        dataset = json.loads(Path(args.dataset).read_text(encoding="utf-8"))
    elif args.dataset.endswith(".jsonl"):
        dataset = [json.loads(line) for line in Path(args.dataset).read_text(encoding="utf-8").splitlines()]
    else:
        dataset = load_dataset(args.dataset, split="test", streaming=True)
    row = next(item for item in dataset if item["instance_id"] == args.instance_id)
    result = {
        "dataset": args.dataset,
        "split": "test",
        "instance_id": row["instance_id"],
        "repo": row["repo"],
        "base_commit": row["base_commit"],
        "patch_sha256": hashlib.sha256(row["patch"].encode()).hexdigest(),
        "patch_bytes": len(row["patch"].encode()),
        "score_eligible": False,
        "purpose": "metadata readiness only; no model inference or Docker scoring",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
