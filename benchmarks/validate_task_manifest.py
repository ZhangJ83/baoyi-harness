"""Validate a predeclared Terminal-Bench task manifest without model calls."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def validate(manifest_path: Path, dataset_root: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    ids = manifest.get("task_ids", [])
    errors: list[str] = []
    if len(ids) != len(set(ids)):
        errors.append("duplicate task IDs")
    missing = [task_id for task_id in ids if not (dataset_root / task_id / "task.yaml").is_file()]
    if missing:
        errors.append(f"missing task.yaml: {missing}")
    strata = manifest.get("strata", {})
    stratified = [task_id for values in strata.values() for task_id in values]
    if sorted(stratified) != sorted(ids):
        errors.append("strata do not cover task_ids exactly once")
    protocol = manifest.get("fixed_protocol", {})
    for key, expected in {"n_concurrent": 1, "n_attempts": 1, "temperature": 0.0}.items():
        if protocol.get(key) != expected:
            errors.append(f"protocol.{key} must be {expected}")
    return {
        "manifest": str(manifest_path),
        "dataset_root": str(dataset_root),
        "benchmark_commit": manifest.get("commit"),
        "task_count": len(ids),
        "task_ids": ids,
        "strata_count": len(strata),
        "errors": errors,
        "valid": not errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = validate(args.manifest, args.dataset_root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
