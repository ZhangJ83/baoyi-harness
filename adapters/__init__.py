"""Vendor adapter registry."""
from __future__ import annotations

from typing import Dict

from adapters.base import CapabilityBinding, HarnessAdapter, resolve_bindings
from adapters.claude_code import ClaudeCodeAdapter
from adapters.codex import CodexAdapter
from adapters.implementations import (
    CANDIDATES,
    ResolutionContext,
    ToolImplementation,
    candidate_implementations,
    resolve_implementations,
    resolve_primary,
)
from adapters.opencode import OpenCodeAdapter
from adapters.workbuddy import WorkBuddyAdapter

ADAPTERS: Dict[str, HarnessAdapter] = {
    "claude_code": ClaudeCodeAdapter(),
    "codex": CodexAdapter(),
    "opencode": OpenCodeAdapter(),
    "workbuddy": WorkBuddyAdapter(),
}


def get_adapter(name: str) -> HarnessAdapter:
    try:
        return ADAPTERS[name]
    except KeyError:
        raise KeyError(f"unknown harness adapter: {name}") from None


__all__ = [
    "ADAPTERS", "get_adapter", "HarnessAdapter", "CapabilityBinding", "resolve_bindings",
    "ClaudeCodeAdapter", "CodexAdapter", "OpenCodeAdapter", "WorkBuddyAdapter",
    "CANDIDATES", "ResolutionContext", "ToolImplementation",
    "candidate_implementations", "resolve_implementations", "resolve_primary",
]
