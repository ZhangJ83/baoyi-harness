"""Small, auditable verifier for a frozen SWE-bench Verified sample.

This deliberately separates repository/oracle validation from model scoring.
It never reports a task as solved merely because a checkout exists: the
result records whether the requested base commit, patch, and test command are
available, and preserves an explicit ``environment_incomplete`` state.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path


def _run(*args: str, cwd: Path) -> tuple[int, str]:
    p = subprocess.run(args, cwd=cwd, text=True, capture_output=True)
    return p.returncode, (p.stdout + p.stderr).strip()[-4000:]


def verify(root: Path, checkout_root: Path, limit: int) -> dict:
    manifest = json.loads((root / "benchmarks" / "official_swe_sample.json").read_text())
    detailed = {
        item["instance_id"]: item
        for item in json.loads((root / "research" / "swe_verified_sample.json").read_text())
    }
    rows = []
    for item in manifest["instances"][:limit]:
        short = item["instance_id"].split("__", 1)[-1]
        repo = checkout_root / short
        row = {"instance_id": item["instance_id"], "expected_base_commit": item["base_commit"]}
        row["official_patch_available"] = bool(detailed.get(item["instance_id"], {}).get("patch"))
        row["problem_statement_available"] = bool(detailed.get(item["instance_id"], {}).get("problem_statement"))
        patch = detailed.get(item["instance_id"], {}).get("patch", "")
        row["gold_patch_available"] = bool(patch)
        if not repo.exists():
            row.update(status="checkout_missing")
            rows.append(row)
            continue
        if patch:
            with tempfile.NamedTemporaryFile("w", suffix=".patch", encoding="utf-8", delete=False) as f:
                f.write(patch)
                patch_path = Path(f.name)
            code, detail = _run("git", "apply", "--check", str(patch_path), cwd=repo)
            patch_path.unlink(missing_ok=True)
            row["gold_patch_check"] = code == 0
            if code:
                row["gold_patch_error"] = detail
        code, head = _run("git", "rev-parse", "HEAD", cwd=repo)
        row["head"] = head
        if "not a git repository" in head and ".git/worktrees" in head:
            row["status"] = "worktree_unportable"
            continue
        if code or head != item["base_commit"]:
            row.update(status="base_commit_mismatch")
        else:
            row.update(status="checkout_verified")
        rows.append(row)
    return {
        "source": manifest["source"],
        "split": manifest["split"],
        "limit": limit,
        "rows": rows,
        "environment_incomplete": any(r["status"] != "checkout_verified" for r in rows),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument("--checkout-root", type=Path, required=True)
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--out", type=Path)
    args = p.parse_args()
    result = verify(args.root, args.checkout_root, args.limit)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        args.out.write_text(payload, encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
