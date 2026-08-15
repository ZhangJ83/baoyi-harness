"""Aggregate Xiaopu runs without mixing valid trials and invalid attempts."""
from __future__ import annotations

import argparse, json
from pathlib import Path

def summarize(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    rows = payload.get("results", [])
    valid = [r for r in rows if isinstance(r.get("is_resolved"), bool)]
    invalid = [r for r in rows if not isinstance(r.get("is_resolved"), bool)]
    return {
        "path": str(path), "tasks": [r.get("task_id") for r in rows],
        "n_total": len(rows), "n_valid": len(valid),
        "n_resolved": sum(bool(r.get("is_resolved")) for r in valid),
        "valid_accuracy": (sum(bool(r.get("is_resolved")) for r in valid) / len(valid)) if valid else None,
        "invalid": [{"task_id": r.get("task_id"), "failure_mode": r.get("failure_mode")} for r in invalid],
    }

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("paths", nargs="+", type=Path)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args()
    runs = [summarize(x) for x in args.paths]
    valid = [r for r in runs if r["n_valid"] == r["n_total"] and r["n_total"]]
    result = {
        "kind": "xiaopu_behavioral_run_summary",
        "runs": runs,
        "claim_boundary": "valid_accuracy is descriptive across declared runs; offline runs are not official benchmark scores",
        "all_trials_valid": len(valid) == len(runs),
        "declared_valid_trials": sum(r["n_valid"] for r in runs),
        "declared_resolved_trials": sum(r["n_resolved"] for r in runs),
    }
    result["pooled_valid_accuracy"] = (result["declared_resolved_trials"] / result["declared_valid_trials"] if result["declared_valid_trials"] else None)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
