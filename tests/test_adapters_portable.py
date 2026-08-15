"""Harness adapter tests: portable specs -> four vendor formats."""
from __future__ import annotations

import json

import pytest

import domains.ppt  # noqa: F401  registers capabilities used by validation

from core.skill import SkillSpec

SAMPLE = SkillSpec(
    name="layout_reflow",
    description="reflow existing content into two columns",
    capabilities=("presentation.read", "presentation.edit", "presentation.render",
                  "presentation.visual_inspect"),
    allowed_capabilities=("presentation.read", "presentation.edit"),
    required_inputs=("binary",),
    verification_contract=("structural", "render", "visual"),
    mutation_scope="slides/shapes/properties",
)


@pytest.mark.parametrize("name", ["claude_code", "codex", "opencode", "workbuddy"])
def test_adapter_registry(name):
    from adapters import ADAPTERS, get_adapter

    assert get_adapter(name) is ADAPTERS[name]
    assert ADAPTERS[name].name == name


def test_claude_code_renders_frontmatter():
    from adapters import get_adapter

    rendered = get_adapter("claude_code").render_skill(SAMPLE)
    assert rendered.startswith("---")
    assert "name: layout_reflow" in rendered
    assert "allowed-tools:" in rendered
    assert "Read" in rendered


def test_codex_tools_json_section_is_valid_json():
    from adapters import get_adapter

    rendered = get_adapter("codex").render_skill(SAMPLE)
    marker = "# tools.json"
    assert marker in rendered
    payload = json.loads(rendered.split(marker, 1)[1].strip())
    assert "presentation.read" in payload


def test_codex_tool_manifest_is_json():
    from adapters import get_adapter

    payload = json.loads(get_adapter("codex").render_tool_manifest(("presentation.read", "presentation.render")))
    assert "presentation.read" in payload


def test_opencode_renders_tools_section():
    from adapters import get_adapter

    rendered = get_adapter("opencode").render_skill(SAMPLE)
    assert "name: layout_reflow" in rendered
    assert "tools:" in rendered
    assert "capability: presentation.read" in rendered


def test_workbuddy_renders_valid_json():
    from adapters import get_adapter

    payload = json.loads(get_adapter("workbuddy").render_skill(SAMPLE))
    assert payload["skill"] == "layout_reflow"
    assert payload["tools"]
    assert payload["verification_contract"] == ["structural", "render", "visual"]


def test_validate_rejects_unknown_capability():
    from adapters import get_adapter

    bad = SkillSpec(name="x", description="x", capabilities=("presentation.missing",))
    with pytest.raises(KeyError):
        get_adapter("claude_code").validate(bad)


def test_render_is_deterministic():
    from adapters import get_adapter

    a = get_adapter("claude_code").render_skill(SAMPLE)
    b = get_adapter("claude_code").render_skill(SAMPLE)
    assert a == b


def test_render_capability_resolution_is_harness_specific():
    from adapters import get_adapter
    from adapters.implementations import ResolutionContext, resolve_primary

    # Claude Code on Windows -> PowerPoint COM
    assert resolve_primary("presentation.render", ResolutionContext("claude_code", "windows")).backend == "powerpoint_com"
    # Codex sandbox -> LibreOffice
    assert resolve_primary("presentation.render", ResolutionContext("codex", "linux")).backend == "libreoffice"
    # WorkBuddy -> native renderer
    assert resolve_primary("presentation.render", ResolutionContext("workbuddy", "any")).backend == "workbuddy_native"
    # Available backends override platform preference
    assert resolve_primary(
        "presentation.render",
        ResolutionContext("claude_code", "windows", available_backends=("libreoffice",)),
    ).backend == "libreoffice"
    # Resolved skill output carries the selected implementation
    codex_render = get_adapter("codex").render_tool_manifest(("presentation.render",))
    assert "soffice" in codex_render
    claude_render = get_adapter("claude_code").render_tool_manifest(("presentation.render",))
    assert "PowerShell COM render script" in claude_render


def test_every_ppt_skill_renders_on_every_adapter():
    from adapters import ADAPTERS
    from domains.ppt.skills import PPT_SKILLS

    for adapter in ADAPTERS.values():
        for spec in PPT_SKILLS.values():
            rendered = adapter.render_skill(spec)
            assert rendered.strip()
