"""Validate and immutably lock one completed blind-review draft."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def lock(draft: dict, dimensions: list[str], expected_ids: set[str], source_sha256: str) -> dict:
    errors = []
    if not isinstance(draft.get("reviewer_id"), str) or not draft.get("reviewer_id").strip():
        errors.append("reviewer_id_required")
    for field in ("independent_from_generation", "reviewer_non_author", "conflicts_declared"):
        if draft.get(field) is not True:
            errors.append(f"{field}_must_be_true")
    if not isinstance(draft.get("review_completed_at"), str) or not draft.get("review_completed_at"):
        errors.append("review_completed_at_required")
    rows = draft.get("scores", [])
    ids = [row.get("anonymous_id") for row in rows]
    if len(ids) != len(set(ids)) or set(ids) != expected_ids:
        errors.append("anonymous_score_set_mismatch")
    for row in rows:
        values = row.get("dimensions", {})
        if set(values) != set(dimensions) or any(not isinstance(value, int) or isinstance(value, bool) or value < 1 or value > 5 for value in values.values()):
            errors.append(f"{row.get('anonymous_id')}:invalid_dimensions")
    if errors:
        raise ValueError(";".join(errors))
    return {
        **draft, "schema":"pptbench-v2-blind-review-form",
        "locked_before_adjudication":True,
        "source_draft_sha256":source_sha256,
        "locked_at":datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--draft", type=Path, required=True)
    p.add_argument("--order", type=Path, required=True)
    p.add_argument("--protocol", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    if a.out.exists():
        raise SystemExit("locked output already exists; refusing overwrite")
    draft_bytes = a.draft.read_bytes()
    draft = json.loads(draft_bytes)
    order = json.loads(a.order.read_text(encoding="utf-8"))["anonymous_ids"]
    protocol = json.loads(a.protocol.read_text(encoding="utf-8"))
    result = lock(draft, protocol["blind_review"]["dimensions"], set(order), hashlib.sha256(draft_bytes).hexdigest())
    a.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"locked":True, "reviewer_id":result["reviewer_id"], "n_scores":len(result["scores"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
