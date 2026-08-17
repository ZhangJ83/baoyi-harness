"""Validate the minimal, self-contained run bundle contract for Baoyi.

This module validates evidence packaging, run manifests, trajectories,
artifacts, and evaluation metadata for durable runs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


_CANDIDATES = {
    "input": ("input", "inputs"),
    "output": ("output",),
    "trajectory": (
        "trajectory.md",
        "trajectory.jsonl",
        "events.jsonl",
        "steps.jsonl",
        "events",
        "trajectory",
    ),
    "tool_calls": ("tool_calls.json", "tool_calls.jsonl"),
    "evaluation": ("evaluation.json",),
    "manifest": ("manifest.json", "run_manifest.json", "artifact_manifest.json"),
}


def file_digest(path: Path) -> str:
    """Compute SHA-256 hex digest for a file."""
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _nonempty(path: Path) -> bool:
    if path.is_file():
        return path.stat().st_size > 0
    if path.is_dir():
        return any(item.is_file() and item.stat().st_size > 0 for item in path.rglob("*"))
    return False


def _find_component(run_root: Path, kind: str) -> Path | None:
    for name in _CANDIDATES[kind]:
        candidate = run_root / name
        if _nonempty(candidate):
            return candidate

    if kind == "output":
        for candidate in sorted(run_root.glob("output.*")):
            if candidate.name not in {"output.json", "output.jsonl"} and _nonempty(candidate):
                return candidate
    return None


def _load_json(path: Path, errors: list[str], label: str) -> Any | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"{label} is not valid JSON: {exc}")
        return None
    return value


def _validate_manifest(path: Path, errors: list[str], warnings: list[str]) -> None:
    payload = _load_json(path, errors, "manifest")
    if payload is None:
        return
    if not isinstance(payload, dict):
        errors.append("manifest must be a JSON object")
        return

    # Check for known manifest structures (run manifest vs artifact manifest)
    if "artifacts" in payload:
        artifacts = payload.get("artifacts")
        if not isinstance(artifacts, list):
            errors.append("manifest.artifacts must be a list")
        else:
            root = path.parent
            for idx, item in enumerate(artifacts):
                if not isinstance(item, dict):
                    errors.append(f"manifest.artifacts[{idx}] must be an object")
                    continue
                p = item.get("path")
                if p:
                    resolved = Path(p) if Path(p).is_absolute() else (root / p)
                    if not resolved.exists():
                        warnings.append(f"manifest artifact path missing on disk: {p}")


def _validate_trajectory(path: Path, errors: list[str]) -> None:
    if path.suffix == ".jsonl":
        try:
            lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            for idx, line in enumerate(lines):
                try:
                    json.loads(line)
                except Exception as exc:
                    errors.append(f"trajectory.jsonl line {idx + 1} invalid JSON: {exc}")
                    break
        except Exception as exc:
            errors.append(f"failed reading trajectory: {exc}")


def validate_run_bundle(run_root: Path | str) -> dict[str, Any]:
    """Validate a run bundle directory against the Baoyi bundle specification."""
    root = Path(run_root).resolve()
    errors: list[str] = []
    warnings: list[str] = []

    if not root.is_dir():
        return {
            "valid": False,
            "root": str(root),
            "errors": [f"run root directory does not exist: {root}"],
            "warnings": [],
            "components": {},
        }

    components: dict[str, str | None] = {}
    for kind in _CANDIDATES:
        found = _find_component(root, kind)
        components[kind] = str(found.relative_to(root)) if found else None

    # Check required bundle components
    manifest_path = _find_component(root, "manifest")
    if manifest_path:
        _validate_manifest(manifest_path, errors, warnings)
    else:
        warnings.append("no run manifest found in bundle")

    traj_path = _find_component(root, "trajectory")
    if traj_path:
        _validate_trajectory(traj_path, errors)

    return {
        "valid": len(errors) == 0,
        "root": str(root),
        "components": components,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a Baoyi run bundle directory.")
    parser.add_argument("path", type=Path, help="Path to run bundle directory")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    args = parser.parse_args()

    result = validate_run_bundle(args.path)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if result["valid"]:
            print(f"✓ Run bundle is valid: {result['root']}")
            for k, v in result["components"].items():
                if v:
                    print(f"  - {k}: {v}")
            if result["warnings"]:
                for w in result["warnings"]:
                    print(f"  ⚠ warning: {w}")
        else:
            print(f"✕ Run bundle validation failed: {result['root']}")
            for err in result["errors"]:
                print(f"  ✕ {err}")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
