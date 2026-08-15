"""Generic tool abstraction.

The core knows that a harness exposes *tools* and that tools satisfy
capabilities. Concrete tool names and backends are adapter territory.
"""
from dataclasses import dataclass, field
from typing import Dict, Tuple


@dataclass(frozen=True)
class ToolSpec:
    name: str
    capabilities: Tuple[str, ...] = ()
    description: str = ""


TOOLS: Dict[str, ToolSpec] = {}


def register_tool(spec: ToolSpec) -> None:
    if spec.name in TOOLS:
        raise ValueError(f"tool already registered: {spec.name}")
    TOOLS[spec.name] = spec


def get_tool(name: str) -> ToolSpec:
    try:
        return TOOLS[name]
    except KeyError:
        raise KeyError(f"unknown tool: {name}") from None


def all_tools() -> tuple:
    return tuple(sorted(TOOLS.values(), key=lambda t: t.name))


def tools_for_capability(capability_id: str) -> tuple:
    return tuple(t for t in all_tools() if capability_id in t.capabilities)
