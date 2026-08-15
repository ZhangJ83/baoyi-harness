"""Durable session snapshots for the TUI/CLI.

A snapshot keeps the model-visible conversation plus the auditable task facts;
deck bytes and loop counters are intentionally not serialized, so a resumed
session re-derives the deck from its working copy instead of trusting memory.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from . import config
from .redact import redact


@dataclass
class SessionRecord:
    id: str
    title: str
    created_at: str
    updated_at: str
    model: str
    workspace: str
    turn_count: int
    path: Path
    summary: str = ""


def _sessions_dir() -> Path:
    path = config.state_home() / "sessions"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def snapshot_harness(harness) -> dict:
    """Serialize the resumable slice of a harness session."""
    state = harness.state
    spec = getattr(harness, "task_spec", None)
    messages = []
    for message in getattr(harness, "messages", []):
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        if role in {"system", "user", "assistant"}:
            content = message.get("content", "")
            if role != "system":
                content = redact(str(content))
            messages.append({"role": role, "content": content})
            if role == "assistant" and message.get("tool_calls"):
                calls = []
                for tc in message["tool_calls"]:
                    function = dict(tc.get("function") or {})
                    calls.append({
                        "id": tc.get("id"),
                        "type": "function",
                        "function": {
                            "name": function.get("name"),
                            "arguments": function.get("arguments", ""),
                        },
                    })
                messages[-1]["tool_calls"] = calls
                if message.get("reasoning_content"):
                    messages[-1]["reasoning_content"] = message["reasoning_content"]
        elif role == "tool":
            messages.append({"role": "tool", "tool_call_id": message.get("tool_call_id"),
                             "content": redact(str(message.get("content", "")))}) if message.get("tool_call_id") else None
    return {
        "schema": "xiaopu-session-snapshot-v1",
        "id": getattr(getattr(harness, "session", None), "id", uuid4().hex),
        "created_at": _now(),
        "model": getattr(getattr(harness, "llm", None), "model", config.model()),
        "workspace": str(config.sandbox_root()),
        "messages": messages,
        "facts": dict(state.facts),
        "content_brief": getattr(state, "content_brief", ""),
        "mutation_epoch": state.mutation_epoch,
        "phase": state.phase.value,
        "task_spec": spec.to_dict() if spec is not None else None,
        "active_goal": getattr(harness, "active_goal", None).objective if getattr(harness, "active_goal", None) else None,
        "final_summary": getattr(state, "final_summary", None),
        # Progress-preservation state: resume must reload the same working deck,
        # not the frozen input or a stale copy.
        "deck_source_path": str(getattr(harness, "deck_source_path", "") or ""),
        "deck_working_path": str(getattr(harness, "deck_working_path", "") or ""),
        "unresolved_checks": sorted(getattr(state, "unresolved_checks", set())),
        "repair_attempts": getattr(state, "repair_attempts", 0),
        "last_verification_failed": getattr(state, "last_verification_failed", False),
        "verification_contract_terms": getattr(state, "verification_contract_terms", None),
    }


def save_session(harness, title: str = "") -> SessionRecord:
    payload = snapshot_harness(harness)
    session_id = payload["id"]
    title = (title or _derive_title(payload))[:80]
    payload["title"] = title
    path = _sessions_dir() / f"{session_id}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    turn_count = sum(1 for m in payload["messages"] if m.get("role") == "assistant")
    summary = (payload.get("final_summary") or "").strip()[:200]
    return SessionRecord(id=session_id, title=title, created_at=payload["created_at"],
                         updated_at=payload["created_at"], model=payload["model"],
                         workspace=payload["workspace"], turn_count=turn_count,
                         path=path, summary=summary)


def _derive_title(payload: dict) -> str:
    for message in payload.get("messages", []):
        if message.get("role") == "user":
            text = " ".join(str(message.get("content", "")).split())[:48]
            if text:
                return text
    return "untitled"


def list_sessions() -> list[SessionRecord]:
    records = []
    for path in sorted(_sessions_dir().glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        title = payload.get("title") or _derive_title(payload)
        records.append(SessionRecord(
            id=payload.get("id", path.stem), title=title,
            created_at=payload.get("created_at", ""), updated_at=payload.get("created_at", ""),
            model=payload.get("model", ""), workspace=payload.get("workspace", ""),
            turn_count=sum(1 for m in payload.get("messages", []) if m.get("role") == "assistant"),
            path=path, summary=(payload.get("final_summary") or "")[:200]))
    return records


def load_session(session_id: str) -> dict | None:
    path = _sessions_dir() / f"{session_id}.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    payload["path"] = str(path)
    return payload


def delete_session(session_id: str) -> bool:
    path = _sessions_dir() / f"{session_id}.json"
    if not path.is_file():
        return False
    path.unlink()
    return True


def restore_harness(harness, payload: dict) -> str:
    """Restore the resumable slice into a harness. Returns a short report."""
    if hasattr(harness, "reset"):
        harness.reset()
    else:
        from .state import RunState

        harness.messages = []
        harness.state = RunState()
    messages = []
    for message in payload.get("messages", []):
        if message.get("role") in {"system", "user", "assistant", "tool"}:
            messages.append(dict(message))
    harness.messages = messages
    harness.started = bool(messages)
    state = harness.state
    state.facts.update(dict(payload.get("facts", {})))
    state.content_brief = payload.get("content_brief", "")
    state.mutation_epoch = int(payload.get("mutation_epoch", 0))
    state.unresolved_checks = set(payload.get("unresolved_checks", []))
    state.repair_attempts = int(payload.get("repair_attempts", 0))
    state.last_verification_failed = bool(payload.get("last_verification_failed", False))
    if isinstance(payload.get("verification_contract_terms"), dict):
        state.verification_contract_terms = payload["verification_contract_terms"]
    # Reload the persisted working deck so a resumed turn never starts from the
    # frozen input or an unrelated file.
    deck_path = payload.get("deck_working_path") or payload.get("deck_source_path")
    if deck_path and getattr(harness, "deck", None) is None:
        from pathlib import Path as _Path
        from pptx import Presentation as _Presentation
        candidate = _Path(deck_path)
        if not candidate.is_absolute():
            candidate = config.sandbox_root() / candidate
        if candidate.is_file():
            try:
                harness.deck = _Presentation(str(candidate))
                harness.deck_source_path = payload.get("deck_source_path")
                harness.deck_working_path = payload.get("deck_working_path")
            except Exception:
                pass
    from .state import RuntimePhase
    try:
        state.phase = RuntimePhase(payload.get("phase", "intake"))
    except ValueError:
        state.phase = RuntimePhase.INTAKE
    task_spec = payload.get("task_spec")
    if task_spec:
        from .task_compiler import TaskSpec
        try:
            harness.task_spec = TaskSpec(
                task_root=task_spec.get("task_root", ""), artifact_mode=task_spec.get("artifact_mode", "edit_existing"),
                intent=task_spec.get("intent", "atomic_edit"), skill=task_spec.get("skill", "ppt.atomic_edit"),
                primary_input=task_spec.get("primary_input", ""), output_path=task_spec.get("output_path", ""),
                operation=task_spec.get("operation", ""),
                source_slides=tuple(task_spec.get("source_slides", ())),
                mutation_slides=tuple(task_spec.get("mutation_slides", ())),
                verification=tuple(task_spec.get("verification", ("ppt_structural",))),
                plan=tuple(task_spec.get("plan", ())),
            )
        except TypeError:
            harness.task_spec = None
    if payload.get("active_goal") and hasattr(harness, "start_goal"):
        try:
            harness.start_goal(payload["active_goal"])
        except Exception:
            pass
    title = _derive_title(payload)
    return f"会话 {payload.get('id')} 已恢复：{title}（{len(messages)} 条消息，epoch {state.mutation_epoch}）"


def export_session(session_id: str, target: Path) -> Path:
    payload = load_session(session_id)
    if payload is None:
        raise ValueError(f"session not found: {session_id}")
    lines = [f"# Xiaopu session {session_id}", f"model: {payload.get('model')}",
             f"workspace: {payload.get('workspace')}", ""]
    for message in payload.get("messages", []):
        role = message.get("role", "?")
        content = str(message.get("content", ""))
        lines.append(f"## {role}\n{content}\n")
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines), encoding="utf-8")
    return target
