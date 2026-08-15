"""Vendor-neutral PPT tool facade: capability id -> facade tool names.

No concrete backend (edit library, render engine, inspection script) may
appear here; that mapping is the adapters' job.
"""
from __future__ import annotations

from domains.ppt.tools.capabilities import (
    CAPABILITIES,
    FACADE_TOOL_SPECS,
    register_ppt_capabilities,
    register_ppt_tools,
)

# Derived from FACADE_TOOL_SPECS so the facade and the tool registry can never drift.
_PPT_TOOL_FACADE: dict[str, list[str]] = {}
for _spec in FACADE_TOOL_SPECS:
    for _cap in _spec.capabilities:
        _PPT_TOOL_FACADE.setdefault(_cap, []).append(_spec.name)
PPT_TOOL_FACADE = {cap: tuple(tools) for cap, tools in _PPT_TOOL_FACADE.items()}

__all__ = [
    "CAPABILITIES", "FACADE_TOOL_SPECS", "PPT_TOOL_FACADE",
    "register_ppt_capabilities", "register_ppt_tools",
]
