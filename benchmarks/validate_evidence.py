"""Check that completed audit claims point to existing evidence artifacts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def validate(root: Path) -> dict:
    errors: list[str] = []
    audit_path = root / "workspace/results/completion_audit_current.json"
    if not audit_path.is_file():
        errors.append("missing completion_audit_current.json")
    else:
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        for name, item in audit.get("checks", {}).items():
            status = item.get("status", "")
            evidence = item.get("evidence")
            if status == "achieved" and evidence and not (root / evidence).is_file():
                errors.append(f"{name}: achieved evidence missing: {evidence}")

    matrix_path = root / "research/paper_experiment_matrix.json"
    if not matrix_path.is_file():
        errors.append("missing paper_experiment_matrix.json")
    else:
        matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
        required = {"exp_id", "status", "metrics", "minimal_success_criterion", "next_action"}
        for row in matrix.get("experiments", []):
            missing = sorted(required - set(row))
            if missing:
                errors.append(f"{row.get('exp_id')}: missing matrix fields {missing}")

    return {
        "kind": "evidence_consistency_check",
        "root": str(root),
        "errors": errors,
        "valid": not errors,
        "claim_boundary": "path consistency only; does not validate scientific truth",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = validate(args.root.resolve())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
