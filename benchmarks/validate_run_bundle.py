"""Benchmark run bundle validator (compatibility proxy to agent.run_bundle_validator)."""
from __future__ import annotations

from agent.run_bundle_validator import (
    _CANDIDATES,
    _find_component,
    _load_json,
    _nonempty,
    _safe_member,
    _validate_jsonl,
    _validate_manifest_files,
    digest,
    main,
    validate,
    validate_run_bundle,
)

__all__ = [
    "_CANDIDATES",
    "_find_component",
    "_load_json",
    "_nonempty",
    "_safe_member",
    "_validate_jsonl",
    "_validate_manifest_files",
    "digest",
    "main",
    "validate",
    "validate_run_bundle",
]


if __name__ == "__main__":
    raise SystemExit(main())
