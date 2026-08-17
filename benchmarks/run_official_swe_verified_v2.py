"""Resumable patch-generation and official-evaluation runner for frozen SWE v2."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from benchmarks.run_official_swe_local import _install_source_paths


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_frozen(protocol_path: Path, arrow_path: Path, selected: list[str] | None = None) -> tuple[dict, list[dict]]:
    from datasets import Dataset
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    official = {row["instance_id"]: row for row in Dataset.from_file(str(arrow_path))}
    frozen_ids = [row["instance_id"] for row in protocol["instances"]]
    ids = frozen_ids if selected is None else selected
    if len(ids) != len(set(ids)) or any(value not in frozen_ids for value in ids):
        raise ValueError("selected ids must be a unique subset of the frozen protocol")
    rows = []
    for instance_id in ids:
        row = official[instance_id]
        declared = next(value for value in protocol["instances"] if value["instance_id"] == instance_id)
        if row["repo"] != declared["repo"] or row["base_commit"] != declared["base_commit"]:
            raise ValueError(f"official metadata drift: {instance_id}")
        rows.append(row)
    return protocol, rows


def build_prompt(row: dict) -> str:
    return f"""Solve the following frozen SWE-bench Verified issue in the current repository.

Instance: {row['instance_id']}
Repository: {row['repo']}
Base commit: {row['base_commit']}

Problem statement:
{row['problem_statement']}

