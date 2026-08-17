"""Fail-closed validation of the frozen 12-instance SWE Verified protocol."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

def validate(protocol_path: Path, arrow_path: Path, evaluator_root: Path, checkout_smoke_path: Path) -> dict:
    from datasets import Dataset
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    root = protocol_path.resolve().parents[1]
    ds = Dataset.from_file(str(arrow_path))
    official = {row["instance_id"]: row for row in ds}
    instances = protocol.get("instances", [])
    rows = []
    for item in instances:
        row = official.get(item.get("instance_id"))
        rows.append({
            "instance_id": item.get("instance_id"),
            "present": row is not None,
            "repo_match": bool(row and row["repo"] == item.get("repo")),
            "base_commit_match": bool(row and row["base_commit"] == item.get("base_commit")),
            "problem_statement_present": bool(row and row.get("problem_statement")),
            "test_patch_present": bool(row and row.get("test_patch")),
        })
    ids = [x.get("instance_id") for x in instances]
    execution = protocol.get("execution", {})
    runtime_rows = []
    for name in ("runner", "image_builder", "official_launcher"):
        item = execution.get(name, {})
        path = root / item.get("path", "")
        runtime_rows.append({"name": name, "path": item.get("path"), "present": path.is_file(),
                             "hash_match": path.is_file() and item.get("sha256") == hashlib.sha256(path.read_bytes()).hexdigest()})
    head_result = subprocess.run(["git", "-C", str(evaluator_root), "rev-parse", "HEAD"], capture_output=True, text=True)
    evaluator_head = head_result.stdout.strip() if head_result.returncode == 0 else None
    budget = protocol.get("budget", {})
    checkout_smoke = json.loads(checkout_smoke_path.read_text(encoding="utf-8")) if checkout_smoke_path.is_file() else {}
    checkout_smoke_valid = bool(
        checkout_smoke.get("valid") is True
        and checkout_smoke.get("protocol_sha256") == hashlib.sha256(protocol_path.read_bytes()).hexdigest()
        and checkout_smoke.get("runner_sha256") == execution.get("runner", {}).get("sha256")
        and checkout_smoke.get("observed_head") == checkout_smoke.get("expected_base_commit")
        and checkout_smoke.get("instance_id") in ids
    )
    valid = bool(
        protocol.get("schema") == "official-swe-verified-protocol-v2"
        and protocol.get("source") == "SWE-bench/SWE-bench_Verified"
        and protocol.get("split") == "test"
        and len(instances) >= 10
        and len(ids) == len(set(ids))
        and protocol.get("minimum_score_eligible_reports", 0) >= 10
        and protocol.get("model") == "deepseek-v4-flash"
        and budget == {"max_generated_output_tokens": 4500, "max_covered_local_tool_calls": 60, "max_agent_wall_seconds": 300}
        and "before any new 12-instance v2 model run" in protocol.get("amendment_boundary", "")
        and execution.get("dataset_arrow_sha256") == hashlib.sha256(arrow_path.read_bytes()).hexdigest()
        and execution.get("official_evaluator_commit") == evaluator_head
        and execution.get("resumable_fail_closed") is True
        and execution.get("gold_patch_excluded_from_model_prompt") is True
        and all(row["present"] and row["hash_match"] for row in runtime_rows)
        and checkout_smoke_valid
        and all(r["present"] and r["repo_match"] and r["base_commit_match"]
                and r["problem_statement_present"] and r["test_patch_present"] for r in rows)
        and (evaluator_root / "swebench/harness/run_evaluation.py").is_file()
    )
    return {
        "schema": "official-swe-verified-readiness-v2",
        "valid": valid,
        "protocol_sha256": hashlib.sha256(protocol_path.read_bytes()).hexdigest(),
        "dataset_cache_sha256": hashlib.sha256(arrow_path.read_bytes()).hexdigest(),
        "official_dataset_size": len(ds),
        "n_frozen_instances": len(instances),
        "n_repositories": len({x.get("repo") for x in instances}),
        "official_evaluator_present": (evaluator_root / "swebench/harness/run_evaluation.py").is_file(),
        "official_evaluator_commit": evaluator_head,
        "execution_runtime_hashes": runtime_rows,
        "execution_ready": all(row["present"] and row["hash_match"] for row in runtime_rows) and checkout_smoke_valid,
        "checkout_materialization_smoke_valid": checkout_smoke_valid,
        "score_eligible_reports": 0,
        "model_run_complete": False,
        "claim_boundary": "ready protocol and local official metadata; no new model patches or official scores",
        "rows": rows,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--protocol", type=Path, required=True)
    p.add_argument("--dataset-arrow", type=Path, required=True)
    p.add_argument("--evaluator-root", type=Path, required=True)
    p.add_argument("--checkout-smoke", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    result = validate(a.protocol, a.dataset_arrow, a.evaluator_root, a.checkout_smoke)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
