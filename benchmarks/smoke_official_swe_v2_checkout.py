"""Non-model smoke for image-to-base-commit checkout materialization."""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from benchmarks.run_official_swe_local import _install_source_paths
from benchmarks.run_official_swe_verified_v2 import load_frozen, materialize_checkout, sha256


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=ROOT / "benchmarks/official_swe_verified_v2.json")
    parser.add_argument("--dataset-arrow", type=Path, required=True)
    parser.add_argument("--instance-id", required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    protocol, rows = load_frozen(args.protocol.resolve(), args.dataset_arrow.resolve(), [args.instance_id])
    row = rows[0]
    _install_source_paths()
    import docker
    client = docker.from_env()
    client.ping()
    image_key = f"sweb.eval.x86_64.{args.instance_id.lower()}:latest"
    image = client.images.get(image_key)
    checkout = materialize_checkout(client, image_key, args.workspace.resolve(), row["base_commit"])
    head = subprocess.run(["git", "-C", str(checkout), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()
    result = {"schema": "official-swe-v2-checkout-smoke", "valid": head == row["base_commit"],
              "instance_id": args.instance_id, "protocol_sha256": sha256(args.protocol.resolve()),
              "runner_sha256": sha256(ROOT / protocol["execution"]["runner"]["path"]),
              "image_key": image_key, "image_id": image.id, "observed_head": head,
              "expected_base_commit": row["base_commit"], "workspace": str(checkout),
              "completed_at": datetime.now(timezone.utc).isoformat(),
              "claim_boundary": "checkout materialization only; no model patch or official score"}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
