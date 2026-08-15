"""Evidence gate for benchmark superiority claims.

It refuses to infer a comparison from missing, partial, or mismatched result
files. A successful gate still only reports a paired delta and interval; the
user must decide how to phrase the scientific claim.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from benchmarks.paired_stats import paired_bootstrap_delta


def load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    results = payload.get("results", [])
    valid = [r for r in results if isinstance(r.get("is_resolved"), bool)]
    return {
        "path": str(path),
        "tasks": {r.get("task_id"): r.get("is_resolved") for r in valid},
        "complete": bool(results) and len(valid) == len(results),
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
            for r in results
            if not isinstance(r.get("is_resolved"), bool)
        ],
        "accuracy": payload.get("accuracy"),
    }


def gate(
    system_paths: dict[str, Path],
    *,
    min_tasks: int = 18,
    alpha: float = 0.05,
    budget_parity: dict | None = None,
) -> dict:
    rows = {name: load(path) for name, path in system_paths.items() if path.exists()}
    reasons = []
    required = {"xiaopu", "claude_code", "codex"}
    missing = sorted(required - rows.keys())
    if missing:
        reasons.append(f"missing finalized result files: {', '.join(missing)}")
    if rows:
        task_sets = {tuple(sorted(v["tasks"])) for v in rows.values()}
        if len(task_sets) != 1:
            reasons.append("task IDs are not identical across systems")
        if any(not v["complete"] for v in rows.values()):
            reasons.append("at least one result file is incomplete")
    result = {
        "claim_allowed": False,
        "superiority_supported": False,
        "reasons": reasons,
        "superiority_reasons": [],
        "systems": rows,
        "superiority_gate": {
            "min_tasks": min_tasks,
            "alpha": alpha,
            "requirements": [
                "strict matched token/tool/step/wall-time budget parity verified",
                "paired bootstrap lower CI > 0",
                "exact two-sided McNemar p < alpha",
                "n_tasks >= min_tasks",
            ],
        },
        "budget_parity": {
            "verified": False,
            "task_set_parity": bool(
                budget_parity and budget_parity.get("task_set_parity") is True
            ),
        },
    }
    if not reasons:
        tasks = sorted(next(iter(rows.values()))["tasks"])
        x = [int(rows["xiaopu"]["tasks"][t]) for t in tasks]
        c = [int(rows["claude_code"]["tasks"][t]) for t in tasks]
        d = [int(rows["codex"]["tasks"][t]) for t in tasks]
        result["paired"] = {
            "xiaopu_vs_claude_code": paired_bootstrap_delta(x, c),
            "xiaopu_vs_codex": paired_bootstrap_delta(x, d),
        }
        result["claim_allowed"] = True
        parity_systems = (budget_parity or {}).get("systems", {})
        parity_task_sets_match = all(
            sorted(parity_systems.get(name, {}).get("task_ids", [])) == tasks
            for name in required
        )
        parity_systems_eligible = all(
            parity_systems.get(name, {}).get("eligible") is True
            for name in required
        )
        parity_verified = bool(
            budget_parity
            and budget_parity.get("budget_parity_verified") is True
            and budget_parity.get("task_set_parity") is True
            and parity_task_sets_match
            and parity_systems_eligible
        )
        result["budget_parity"].update(
            {
                "verified": parity_verified,
                "task_ids_match_results": parity_task_sets_match,
                "all_systems_eligible": parity_systems_eligible,
            }
        )
        if not parity_verified:
            result["superiority_reasons"].append(
                "strict matched token/tool/step/wall-time budget parity is not verified for these result task IDs"
            )
        for label, stats in result["paired"].items():
            if stats["bootstrap_95_ci"][0] <= 0:
                result["superiority_reasons"].append(
                    f"{label} 95% paired interval does not exclude zero"
                )
            if stats["exact_mcnemar_two_sided_p"] >= alpha:
                result["superiority_reasons"].append(
                    f"{label} exact McNemar p={stats['exact_mcnemar_two_sided_p']:.6g} is not below alpha={alpha}"
                )
            if stats["n_tasks"] < min_tasks:
                result["superiority_reasons"].append(
                    f"{label} has n_tasks={stats['n_tasks']} below the preregistered minimum {min_tasks}"
                )
        result["superiority_supported"] = not result["superiority_reasons"]
    return result


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--xiaopu", type=Path, required=True)
    p.add_argument("--claude-code", type=Path, required=True)
    p.add_argument("--codex", type=Path, required=True)
    p.add_argument("--budget-parity", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--min-tasks", type=int, default=18)
    p.add_argument("--alpha", type=float, default=0.05)
    args = p.parse_args()
    budget_parity = json.loads(args.budget_parity.read_text(encoding="utf-8-sig"))
    result = gate(
        {"xiaopu": args.xiaopu, "claude_code": args.claude_code, "codex": args.codex},
        min_tasks=args.min_tasks,
        alpha=args.alpha,
        budget_parity=budget_parity,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
