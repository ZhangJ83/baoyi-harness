"""Candidate tool implementations and harness-specific resolution.

One capability may have several candidate implementations (editing library,
COM, render engine, native tool). Resolution order is deterministic:

1. candidates explicitly bound to this harness (native/preferred tools);
2. candidates whose backend is in ``available_backends``;
3. candidates matching the current platform;
4. first candidate in registration order.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Sequence, Tuple


@dataclass(frozen=True)
class ToolImplementation:
    capability_id: str
    backend: str
    tool: str
    platforms: Tuple[str, ...] = ("any",)
    harness: Optional[str] = None  # None = harness-agnostic candidate


@dataclass(frozen=True)
class ResolutionContext:
    harness: str
    platform: str = "windows"
    available_backends: Tuple[str, ...] = ()


CANDIDATES: Dict[str, Tuple[ToolImplementation, ...]] = {
    "presentation.read": (
        ToolImplementation("presentation.read", "claude_read", "Read", harness="claude_code"),
        ToolImplementation("presentation.read", "opencode_read", "read", harness="opencode"),
        ToolImplementation("presentation.read", "workbuddy_native", "ppt_open", harness="workbuddy"),
        ToolImplementation("presentation.read", "python_pptx", "Bash(python-pptx read/inspect script)"),
    ),
    "presentation.edit": (
        ToolImplementation("presentation.edit", "claude_edit", "Edit", harness="claude_code"),
        ToolImplementation("presentation.edit", "opencode_edit", "edit", harness="opencode"),
        ToolImplementation("presentation.edit", "workbuddy_native", "ppt_edit_text", harness="workbuddy"),
        ToolImplementation("presentation.edit", "python_pptx", "Bash(python-pptx edit script)"),
    ),
    "presentation.style": (
        ToolImplementation("presentation.style", "claude_edit", "Edit", harness="claude_code"),
        ToolImplementation("presentation.style", "opencode_edit", "edit", harness="opencode"),
        ToolImplementation("presentation.style", "workbuddy_native", "ppt_style", harness="workbuddy"),
        ToolImplementation("presentation.style", "python_pptx", "Bash(python-pptx style script)"),
    ),
    "presentation.render": (
        ToolImplementation("presentation.render", "opencode_bash", "bash", harness="opencode"),
        ToolImplementation("presentation.render", "powerpoint_com", "PowerShell COM render script", platforms=("windows",)),
        ToolImplementation("presentation.render", "libreoffice", "soffice --headless --convert-to png", platforms=("any",)),
        ToolImplementation("presentation.render", "workbuddy_native", "ppt_render", harness="workbuddy"),
    ),
    "presentation.visual_inspect": (
        ToolImplementation("presentation.visual_inspect", "opencode_bash", "bash", harness="opencode"),
        ToolImplementation("presentation.visual_inspect", "workbuddy_native", "ppt_visual_inspect", harness="workbuddy"),
        ToolImplementation("presentation.visual_inspect", "image_script", "Bash(image inspection script)"),
    ),
    "presentation.structure_inspect": (
        ToolImplementation("presentation.structure_inspect", "opencode_bash", "bash", harness="opencode"),
        ToolImplementation("presentation.structure_inspect", "workbuddy_native", "ppt_check", harness="workbuddy"),
        ToolImplementation("presentation.structure_inspect", "python_pptx", "Bash(python-pptx structure script)"),
    ),
    "presentation.arrange": (
        ToolImplementation("presentation.arrange", "claude_edit", "Edit", harness="claude_code"),
        ToolImplementation("presentation.arrange", "opencode_edit", "edit", harness="opencode"),
        ToolImplementation("presentation.arrange", "workbuddy_native", "ppt_arrange", harness="workbuddy"),
        ToolImplementation("presentation.arrange", "python_pptx", "Bash(python-pptx arrange script)"),
    ),
}


def candidate_implementations(capability_id: str) -> Tuple[ToolImplementation, ...]:
    try:
        return CANDIDATES[capability_id]
    except KeyError:
        raise KeyError(f"no candidate implementations for capability {capability_id!r}") from None


def resolve_implementations(
    capability_id: str, context: ResolutionContext
) -> Tuple[ToolImplementation, ...]:
    """Return candidate implementations in preference order for a harness context."""
    candidates = candidate_implementations(capability_id)
    compatible = [c for c in candidates if c.harness in (None, context.harness)]
    if not compatible:
        compatible = list(candidates)

    exact = [c for c in compatible if c.harness == context.harness]
    generic = [c for c in compatible if c.harness is None]
    pool = exact + generic  # harness-specific candidates always beat generic ones

    if context.available_backends:
        available = [c for c in pool if c.backend in context.available_backends]
        if available:
            pool = available

    platform_matches = [c for c in pool if context.platform in c.platforms or "any" in c.platforms]
    if platform_matches:
        pool = platform_matches

    return tuple(pool) or (candidates[0],)


def resolve_primary(capability_id: str, context: ResolutionContext) -> ToolImplementation:
    return resolve_implementations(capability_id, context)[0]


__all__ = [
    "CANDIDATES", "ResolutionContext", "ToolImplementation",
    "candidate_implementations", "resolve_implementations", "resolve_primary",
]
