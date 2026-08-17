"""Native Baoyi runtime composition root.

Wires the user instruction and task facts through:
  get_domain_pack("ppt") -> core.compile_task -> TaskContract ->
  TaskSpec (runtime projection) -> ExecutionContract (execution envelope)
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.compiler import compile_task as core_compile_task, DomainProfile
from core.contract import TaskContract
from core.model import Task
from domains import get_domain_pack
from agent.task_compiler import TaskSpec, compile_task as compile_legacy_spec
from agent.execution_contract import ExecutionContract, compile_execution_contract
from agent.code_task_compiler import compile_code_task


@dataclass(frozen=True)
class CompiledRuntimeTask:
    task_contract: TaskContract
    task_spec: TaskSpec  # compatibility/runtime projection
    execution_contract: ExecutionContract


def compile_runtime_task(
    instruction: str,
    facts: dict[str, Any] | None = None,
    brief: str = "",
    *,
    domain: str = "ppt",
    sandbox_root: str = "",
) -> CompiledRuntimeTask:
    """Production composition root for native Baoyi execution."""
    facts = facts or {}
    instruction_text = facts.get("task_instruction", "")
    capability = facts.get("task_capability", "")
    full_text = f"{capability}\n{instruction}\n{instruction_text}".strip() or brief
    task_id = facts.get("manifest_task_id", "") or facts.get("task_id", "") or "task"

    if domain == "ppt":
        pack = get_domain_pack("ppt")
        output = Path(facts["required_output_pptx"]) if facts.get("required_output_pptx") else None
        sources = (facts["ppt_input_deck"],) if facts.get("ppt_input_deck") else ()
        task_contract = core_compile_task(
            Task(id=task_id, instruction=full_text, sources=sources, output=output),
            pack,
        )
        task_spec = compile_legacy_spec(
            instruction,
            facts=facts,
            brief=brief,
            portable=task_contract,
        )
        execution_contract = compile_execution_contract(
            task_spec,
            ppt_task=True,
            code_spec=None,
            portable=task_contract,
        )
    else:
        # Code domain projection
        code_spec = compile_code_task(instruction, sandbox_root)
        task_spec = TaskSpec(
            task_root=str(sandbox_root or ""),
            artifact_mode="edit_existing",
            intent="code.workspace_edit",
            skill="code.workspace_edit",
        )
        execution_contract = compile_execution_contract(
            task_spec,
            ppt_task=False,
            code_spec=code_spec,
            portable=None,
        )
        from core.contract import OutputContract
        from core.verification import VerificationContract

        task_contract = TaskContract(
            task_type="code.workspace_edit",
            capabilities=("code.read", "code.edit"),
            profile=DomainProfile(name="code.workspace_edit", capabilities=("code.read", "code.edit")),
            output=OutputContract(),
            verification=VerificationContract.from_kinds(("file_verification",)),
        )

    return CompiledRuntimeTask(
        task_contract=task_contract,
        task_spec=task_spec,
        execution_contract=execution_contract,
    )
