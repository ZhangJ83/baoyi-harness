"""Plan or build the official Docker instance images for the frozen SWE v2 slice."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from benchmarks.run_official_swe_local import _install_source_paths


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expected_image_key(instance_id: str) -> str:
    return f"sweb.eval.x86_64.{instance_id.lower()}:latest"


def plan(protocol_path: Path, arrow_path: Path, selected_ids: list[str] | None = None) -> tuple[dict, list[dict]]:
    from datasets import Dataset
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    dataset = Dataset.from_file(str(arrow_path))
    official = {row["instance_id"]: row for row in dataset}
    frozen = [row["instance_id"] for row in protocol["instances"]]
    ids = frozen if selected_ids is None else selected_ids
    if len(ids) != len(set(ids)) or any(instance_id not in frozen for instance_id in ids):
        raise ValueError("selected instance ids must be a unique subset of the frozen protocol")
    rows = []
    for instance_id in ids:
        item = official.get(instance_id)
        if item is None:
            raise ValueError(f"instance absent from official dataset: {instance_id}")
        frozen_row = next(row for row in protocol["instances"] if row["instance_id"] == instance_id)
        if item["repo"] != frozen_row["repo"] or item["base_commit"] != frozen_row["base_commit"]:
            raise ValueError(f"official metadata drift: {instance_id}")
        rows.append({"instance_id": instance_id, "repo": item["repo"], "base_commit": item["base_commit"],
                     "image_key": expected_image_key(instance_id), "dataset_row": item})
    manifest = {
        "schema": "official-swe-v2-image-build-plan", "protocol_sha256": sha256(protocol_path),
        "dataset_arrow_sha256": sha256(arrow_path), "selected_instances": ids,
        "expected_images": [row["image_key"] for row in rows], "n_instances": len(rows),
        "claim_boundary": "image preparation only; no model patch or official score",
    }
    return manifest, rows


def build(protocol_path: Path, arrow_path: Path, selected_ids: list[str] | None, max_workers: int) -> dict:
    manifest, rows = plan(protocol_path, arrow_path, selected_ids)
    _install_source_paths()
    import docker
    from swebench.harness.docker_build import build_instance_images
    from swebench.harness.test_spec.test_spec import make_test_spec

    client = docker.from_env()
    client.ping()
    before = {}
    for row in rows:
        try:
            client.images.get(row["image_key"])
            before[row["instance_id"]] = True
        except docker.errors.ImageNotFound:
            before[row["instance_id"]] = False
    dataset_rows = [row["dataset_row"] for row in rows if not before[row["instance_id"]]]
    build_error = None
    if dataset_rows:
        try:
            build_instance_images(client=client, dataset=dataset_rows, force_rebuild=False,
                                  max_workers=max_workers, namespace=None, tag="latest", env_image_tag="latest")
        except Exception as exc:
            build_error = f"{type(exc).__name__}:{exc}"
    states = []
    for row in rows:
        spec = make_test_spec(row["dataset_row"], namespace=None, instance_image_tag="latest", env_image_tag="latest")
        try:
            image = client.images.get(spec.instance_image_key)
            states.append({"instance_id": row["instance_id"], "image_key": spec.instance_image_key,
                           "cached_before": before[row["instance_id"]], "cached_after": True,
                           "image_id": image.id})
        except docker.errors.ImageNotFound:
            states.append({"instance_id": row["instance_id"], "image_key": spec.instance_image_key,
                           "cached_before": before[row["instance_id"]], "cached_after": False, "image_id": None})
    successful = [row["instance_id"] for row in states if row["cached_after"]]
    failed = [row["instance_id"] for row in states if not row["cached_after"]]
    return {**manifest, "schema": "official-swe-v2-image-build-result", "completed_at": datetime.now(timezone.utc).isoformat(),
            "docker_server_reachable": True, "max_workers": max_workers, "successful": successful, "failed": failed,
            "build_error": build_error, "images": states, "all_images_ready": all(row["cached_after"] for row in states)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=ROOT / "benchmarks/official_swe_verified_v2.json")
    parser.add_argument("--dataset-arrow", type=Path, required=True)
    parser.add_argument("--instance-id", action="append")
    parser.add_argument("--max-workers", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--acknowledge-image-build", action="store_true")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if not args.dry_run and not args.acknowledge_image_build:
        raise SystemExit("official image build refused without --acknowledge-image-build")
    if args.max_workers < 1 or args.max_workers > 4:
        raise SystemExit("max-workers must be in [1,4]")
    if args.dry_run:
        result, _ = plan(args.protocol.resolve(), args.dataset_arrow.resolve(), args.instance_id)
        result["dry_run"] = True
    else:
        result = build(args.protocol.resolve(), args.dataset_arrow.resolve(), args.instance_id, args.max_workers)
        result["dry_run"] = False
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if args.dry_run or result.get("all_images_ready") else 2


if __name__ == "__main__":
    raise SystemExit(main())
