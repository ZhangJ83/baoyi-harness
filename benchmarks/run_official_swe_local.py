"""Invoke the pinned official SWE-bench local Docker evaluator.

The launcher avoids importing the package-level collection helpers (which
pull in optional GitHub tooling) and exposes the official harness module
directly. It is intended for a smoke or real prediction run, not for making
an oracle patch look like an agent result.
"""
from __future__ import annotations

import argparse
import importlib
import os
import sys
import types
from pathlib import Path


def _install_source_paths() -> Path:
    project = Path(__file__).resolve().parents[2]
    swe_root = project / "official_refs" / "swe-bench"
    refs = [
        swe_root,
        project / "official_refs" / "ghapi",
        project / "official_refs" / "fastcore",
        project / "official_refs" / "fastspec",
        project / "official_refs" / "unidiff",
    ]
    for path in refs:
        sys.path.insert(0, str(path))
    # The local venv contains Docker SDK; datasets remains in the workspace
    # Python environment. Both are pure import paths and no package is copied.
    tb_site = swe_root.parent / "terminal-bench" / ".venv" / "Lib" / "site-packages"
    if tb_site.exists():
        sys.path.insert(0, str(tb_site))
    # Bypass swebench/__init__.py's collection-only imports while retaining the
    # official package submodule tree and evaluator implementation.
    root = swe_root / "swebench"
    pkg = types.ModuleType("swebench")
    pkg.__path__ = [str(root)]
    sys.modules["swebench"] = pkg
    harness = types.ModuleType("swebench.harness")
    harness.__path__ = [str(root / "harness")]
    sys.modules["swebench.harness"] = harness
    return project


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        default="SWE-bench/SWE-bench_Verified",
        help="Official HF name or local JSON/JSONL dataset file",
    )
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--instance-id", action="append", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--report-dir", required=True)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--max-workers", type=int, default=1)
    parser.add_argument("--force-rebuild", action="store_true")
    args = parser.parse_args()
    _install_source_paths()
    evaluator = importlib.import_module("swebench.harness.run_evaluation")
    evaluator.main(
        dataset_name=args.dataset,
        split="test",
        instance_ids=args.instance_id,
        predictions_path=args.predictions,
        max_workers=args.max_workers,
        force_rebuild=args.force_rebuild,
        cache_level="env",
        clean=False,
        open_file_limit=4096,
        run_id=args.run_id,
        timeout=args.timeout,
        namespace=None,
        rewrite_reports=False,
        modal=False,
        report_dir=args.report_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
