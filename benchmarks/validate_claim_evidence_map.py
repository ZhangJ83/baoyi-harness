"""Validate that paper claims have existing evidence and explicit caveats."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def validate(root: Path, claim_map: Path) -> dict:
    data = json.loads(claim_map.read_text(encoding="utf-8"))
    errors: list[str] = []
    rows = []
    for claim in data.get("claims", []):
        cid = claim.get("id", "<missing>")
        evidence = claim.get("evidence", [])
        caveat = claim.get("caveat")
        missing = [path for path in evidence if not (root / path).exists()]
        if not evidence:
            errors.append(f"{cid}: no evidence paths")
        if missing:
            errors.append(f"{cid}: missing evidence: {', '.join(missing)}")
        if not caveat:
            errors.append(f"{cid}: missing caveat")
        rows.append({
            "id": cid,
            "status": claim.get("status"),
            "evidence_count": len(evidence),
            "missing_evidence": missing,
            "has_caveat": bool(caveat),
        })
    return {
        "schema": "claim-evidence-map-validation-v1",
        "valid": not errors,
        "claim_count": len(rows),
        "errors": errors,
        "claims": rows,
        "boundary": "path and caveat consistency only; does not validate scientific truth",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--map", dest="claim_map", type=Path, default=None)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    claim_map = args.claim_map or root / "research" / "CLAIM_EVIDENCE_MAP.json"
    result = validate(root, claim_map)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
