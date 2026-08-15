"""Cross-CLI PreToolUse hook implementing a hard observable tool-call cap.

Claude Code and Codex accept the same deny payload for PreToolUse. The hook
counts a tool-use id before execution and denies every new call after the cap.
State is durable JSON so the benchmark ledger can audit allowed and denied
calls after the CLI exits.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


@contextmanager
def _locked(path: Path) -> Iterator[object]:
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = path.open("a+", encoding="utf-8")
    try:
        if os.name == "nt":
            import msvcrt

            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        yield stream
    finally:
        if os.name == "nt":
            import msvcrt

            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        stream.close()


def _read_state(stream: object) -> dict:
    stream.seek(0)
    raw = stream.read()
    if not raw.strip():
        return {"schema": "tool-budget-hook-v1", "allowed": [], "denied": []}
    try:
        state = json.loads(raw)
    except json.JSONDecodeError:
        return {
            "schema": "tool-budget-hook-v1",
            "allowed": [],
            "denied": [],
            "state_recovered_from_invalid_json": True,
        }
    if not isinstance(state.get("allowed"), list) or not isinstance(state.get("denied"), list):
        raise ValueError("invalid tool-budget state schema")
    return state


def _write_state(stream: object, state: dict) -> None:
    stream.seek(0)
    stream.truncate()
    stream.write(json.dumps(state, ensure_ascii=False, indent=2))
    stream.flush()
    os.fsync(stream.fileno())


def process_event(payload: dict, *, state_path: Path, max_tool_calls: int) -> dict | None:
    if max_tool_calls <= 0:
        raise ValueError("max_tool_calls must be positive")
    if payload.get("hook_event_name") not in {None, "PreToolUse"}:
        raise ValueError("hook payload is not PreToolUse")
    tool_name = payload.get("tool_name")
    tool_use_id = payload.get("tool_use_id")
    if not isinstance(tool_name, str) or not tool_name:
        raise ValueError("tool_name is required")
    if not isinstance(tool_use_id, str) or not tool_use_id:
        raise ValueError("tool_use_id is required for deduplicated accounting")
    with _locked(state_path) as stream:
        state = _read_state(stream)
        known = {row["tool_use_id"] for row in state["allowed"] + state["denied"]}
        if tool_use_id in known:
            return None
        row = {"tool_use_id": tool_use_id, "tool_name": tool_name}
        if len(state["allowed"]) >= max_tool_calls:
            state["denied"].append(row)
            state["max_tool_calls"] = max_tool_calls
            _write_state(stream, state)
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": f"Observable tool-call budget exhausted ({max_tool_calls}).",
                }
            }
        state["allowed"].append(row)
        state["max_tool_calls"] = max_tool_calls
        _write_state(stream, state)
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", type=Path, default=Path(os.environ.get("XIAOPU_TOOL_BUDGET_STATE", "/logs/agent/tool_budget_hook.json")))
    parser.add_argument("--max-tool-calls", type=int, default=int(os.environ.get("XIAOPU_MAX_TOOL_CALLS", "60")))
    args = parser.parse_args()
    try:
        payload = json.load(sys.stdin)
        decision = process_event(payload, state_path=args.state, max_tool_calls=args.max_tool_calls)
    except Exception as exc:
        # A broken budget hook must fail closed rather than silently unmetering
        # the comparator.
        decision = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"Budget hook failure: {type(exc).__name__}",
            }
        }
    if decision is not None:
        json.dump(decision, sys.stdout)
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
