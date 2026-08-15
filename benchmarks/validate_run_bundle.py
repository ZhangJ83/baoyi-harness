"""Validate the minimal, self-contained benchmark run bundle contract.

This module deliberately validates evidence packaging, not benchmark scores.
It accepts the recorder's existing ``run_manifest.json`` and ``steps.jsonl``
names as well as the compact research-facing aliases documented below.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from benchmarks.build_evidence_manifest import digest


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

    # Output files are commonly named output.pptx/output.docx rather than
    # placed in an output directory.  Do not treat metadata sidecars as the
    # final artifact.
    if kind == "output":
        for candidate in sorted(run_root.glob("output.*")):
            if candidate.name not in {"output.json", "output.jsonl"} and _nonempty(candidate):
                return candidate
    return None


def _load_json(path: Path, errors: list[str], label: str) -> Any | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f"{label}: invalid JSON at {path.name}: {type(exc).__name__}: {exc}")
        return None
    return value


def _validate_jsonl(path: Path, errors: list[str], label: str) -> None:
    try:
        rows = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, UnicodeError) as exc:
        errors.append(f"{label}: unreadable JSONL at {path.name}: {type(exc).__name__}: {exc}")
        return
    if not rows:
        errors.append(f"{label}: {path.name} has no events")
        return
    for line_number, line in enumerate(rows, start=1):
        try:
            json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"{label}: invalid JSONL at {path.name}:{line_number}: {exc.msg}")
            return


def _safe_member(run_root: Path, declared: str) -> Path | None:
    candidate = Path(declared)
    if candidate.is_absolute():
        return None
    resolved = (run_root / candidate).resolve()
    try:
        resolved.relative_to(run_root)
    except ValueError:
        return None
    return resolved


def _validate_manifest_files(run_root: Path, manifest: dict[str, Any], errors: list[str]) -> int:
    """Validate optional evidence-manifest-v1 file declarations.

    Existing lifecycle manifests do not contain a ``files`` table, so they
    remain valid.  When the existing manifest builder's table is present, its
    bytes and SHA-256 claims are checked with the same digest implementation.
    """
    rows = manifest.get("files")
    if rows is None:
        return 0
    if not isinstance(rows, list):
        errors.append("manifest: files must be a list when present")
        return 0

    checked = 0
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            errors.append(f"manifest: files[{index}] must contain a string path")
            continue
        declared = row["path"]
        path = _safe_member(run_root, declared)
        if path is None:
            errors.append(f"manifest: files[{index}] path escapes run directory: {declared}")
            continue
        if not path.is_file():
            errors.append(f"manifest: declared file missing: {declared}")
            continue
        checked += 1
        expected_bytes = row.get("bytes")
        if isinstance(expected_bytes, int) and path.stat().st_size != expected_bytes:
            errors.append(
                f"manifest: byte size mismatch for {declared}: "
                f"expected {expected_bytes}, got {path.stat().st_size}"
            )
        expected_digest = row.get("sha256")
        if isinstance(expected_digest, str) and digest(path).lower() != expected_digest.lower():
            errors.append(f"manifest: sha256 mismatch for {declared}")
    return checked


def validate(run_root: Path) -> dict[str, Any]:
    run_root = run_root.resolve()
    errors: list[str] = []
    components: dict[str, str | None] = {}

    if not run_root.is_dir():
        return {
            "schema": "xiaopu-benchmark-run-bundle-validation-v1",
            "run_root": str(run_root),
            "valid": False,
            "components": {},
            "errors": [f"run directory does not exist: {run_root}"],
            "boundary": "bundle completeness only; benchmark scores are not interpreted or changed",
        }

    for kind in ("input", "output", "trajectory", "tool_calls", "evaluation", "manifest"):
        found = _find_component(run_root, kind)
        components[kind] = str(found.relative_to(run_root)) if found is not None else None
        if found is None:
            if kind == "trajectory":
                errors.append(
                    "missing execution trace: add trajectory.md, steps.jsonl, "
                    "events.jsonl, or a non-empty trajectory/events directory"
                )
            elif kind == "output":
                errors.append("missing output: add output.<ext> or a non-empty output directory")
            else:
                names = ", ".join(_CANDIDATES[kind])
                errors.append(f"missing {kind}: expected one of {names}")

    manifest_files_checked = 0
    tool_calls = _find_component(run_root, "tool_calls")
    if tool_calls is not None:
        if tool_calls.suffix == ".jsonl":
            _validate_jsonl(tool_calls, errors, "tool_calls")
        else:
            value = _load_json(tool_calls, errors, "tool_calls")
            if value is not None and not isinstance(value, (list, dict)):
                errors.append("tool_calls: JSON root must be an array or object")

    evaluation = _find_component(run_root, "evaluation")
    if evaluation is not None:
        value = _load_json(evaluation, errors, "evaluation")
        if value is not None and not isinstance(value, dict):
            errors.append("evaluation: JSON root must be an object")

    trace = _find_component(run_root, "trajectory")
    if trace is not None and trace.is_file() and trace.suffix == ".jsonl":
        _validate_jsonl(trace, errors, "trajectory")

    manifest_path = _find_component(run_root, "manifest")
    if manifest_path is not None:
        value = _load_json(manifest_path, errors, "manifest")
        if value is not None and not isinstance(value, dict):
            errors.append("manifest: JSON root must be an object")
        elif isinstance(value, dict):
            manifest_files_checked = _validate_manifest_files(run_root, value, errors)

    return {
        "schema": "xiaopu-benchmark-run-bundle-validation-v1",
        "run_root": str(run_root),
        "valid": not errors,
        "components": components,
        "manifest_files_checked": manifest_files_checked,
        "errors": errors,
        "optional": {"screenshots": _nonempty(run_root / "screenshots")},
        "boundary": "bundle completeness only; benchmark scores are not interpreted or changed",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a Xiaopu benchmark run directory without executing a benchmark"
    )
    parser.add_argument("run", type=Path, help="benchmark run directory")
    parser.add_argument("--out", type=Path, help="optional JSON report path")
    args = parser.parse_args()
    result = validate(args.run)
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
