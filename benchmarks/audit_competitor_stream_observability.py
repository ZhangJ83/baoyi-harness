"""Audit what the public competitor CLI JSON streams expose without inference."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from agent.competitor_stream_ledger import normalize_claude, normalize_codex


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--claude", type=Path, required=True)
    parser.add_argument("--codex", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    claude = normalize_claude(args.claude.read_text(encoding="utf-8").splitlines())
    codex = normalize_codex(args.codex.read_text(encoding="utf-8").splitlines())
    result = {
        "schema": "competitor-stream-observability-v1",
        "source_kind": "representative schema fixtures, not live benchmark traces",
        "systems": {"claude_code": claude, "codex": codex},
        "strict_common_step_observable": bool(claude["steps"] is not None and codex["steps"] is not None),
        "strict_parity_ready": bool(claude["complete"] and codex["complete"]),
        "decision": "retain fail-closed parity gate; do not infer Codex model steps",
        "next_action": "pre-register a vendor-independent observable budget contract or obtain an authoritative Codex step counter before live matched evaluation",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
