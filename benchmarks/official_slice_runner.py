"""Run and persist one official-repository test slice.

This runner is intentionally model-agnostic: it executes a caller-supplied
test command in an already prepared exact-commit checkout and records raw
output plus the observed HEAD.  It never converts a failed environment into
a benchmark score.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo", type=Path, required=True)
    p.add_argument("--expected-commit", required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("command", nargs=argparse.REMAINDER, help="test command after --")
    args = p.parse_args()
    if not args.command or args.command[0] == "--":
        args.command = args.command[1:]
    if not args.command:
        p.error("a test command is required after --")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=args.repo, text=True, capture_output=True)
    observed = head.stdout.strip() or head.stderr.strip()
    row = {
        "repo": str(args.repo),
        "expected_commit": args.expected_commit,
        "observed_head": observed,
        "checkout_verified": head.returncode == 0 and observed == args.expected_commit,
        "command": args.command,
    }
    start = time.monotonic()
    run = subprocess.run(args.command, cwd=args.repo, text=True, capture_output=True)
    row.update(
        exit_code=run.returncode,
        elapsed_seconds=round(time.monotonic() - start, 3),
        stdout=run.stdout,
        stderr=run.stderr,
        test_executed=True,
        execution_success=run.returncode == 0,
        # A successful arbitrary command is not an official benchmark score.
        # Promotion to score eligibility requires an external scorer contract.
        score_eligible=False,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(row, ensure_ascii=False, indent=2))
    return run.returncode


if __name__ == "__main__":
    raise SystemExit(main())
