"""Validate and summarize matched-evaluation result records."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("results", nargs="+", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8-sig"))
    protocol = manifest["protocol"]
    rows = []
    mismatches = []
    for path in args.results:
        row = json.loads(path.read_text(encoding="utf-8-sig"))
        observed = row.get("protocol", {})
        for field in ("model", "max_total_tokens", "max_output_tokens", "max_steps", "max_tool_calls", "api_retries"):
            if observed.get(field) != protocol[field]:
                mismatches.append({"file": str(path), "field": field, "expected": protocol[field], "observed": observed.get(field)})
        rows.append({"file": str(path), "system": row.get("system"), "suite": row.get("suite"), "task_id": row.get("task_id"), "score": row.get("score"), "status": row.get("status")})
    scores = [r["score"] for r in rows if isinstance(r["score"], (int, float))]
    report = {
        "manifest": manifest["version"],
        "matched": not mismatches,
        "mismatches": mismatches,
        "rows": rows,
        "mean_score": sum(scores) / len(scores) if scores else None,
        "claims": manifest["claims"],
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["matched"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
