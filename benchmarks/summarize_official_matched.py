"""Summarize official Terminal-Bench matched result files.

Unlike the mini-run summarizer, this consumes Terminal-Bench's native
``results.json`` schema and computes task-level paired deltas without treating
attempts or log lines as independent samples.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from benchmarks.paired_stats import paired_bootstrap_delta


def load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    rows = payload.get("results", [])
    valid = [r for r in rows if isinstance(r.get("is_resolved"), bool)]
    invalid = [r for r in rows if not isinstance(r.get("is_resolved"), bool)]
    return {
        "path": str(path),
        "task_ids": sorted(r.get("task_id") for r in rows),
        "outcomes": {r.get("task_id"): int(r.get("is_resolved")) for r in valid},
        "accuracy": payload.get("accuracy"),
        "n": len(rows),
        "score_eligible": bool(rows) and not invalid,
        "invalid_trials": [
            {
                "task_id": r.get("task_id"),
                "failure_mode": r.get("failure_mode"),
                "classification": (
                    "infrastructure_invalid"
                    if r.get("trial_started_at") is None
                    else "invalid_trial"
                ),
            }
            for r in invalid
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--xiaopu", type=Path, required=True)
    parser.add_argument("--claude-code", type=Path, required=True)
    parser.add_argument("--codex", type=Path, required=True)
    parser.add_argument("--opencode", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    paths = {"xiaopu": args.xiaopu, "claude_code": args.claude_code, "codex": args.codex}
    if args.opencode:
        paths["opencode"] = args.opencode
    systems = {name: load(path) for name, path in paths.items()}
    task_sets = {tuple(v["task_ids"]) for v in systems.values()}
    common = sorted(set.intersection(*(set(v["task_ids"]) for v in systems.values()))) if systems else []
    result = {
        "kind": "official_terminal_matched_summary",
        "systems": systems,
        "common_task_ids": common,
        "task_sets_identical": len(task_sets) == 1,
        "paired": {},
        "claim_boundary": "pilot comparison only; no superiority claim without positive lower CI",
    }
    score_eligible = all(v["score_eligible"] for v in systems.values())
    result["score_eligible"] = score_eligible
    if result["task_sets_identical"] and common and score_eligible:
        x = [systems["xiaopu"]["outcomes"][t] for t in common]
        for name in ("claude_code", "codex", "opencode"):
            if name in systems:
                c = [systems[name]["outcomes"][t] for t in common]
                result["paired"][f"xiaopu_vs_{name}"] = paired_bootstrap_delta(x, c)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["task_sets_identical"] and score_eligible else 2


if __name__ == "__main__":
    raise SystemExit(main())
