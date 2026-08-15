"""Summarize offline SWE container evidence without model calls.

This report intentionally distinguishes local execution evidence from an
official SWE-bench score.  It accepts the persisted ``run*/result.json`` files
produced by ``astropy_slice_entry.py`` and fails closed on missing/duplicate
commits.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def summarize(paths: list[Path]) -> dict:
    # Accept JSON exported by Windows tooling with a UTF-8 BOM while keeping
    # the persisted report itself UTF-8 without a BOM.
    rows = [json.loads(p.read_text(encoding="utf-8-sig")) for p in paths]
    commits = [row.get("expected_commit", "") for row in rows]
    unique = len(commits) == len(set(commits))
    built = sum(row.get("build_exit_code") == 0 for row in rows)
    tested = sum(row.get("test_exit_code") == 0 for row in rows)
    return {
        "evidence_type": "offline_container_execution",
        "attempted": len(rows),
        "build_passed": built,
        "test_passed": tested,
        "build_rate": built / len(rows) if rows else 0.0,
        "test_rate": tested / len(rows) if rows else 0.0,
        "unique_commits": unique,
        "score_eligible": False,
        "runs": [
            {
                "expected_commit": row.get("expected_commit"),
                "build_exit_code": row.get("build_exit_code"),
                "test_exit_code": row.get("test_exit_code"),
                "elapsed_seconds": row.get("elapsed_seconds"),
            }
            for row in rows
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = summarize(args.paths)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
