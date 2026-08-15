"""Fail-closed normalization of observable competitor CLI JSON event streams.

The module deliberately does not infer hidden model steps. A field is emitted
only when the public CLI stream exposes a defensible counter.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Iterable


TOOL_ITEM_TYPES = {"command_execution", "mcp_tool_call", "file_change", "web_search"}


@dataclass
class StreamLedger:
    provider: str
    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: int = 0
    steps: int | None = None
    final_event_seen: bool = False
    parse_errors: list[str] = field(default_factory=list)
    observability_gaps: list[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return (
            self.final_event_seen
            and not self.parse_errors
            and not self.observability_gaps
            and self.steps is not None
        )

    def as_dict(self) -> dict:
        return {
            "provider": self.provider,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "tool_calls": self.tool_calls,
            "steps": self.steps,
            "final_event_seen": self.final_event_seen,
            "parse_errors": self.parse_errors,
            "observability_gaps": self.observability_gaps,
            "complete": self.complete,
        }


def _events(lines: Iterable[str], ledger: StreamLedger) -> Iterable[dict]:
    for line_number, raw in enumerate(lines, start=1):
        if not raw.strip():
            continue
        try:
            event = json.loads(raw)
        except json.JSONDecodeError as exc:
            ledger.parse_errors.append(f"line {line_number}: invalid JSON: {exc.msg}")
            continue
        if not isinstance(event, dict):
            ledger.parse_errors.append(f"line {line_number}: event is not an object")
            continue
        yield event


def _nonnegative_int(value: object, *, field_name: str, ledger: StreamLedger) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        ledger.parse_errors.append(f"{field_name} is not a nonnegative integer")
        return 0
    return value


def normalize_claude(lines: Iterable[str]) -> dict:
    """Normalize Claude Code ``--output-format stream-json`` output.

    Token usage is summed only from assistant message events. Result-event
    usage is intentionally ignored because it may repeat cumulative totals.
    """
    ledger = StreamLedger(provider="claude_code", steps=0)
    usage_events = 0
    for event in _events(lines, ledger):
        event_type = event.get("type")
        if event_type == "assistant":
            message = event.get("message")
            if not isinstance(message, dict):
                ledger.parse_errors.append("assistant event has no message object")
                continue
            usage = message.get("usage")
            if not isinstance(usage, dict):
                ledger.parse_errors.append("assistant message has no usage object")
                continue
            ledger.input_tokens += _nonnegative_int(
                usage.get("input_tokens"), field_name="input_tokens", ledger=ledger
            )
            ledger.output_tokens += _nonnegative_int(
                usage.get("output_tokens"), field_name="output_tokens", ledger=ledger
            )
            usage_events += 1
            ledger.steps = (ledger.steps or 0) + 1
            content = message.get("content", [])
            if not isinstance(content, list):
                ledger.parse_errors.append("assistant message content is not a list")
                continue
            ledger.tool_calls += sum(
                1 for block in content if isinstance(block, dict) and block.get("type") == "tool_use"
            )
        elif event_type == "result":
            ledger.final_event_seen = True
    if usage_events == 0:
        ledger.observability_gaps.append("no assistant usage events")
    if not ledger.final_event_seen:
        ledger.observability_gaps.append("no final result event")
    return ledger.as_dict()


def normalize_codex(lines: Iterable[str]) -> dict:
    """Normalize Codex ``exec --json`` output without inventing step counts.

    Current Codex JSON exposes cumulative turn usage and tool items, but not a
    provider-call/model-response counter equivalent to Claude assistant events.
    The returned ledger therefore remains intentionally incomplete.
    """
    ledger = StreamLedger(provider="codex", steps=None)
    usage_seen = False
    seen_tool_ids: set[str] = set()
    for event in _events(lines, ledger):
        event_type = event.get("type")
        if event_type == "item.started":
            item = event.get("item")
            if isinstance(item, dict) and item.get("type") in TOOL_ITEM_TYPES:
                item_id = item.get("id")
                dedupe_key = str(item_id) if item_id is not None else json.dumps(item, sort_keys=True)
                if dedupe_key not in seen_tool_ids:
                    seen_tool_ids.add(dedupe_key)
                    ledger.tool_calls += 1
        elif event_type == "turn.completed":
            usage = event.get("usage")
            if not isinstance(usage, dict):
                ledger.parse_errors.append("turn.completed has no usage object")
                continue
            ledger.input_tokens = _nonnegative_int(
                usage.get("input_tokens"), field_name="input_tokens", ledger=ledger
            )
            ledger.output_tokens = _nonnegative_int(
                usage.get("output_tokens"), field_name="output_tokens", ledger=ledger
            )
            usage_seen = True
            ledger.final_event_seen = True
    if not usage_seen:
        ledger.observability_gaps.append("no turn.completed usage event")
    ledger.observability_gaps.append("model step count is not exposed by Codex exec --json")
    return ledger.as_dict()


def normalize(provider: str, lines: Iterable[str]) -> dict:
    if provider == "claude_code":
        return normalize_claude(lines)
    if provider == "codex":
        return normalize_codex(lines)
    raise ValueError(f"unsupported provider: {provider}")
