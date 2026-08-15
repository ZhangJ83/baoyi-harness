"""Cross-layer boundary tests for the portable harness architecture.

Enforces:
- core/ is generic: no domain vocabulary, no upper-layer imports.
- domains/ppt/ may import core and legacy agent implementation, never adapters.
- adapters/ never import legacy agent code; they are the only layer naming
  concrete backends (python-pptx / soffice / libreoffice).
- The whole stack assembles and renders for every registered PPT skill.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_DOMAIN_WORDS = (
    "ppt", "pptx", "slide", "deck", "powerpoint", "xmind", "office", "xlsx",
    "shape", "chart",
)


def py_files(pkg: str) -> tuple[Path, ...]:
    return tuple((ROOT / pkg).rglob("*.py"))


def sources_of(files: tuple[Path, ...]) -> str:
    return "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in files)


def test_core_has_no_domain_vocabulary():
    text = sources_of(py_files("core")).lower()
    for word in FORBIDDEN_DOMAIN_WORDS:
        assert word not in text, f"core/ leaks domain vocabulary: {word!r}"


def test_core_imports_only_stdlib_and_core():
    pattern = re.compile(r"^\s*(?:import|from)\s+([A-Za-z0-9_\.]+)", re.MULTILINE)
    stdlib_and_core = {"core", "abc", "dataclasses", "pathlib", "typing", "hashlib",
                       "collections", "collections.abc", "json", "functools", "os",
                       "sys", "re", "enum", "itertools", "types"}
    for path in py_files("core"):
        for match in pattern.finditer(path.read_text(encoding="utf-8")):
            module = match.group(1)
            root = module.split(".")[0]
            assert root in stdlib_and_core, f"{path}: unexpected import {module!r}"


def test_domains_never_import_adapters():
    pattern = re.compile(r"^\s*(?:import|from)\s+([A-Za-z0-9_\.]+)", re.MULTILINE)
    for path in py_files("domains"):
        for match in pattern.finditer(path.read_text(encoding="utf-8")):
            assert match.group(1).split(".")[0] != "adapters", f"{path}: domains imports adapters"


def test_adapters_never_import_legacy_agent():
    pattern = re.compile(r"^\s*(?:import|from)\s+([A-Za-z0-9_\.]+)", re.MULTILINE)
    for path in py_files("adapters"):
        for match in pattern.finditer(path.read_text(encoding="utf-8")):
            assert match.group(1).split(".")[0] != "agent", f"{path}: adapters imports legacy agent code"


def test_ppt_tools_are_vendor_neutral():
    import re as _re
    for path in (ROOT / "domains" / "ppt" / "tools").rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="replace").lower()
        for backend in ("python-pptx", "libreoffice", "soffice"):
            assert backend not in text, f"{path}: vendor backend leaks into domain tools layer"
        assert not _re.search(r"\bcom\b", text), f"{path}: vendor backend leaks into domain tools layer"


def _one_skill():
    from core.skill import SkillSpec
    return SkillSpec(
        name="layout_reflow",
        description="reflow existing content",
        capabilities=("presentation.read", "presentation.edit", "presentation.render",
                      "presentation.visual_inspect"),
        allowed_capabilities=("presentation.read", "presentation.edit"),
        required_inputs=("binary",),
        verification_contract=("structural", "render", "visual"),
        mutation_scope="slides/shapes/properties",
    )


@pytest.mark.parametrize("adapter_name", ["claude_code", "codex", "opencode", "workbuddy"])
def test_full_stack_renders_skill(adapter_name):
    import domains.ppt  # noqa: F401  ensures capabilities/skills are registered
    from adapters import get_adapter
    adapter = get_adapter(adapter_name)
    rendered = adapter.render_skill(_one_skill())
    assert rendered.strip()
    adapter.validate(_one_skill())


def test_workbuddy_skill_output_is_json():
    from adapters import get_adapter
    rendered = get_adapter("workbuddy").render_skill(_one_skill())
    payload = json.loads(rendered)
    assert payload["skill"] == "layout_reflow"


def test_codex_tool_manifest_is_json():
    from adapters import get_adapter
    rendered = get_adapter("codex").render_tool_manifest(
        ("presentation.read", "presentation.render"))
    payload = json.loads(rendered)
    assert "presentation.read" in payload
    assert "presentation.render" in payload


def test_ppt_domain_pack_registers_ontology():
    from domains.ppt.task_types import PPTTaskType
    assert {t.value for t in PPTTaskType} == {
        "atomic_edit", "atomic_style", "element_creation", "layout_reflow",
        "diagram_composition", "compose_from_slides", "source_grounded_build",
        "template_build",
    }


def test_runner_assemble_compiles_and_renders():
    from runner import assemble
    from core.model import Task

    assembly = assemble(domain="ppt", adapter="claude_code")
    task = Task(id="demo", instruction="convert slide 8 checklist into two columns")
    contract = assembly.compile(task)
    assert contract.task_type == "layout_reflow"
    rendered = assembly.render_skill(contract.task_type)
    assert "layout_reflow" in rendered
