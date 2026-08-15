"""Tests for the generic core layer: no domain vocabulary, no upper imports, clean contracts."""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"

FORBIDDEN = ("ppt", "pptx", "slide", "deck", "powerpoint", "xmind", "office", "xlsx", "shape", "chart")


def test_core_has_no_domain_vocabulary():
    text = "\n".join(p.read_text(encoding="utf-8") for p in CORE.rglob("*.py")).lower()
    for word in FORBIDDEN:
        assert word not in text, word


def test_core_imports_only_stdlib_and_core():
    allowed = {"core", "abc", "dataclasses", "pathlib", "typing", "hashlib",
               "collections", "collections.abc", "json", "functools", "os", "sys", "re", "enum"}
    pattern = re.compile(r"^\s*(?:import|from)\s+([A-Za-z0-9_\.]+)", re.MULTILINE)
    for path in CORE.rglob("*.py"):
        for match in pattern.finditer(path.read_text(encoding="utf-8")):
            assert match.group(1).split(".")[0] in allowed, f"{path.name}: {match.group(1)}"


def test_compile_task_roundtrip_and_missing_profile_raises():
    from core import DomainPack, DomainProfile, Task, compile_task

    def classify(text):
        if "reflow" in text:
            return ("layout_reflow", ("read", "edit", "render"))
        raise ValueError(text)

    pack = DomainPack(
        name="demo",
        classifier=classify,
        profiles={"layout_reflow": DomainProfile("reflow", ("read", "edit"), ("check",))},
    )
    contract = compile_task(Task(id="t1", instruction="reflow this"), pack)
    assert contract.task_type == "layout_reflow"
    assert contract.capabilities == ("read", "edit", "render")
    assert contract.verification.required_kinds() == ("check",)

    with pytest.raises(ValueError):
        compile_task(Task(id="t2", instruction="unknown"), pack)


def test_balance_brief_budget():
    from core.intake import IntakePolicy, SourceRegistration, balance_brief

    regs = [SourceRegistration(path=Path("a.md"), sha256="x", kind="text", size=3, text="A" * 10000)]
    brief = balance_brief(regs, IntakePolicy(max_total_chars=100, max_per_source=4000))
    assert len(brief) <= 100 + len("...(brief budget reached)")
    assert brief.endswith("...(brief budget reached)")


def test_discover_tasks_prunes_and_sorts(tmp_path):
    from core import DiscoverySpec, discover_tasks

    (tmp_path / "b" / "instruction.md").parent.mkdir(parents=True)
    (tmp_path / "b" / "instruction.md").write_text("x", encoding="utf-8")
    (tmp_path / "a" / "task.toml").parent.mkdir(parents=True)
    (tmp_path / "a" / "task.toml").write_text("x", encoding="utf-8")
    hidden = tmp_path / "skipme" / "instruction.md"
    hidden.parent.mkdir(parents=True)
    hidden.write_text("x", encoding="utf-8")

    spec = DiscoverySpec(search_roots=(tmp_path,), excluded_dir_names=("skipme",))
    found = discover_tasks(spec)
    assert [c.task_id for c in found] == ["a", "b"]
    assert all("skipme" not in str(c.root) for c in found)


def test_epoch_freshness_semantics():
    from core import Certificate, Evidence, is_fresh

    assert is_fresh(Evidence(kind="check", epoch=2, passed=True), 2)
    assert not is_fresh(Evidence(kind="check", epoch=1, passed=True), 2)
    cert = Certificate(kind="immutability", artifact_ref="a", epoch=2)
    assert cert.is_fresh(2)
    assert not cert.is_fresh(3)


def test_generic_tool_abstraction():
    from core import ToolSpec, register_tool, tools_for_capability

    register_tool(ToolSpec(name="read_file", capabilities=("content.read",), description="read"))
    assert tools_for_capability("content.read")[0].name == "read_file"


def test_immutability_policy_generic():
    from core import AllowedMutation, ImmutabilityPolicy, MutationScope

    policy = ImmutabilityPolicy(allow=("slides",), deny=("theme",))
    mutation = AllowedMutation(scope=MutationScope(label="x", fields=("slides",)), policy=policy)
    assert mutation.policy.deny == ("theme",)


def test_skill_registry():
    from core import SkillSpec, get_skill, register_skill

    register_skill(SkillSpec(name="demo_skill", description="d", capabilities=("read",)))
    assert get_skill("demo_skill").capabilities == ("read",)


def test_artifact_ir_builder_registry(tmp_path):
    from core import Artifact, build_ir, register_ir_builder

    class IR:
        kind = "binary"

        def summary(self):
            return "ok"

    register_ir_builder("binary", lambda p: IR())
    artifact = Artifact(path=tmp_path / "f.bin", kind="binary")
    built = build_ir(artifact)
    assert built.summary() == "ok"
    assert artifact.ir is built