Rules:
- Inspect the repository and implement a minimal, general fix for the stated issue.
- Do not search for or use a gold patch, test_patch, benchmark answer, or hidden evaluator output.
- Run focused existing tests when feasible; do not weaken, delete, or rewrite tests to force a pass.
- Leave the final code changes in the working tree. Do not commit them.
- Do not modify files outside this isolated repository.
"""


def safe_extract(archive_path: Path, destination: Path) -> None:
    destination = destination.resolve()
    with tarfile.open(archive_path) as archive:
        for member in archive.getmembers():
            target = (destination / member.name).resolve()
            try:
                target.relative_to(destination)
            except ValueError as exc:
                raise RuntimeError("Docker archive path traversal rejected") from exc
        archive.extractall(destination)


def materialize_checkout(client, image_key: str, cell: Path, base_commit: str) -> Path:
    source_parent = cell / "image_checkout"
    workspace = cell / "workspace"
    if workspace.exists():
        return workspace
    source_parent.mkdir(parents=True, exist_ok=True)
    container = client.containers.create(image_key, command=["sleep", "1"], name=f"xiaopu-swe-{uuid.uuid4().hex[:10]}")
    archive_path = None
    try:
        chunks, _ = container.get_archive("/testbed")
        with tempfile.NamedTemporaryFile(prefix="xiaopu-swe-checkout-", suffix=".tar", delete=False) as stream:
            archive_path = Path(stream.name)
            for chunk in chunks:
                stream.write(chunk)
        safe_extract(archive_path, source_parent)
    finally:
        container.remove(force=True)
        if archive_path is not None:
            archive_path.unlink(missing_ok=True)
    source_repo = source_parent / "testbed"
    if not (source_repo / ".git").exists():
        raise RuntimeError("official image did not contain /testbed/.git")
    result = subprocess.run(["git", "-C", str(source_repo), "worktree", "add", "--detach", str(workspace), base_commit],
                            capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"git worktree materialization failed: {(result.stderr or result.stdout)[-1000:]}")
    observed = subprocess.run(["git", "-C", str(workspace), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    if observed != base_commit:
        raise RuntimeError(f"base commit mismatch after materialization: {observed}")
    return workspace


def generation_ledger(workspace: Path, protocol: dict, returncode: int) -> dict:
    log = workspace / ".xiaopu" / "run.jsonl"
    events = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()] if log.is_file() else []
    finish = next((event for event in reversed(events) if event.get("kind") == "finish"), {})
    budget = protocol["budget"]
    output = finish.get("generated_output_tokens")
    tools = finish.get("tool_calls")
    wall = finish.get("elapsed_seconds")
    within = bool(returncode == 0 and finish.get("status") == "completed" and finish.get("provider_usage_authoritative") is True
                  and isinstance(output, int) and output <= budget["max_generated_output_tokens"]
                  and isinstance(tools, int) and tools <= budget["max_covered_local_tool_calls"]
                  and isinstance(wall, (int, float)) and wall <= budget["max_agent_wall_seconds"] + 1
                  and finish.get("budget_overrun") is not True)
    return {"schema": "official-swe-v2-generation-ledger", "returncode": returncode,
            "input_tokens": finish.get("input_tokens"), "output_tokens": output,
            "covered_local_tool_calls": tools, "wall_seconds": wall,
            "provider_usage_authoritative": finish.get("provider_usage_authoritative"),
            "caps": budget, "within_budget": within}


def score_eligible(summary: dict, instance_id: str) -> bool:
    return bool(summary.get("total_instances") == 1 and summary.get("submitted_instances") == 1
                and summary.get("completed_instances") == 1 and summary.get("empty_patch_instances") == 0
                and summary.get("error_instances") == 0 and summary.get("completed_ids") == [instance_id]
                and instance_id in summary.get("submitted_ids", []))


def find_summary(run_root: Path, run_id: str) -> Path | None:
    matches = [path for path in run_root.glob(f"*.{run_id}.json") if path.is_file()]
    return matches[0] if len(matches) == 1 else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=ROOT / "benchmarks/official_swe_verified_v2.json")
    parser.add_argument("--dataset-arrow", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--instance-id", action="append")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--generate-only", action="store_true")
    parser.add_argument("--acknowledge-live-cost", action="store_true")
    args = parser.parse_args()
    protocol_path = args.protocol.resolve()
    arrow_path = args.dataset_arrow.resolve()
    protocol, rows = load_frozen(protocol_path, arrow_path, args.instance_id)
    run_root = args.run_root.resolve()
    if run_root.exists() and any(run_root.iterdir()) and not args.resume:
        raise SystemExit("run root is non-empty; use a new path or explicit --resume")
    run_root.mkdir(parents=True, exist_ok=True)
    manifest = {"schema": "official-swe-v2-run-manifest", "protocol_sha256": sha256(protocol_path),
                "dataset_arrow_sha256": sha256(arrow_path), "runner_sha256": sha256(Path(__file__)),
                "model": protocol["model"], "budget": protocol["budget"],
                "instance_ids": [row["instance_id"] for row in rows], "dry_run": args.dry_run,
                "generate_only": args.generate_only, "claim_boundary": "execution plan is not an official score"}
    write_json(run_root / "run_manifest.json", manifest)
    if args.dry_run:
        print(json.dumps(manifest, ensure_ascii=False))
        return 0
    if not args.acknowledge_live_cost:
        raise SystemExit("live patch generation refused without --acknowledge-live-cost")
    credential = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not credential:
        raise SystemExit("no provider credential in current process; the runner never reads or persists secrets")
    _install_source_paths()
    import docker
    client = docker.from_env()
    client.ping()
    env = {**os.environ, "DEEPSEEK_API_KEY": credential, "OPENAI_API_KEY": credential,
           "PYTHONPATH": str(ROOT), "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    frozen_dataset = run_root / "frozen_dataset.json"
    frozen_dataset.write_text(json.dumps(rows, ensure_ascii=False) + "\n", encoding="utf-8")
    outcomes = []
    for row in rows:
        instance_id = row["instance_id"]
        cell = run_root / "cells" / instance_id
        result_path = cell / "result.json"
        if args.resume and result_path.is_file() and json.loads(result_path.read_text(encoding="utf-8")).get("score_eligible") is True:
            outcomes.append(json.loads(result_path.read_text(encoding="utf-8")))
            continue
        cell.mkdir(parents=True, exist_ok=True)
        image_key = f"sweb.eval.x86_64.{instance_id.lower()}:latest"
        try:
            client.images.get(image_key)
        except docker.errors.ImageNotFound:
            outcomes.append({"instance_id": instance_id, "score_eligible": False, "failure": "official_instance_image_missing"})
            write_json(result_path, outcomes[-1])
            continue
        try:
            workspace = materialize_checkout(client, image_key, cell, row["base_commit"])
            prompt = build_prompt(row)
            (cell / "PROMPT.md").write_text(prompt, encoding="utf-8")
            budget = protocol["budget"]
            command = [sys.executable, "-m", "agent.benchmark", "--workspace", str(workspace),
                       "--model", protocol["model"], "--max-steps", "50",
                       "--max-tool-calls", str(budget["max_covered_local_tool_calls"]),
                       "--max-generated-output-tokens", str(budget["max_generated_output_tokens"]),
                       "--controller-policy", "cegar_h", "--json", prompt]
            started = time.time()
            completed = subprocess.run(command, cwd=ROOT, env=env, timeout=budget["max_agent_wall_seconds"] + 60)
            ledger = generation_ledger(workspace, protocol, completed.returncode)
            ledger["launcher_wall_seconds"] = time.time() - started
            write_json(cell / "usage_ledger.json", ledger)
            diff = subprocess.run(["git", "-C", str(workspace), "diff", "--binary", row["base_commit"], "--"],
                                  capture_output=True, text=True, check=True).stdout
            (cell / "model.patch").write_text(diff, encoding="utf-8")
            prediction = {"instance_id": instance_id, "model_name_or_path": "xiaopu-deepseek-v4-flash-v2", "model_patch": diff}
            prediction_path = cell / "prediction.jsonl"
            prediction_path.write_text(json.dumps(prediction, ensure_ascii=False) + "\n", encoding="utf-8")
            if not ledger["within_budget"] or not diff.strip():
                outcome = {"instance_id": instance_id, "score_eligible": False,
                           "failure": "generation_budget_invalid" if not ledger["within_budget"] else "empty_model_patch",
                           "patch_sha256": sha256(cell / "model.patch")}
            elif args.generate_only:
                outcome = {"instance_id": instance_id, "score_eligible": False, "generation_complete": True,
                           "official_evaluation_pending": True, "patch_sha256": sha256(cell / "model.patch")}
            else:
                run_id = f"swev2_{instance_id.replace('__', '_').replace('-', '_')}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
                command = [sys.executable, str(ROOT / "benchmarks/run_official_swe_local.py"),
                           "--dataset", str(frozen_dataset), "--predictions", str(prediction_path),
                           "--instance-id", instance_id, "--run-id", run_id,
                           "--report-dir", str(cell / "official_report"), "--max-workers", "1"]
                evaluated = subprocess.run(command, cwd=run_root, env=env, timeout=1900)
                summary_path = find_summary(run_root, run_id)
                summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path else {}
                if summary_path:
                    shutil.copy2(summary_path, cell / "official_summary.json")
                outcome = {"instance_id": instance_id, "score_eligible": evaluated.returncode == 0 and score_eligible(summary, instance_id),
                           "resolved": instance_id in summary.get("resolved_ids", []), "official_returncode": evaluated.returncode,
                           "official_summary_sha256": sha256(cell / "official_summary.json") if (cell / "official_summary.json").is_file() else None,
                           "patch_sha256": sha256(cell / "model.patch")}
            write_json(result_path, outcome)
        except Exception as exc:
            outcome = {"instance_id": instance_id, "score_eligible": False, "failure": f"{type(exc).__name__}:{exc}"}
            write_json(result_path, outcome)
        outcomes.append(outcome)
        write_json(run_root / "progress.json", {"attempted": len(outcomes), "score_eligible": sum(row.get("score_eligible") is True for row in outcomes), "outcomes": outcomes})
    summary = {"schema": "official-swe-v2-run-summary", "protocol_sha256": sha256(protocol_path),
               "n_frozen_instances": len(rows), "score_eligible_reports": sum(row.get("score_eligible") is True for row in outcomes),
               "resolved_instances": sum(row.get("resolved") is True for row in outcomes), "model_run_complete": len(outcomes) == len(rows),
               "minimum_score_eligible_reports": protocol["minimum_score_eligible_reports"], "outcomes": outcomes,
               "claim_boundary": "official resolution evidence only for score-eligible rows; minimum n still applies"}
    write_json(run_root / "run_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["score_eligible_reports"] >= protocol["minimum_score_eligible_reports"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
