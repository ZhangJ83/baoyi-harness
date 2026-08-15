"""Score a fixed PPTBench manifest against produced deck artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ppt_score import score


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("artifacts", type=Path, help="directory containing <task-id>.pptx")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8-sig"))
    rows = []
    for task in manifest["tasks"]:
        artifact = args.artifacts / f"{task['id']}.pptx"
        if artifact.is_file():
            result = score(artifact, task["min_slides"], task.get("required_text", []))
        else:
            result = {"artifact": str(artifact), "score": 0.0, "checks": {"artifact_exists": False}, "deterministic": True}
        rows.append({"task_id": task["id"], "kind": task["kind"], **result})
    report = {"manifest": manifest["version"], "tasks": rows, "mean_score": sum(r["score"] for r in rows) / len(rows)}
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["mean_score"] == 1.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
