"""Test architectural control authority.

Verifies:
1. Native composition root (runner.compile_runtime_task) executes the chain:
   User Task -> DomainPack("ppt") -> core.compile_task -> TaskContract ->
   TaskSpec (projection) -> ExecutionContract (execution envelope).
2. TaskContract is the single semantic source of truth for runtime execution.
3. DomainPack changes directly propagate to production ExecutionContract.
"""
from __future__ import annotations

import pytest

from core import Task, TaskContract
from core.compiler import DomainProfile
from domains import get_domain_pack
from runner import compile_runtime_task, CompiledRuntimeTask
from agent.execution_contract import project_verification_contract


def test_native_composition_root_wires_task_contract_to_runtime():
    """Verify runtime compiler outputs semantic contract originating from DomainPack."""
    compiled = compile_runtime_task(
        "change the title font size to 48pt",
        facts={},
    )
    assert isinstance(compiled, CompiledRuntimeTask)
    assert compiled.task_contract.task_type == "atomic_style"
    assert compiled.task_spec.skill == "ppt.atomic_style"
    assert compiled.task_spec.intent == "atomic_style"
    assert (
        compiled.execution_contract.task_type
        == compiled.task_contract.task_type
    )
    assert (
        compiled.execution_contract.portable_capabilities
        == compiled.task_contract.capabilities
    )
    assert (
        compiled.execution_contract.mutation_policy
        == compiled.task_contract.mutation
    )
    assert (
        compiled.execution_contract.finish_certificates
        == frozenset(project_verification_contract(compiled.task_contract.verification))
    )


def test_complex_task_contract_drives_execution_contract():
    """Verify compose / template build derives proper capabilities, repairs, and certificates."""
    compiled = compile_runtime_task(
        "create a 2-page executive summary template with mindmap structure",
        facts={},
    )
    assert compiled.task_contract.task_type == "template_build"
    assert compiled.task_spec.skill == "ppt.template_build"
    assert compiled.execution_contract.capability == "ppt.template_build"
    assert compiled.execution_contract.max_repairs == 8
    assert "ppt_render" in compiled.execution_contract.finish_certificates
    assert "ppt_visual" in compiled.execution_contract.finish_certificates


def test_domain_pack_authority_propagation(monkeypatch):
    """Negative / authority test: mutating DomainPack classification directly alters ExecutionContract."""
    pack = get_domain_pack("ppt")
    original_classifier = pack.classifier

    # Force classifier to map instruction to diagram_composition
    def fake_classifier(instruction: str):
        return ("diagram_composition", ("ppt.read_structure", "ppt.mutate_slide"))

    monkeypatch.setattr(pack, "classifier", fake_classifier)

    compiled = compile_runtime_task(
        "change the title font size to 48pt",
        facts={},
    )
    assert compiled.task_contract.task_type == "diagram_composition"
    assert compiled.task_spec.skill == "ppt.diagram_composition"
    assert compiled.execution_contract.task_type == "diagram_composition"
    assert compiled.execution_contract.capability == "ppt.diagram_composition"
    assert compiled.execution_contract.portable_capabilities == ("ppt.read_structure", "ppt.mutate_slide")
