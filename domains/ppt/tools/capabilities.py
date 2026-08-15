"""PPT capability and facade-tool registry (vendor-neutral).

Concrete tool backends live in adapters; here each facade tool only declares
which capabilities it satisfies.
"""
from __future__ import annotations

from core.capability import Capability, register_capability
from core.tool import ToolSpec, register_tool

CAPABILITIES = (
    Capability("presentation.read", "read and inspect an existing deck"),
    Capability("presentation.edit", "mutate deck content and objects"),
    Capability("presentation.style", "change object and text styling"),
    Capability("presentation.render", "render the current artifact to images"),
    Capability("presentation.visual_inspect", "inspect rendered images"),
    Capability("presentation.structure_inspect", "inspect object structure and geometry"),
    Capability("presentation.arrange", "reposition and reflow objects"),
)

FACADE_TOOL_SPECS = (
    ToolSpec("ppt_open", ("presentation.read",), "open an existing deck"),
    ToolSpec("ppt_inspect", ("presentation.read", "presentation.structure_inspect"), "inspect deck objects"),
    ToolSpec("ppt_edit_text", ("presentation.edit",), "edit text and list structure"),
    ToolSpec("ppt_style", ("presentation.style",), "change object and text styling"),
    ToolSpec("ppt_arrange", ("presentation.arrange",), "reposition and reflow objects"),
    ToolSpec("ppt_render", ("presentation.render",), "render the artifact to images"),
    ToolSpec("ppt_visual_inspect", ("presentation.visual_inspect",), "inspect rendered images"),
    ToolSpec("ppt_check", ("presentation.structure_inspect",), "verify structure and geometry"),
    ToolSpec("ppt_save", ("presentation.edit", "presentation.style", "presentation.arrange"), "persist the artifact"),
)


def register_ppt_capabilities() -> None:
    for cap in CAPABILITIES:
        register_capability(cap)


def register_ppt_tools() -> None:
    for spec in FACADE_TOOL_SPECS:
        register_tool(spec)
