"""Unified executable contract for generic and domain-specialized tasks."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .state import RuntimePhase
from .task_compiler import TaskSpec


class Domain(str, Enum):
    CODE = "code"
    PPT = "ppt"


@dataclass(frozen=True)
class StageSpec:
    id: str
    label: str
    phases: tuple[RuntimePhase, ...]
    tools: frozenset[str]
    required_certificates: frozenset[str] = frozenset()


@dataclass(frozen=True)
class ExecutionContract:
    domain: Domain
    capability: str
    operation: str = ""
    scope: tuple[str, ...] = ()
    stages: tuple[StageSpec, ...] = ()
    finish_certificates: frozenset[str] = frozenset()
    max_repairs: int = 1
    language: str = ""
    test_runner: str = ""
    # Static, non-loop surface supplied by the portable stack (C_static).
    task_type: str = ""
    portable_capabilities: tuple[str, ...] = ()
    mutation_policy: Any = None
    verification_kinds: tuple[str, ...] = ()

    def tools_for(self, phase: RuntimePhase, repairing: bool = False) -> set[str]:
        if phase in {RuntimePhase.DELIVER, RuntimePhase.STOPPED}:
            return {"finish"}
        visible: set[str] = set()
        for stage in self.stages:
            if phase in stage.phases:
                visible.update(stage.tools)
        # CEGAR-H repair pass: a counterexample from the verifier is only
        # actionable if the model can observe the cited surface, mutate it,
        # commit, and reverify.  Reopening the full production facade for the
        # current skill is the loop-level repair envelope, not a per-task
        # special case.
        if repairing and self.domain is Domain.PPT and phase == RuntimePhase.VERIFY:
            for stage in self.stages:
                if RuntimePhase.PRODUCE in stage.phases:
                    visible.update(stage.tools)
            visible.add("ppt_arrange")
        # Compose-capable PPT tasks are iterative: a multi-page deck gains its
        # content slides across several produce/verify passes. Locking verify to
        # only save/check forces a premature finish after the first page. Keep
        # the production facade reachable from verify for non-atomic skills.
        if (
            self.domain is Domain.PPT
            and phase == RuntimePhase.VERIFY
            and self.capability not in {"ppt.atomic_edit", "ppt.atomic_style"}
        ):
            visible.update({"ppt_compose", "ppt_edit_text", "ppt_style", "ppt_arrange", "ppt_metadata"})
        return visible | {"finish"}


def project_verification_contract(verification: Any) -> list[str]:
    """Map domain verification requirements into runtime evidence certificates."""
    if hasattr(verification, "required_kinds"):
        kinds = list(verification.required_kinds())
    elif isinstance(verification, (tuple, list, set)):
        kinds = list(verification)
    else:
        kinds = ["ppt_structural"]
    mapping = {
        "structural": "ppt_structural",
        "render": "ppt_render",
        "visual": "ppt_visual",
        "layout": "ppt_structural",
        "immutability": "ppt_structural",
        "content_grounding": "ppt_structural",
    }
    projected = [mapping.get(k, k) for k in kinds]
    if not projected:
        projected = ["ppt_structural"]
    return list(dict.fromkeys(projected))


def compile_execution_contract(
    spec: TaskSpec | None,
    ppt_task: bool,
    code_spec=None,
    portable: Any = None,
) -> ExecutionContract:
    if ppt_task:
        task_type = str(portable.task_type) if portable is not None else (spec.intent if spec else "atomic_edit")
        skill = f"ppt.{task_type}" if portable is not None else (spec.skill if spec is not None else "ppt.atomic_edit")

        # Single source for capability-to-tool-surface routing.
        from .task_profiles import PPT_OBSERVE, PPT_COMMIT, PPT_VERIFY, tools_for_skill

        skill_tools = tools_for_skill(skill)
        base = set(PPT_OBSERVE) | set(PPT_COMMIT) | set(PPT_VERIFY)
        mutate = skill_tools - base
        portable_kwargs = {}
        if portable is not None:
            portable_kwargs = {
                "task_type": portable.task_type,
                "portable_capabilities": tuple(portable.capabilities),
                "mutation_policy": portable.mutation,
                "verification_kinds": tuple(portable.verification.required_kinds()) if hasattr(portable.verification, "required_kinds") else (),
            }

        finish_certs = (
            frozenset(project_verification_contract(portable.verification))
            if portable is not None and getattr(portable, "verification", None) is not None
            else frozenset(spec.verification if spec else ("ppt_structural",))
        )

        return ExecutionContract(
            domain=Domain.PPT,
            capability=skill,
            operation=spec.operation if spec else "",
            scope=tuple(map(str, spec.mutation_slides)) if spec else (),
            stages=(
                StageSpec("understand", "定位输入与目标", (RuntimePhase.INTAKE, RuntimePhase.UNDERSTAND), frozenset(PPT_OBSERVE)),
                StageSpec("produce", "执行领域操作", (RuntimePhase.PRODUCE,), frozenset(set(PPT_OBSERVE) | mutate | set(PPT_COMMIT) | set(PPT_VERIFY))),
                StageSpec("verify", "保存并验证", (RuntimePhase.VERIFY,), frozenset(set(PPT_COMMIT) | set(PPT_VERIFY)), frozenset({"ppt_structural"})),
            ),
            finish_certificates=finish_certs,
            max_repairs=(
                1 if task_type in {"atomic_edit", "atomic_style"}
                else 8 if task_type in {
                    "template_build", "source_grounded_build",
                    "compose_from_slides", "diagram_composition",
                }
                else 6
            ),
            **portable_kwargs,
        )
    return ExecutionContract(
        domain=Domain.CODE,
        capability="code.workspace_edit",
        stages=(
            StageSpec("understand", "读取并定位代码", (RuntimePhase.INTAKE, RuntimePhase.UNDERSTAND), frozenset({"discover_workspace", "read_file", "read_many", "list_dir", "glob_files", "search_text", "git_status", "git_diff"})),
            StageSpec("produce", "执行最小文件修改", (RuntimePhase.PRODUCE,), frozenset({"read_file", "glob_files", "search_text", "write_file", "edit_file", "apply_edits", "git_status", "git_diff", "verify_files", "run_checks", "update_tasks"})),
            StageSpec("verify", "运行确定性检查", (RuntimePhase.VERIFY,), frozenset({"git_status", "git_diff", "verify_files", "run_checks"}), frozenset({"file_verification", "code_check"})),
        ),
        finish_certificates=frozenset({"file_verification|code_check"}),
        scope=tuple(getattr(code_spec, "target_paths", ()) or ()),
        language=getattr(code_spec, "language", "") if code_spec else "",
        test_runner=getattr(code_spec, "runner", "") if code_spec else "",
    )


def resolve_capability_bindings(contract: ExecutionContract, adapter_name: str = "claude_code") -> dict:
    """Static, non-loop H2 binding: portable capabilities -> concrete vendor tools.

    Loop behavior is untouched; this function only *declares* the binding.
    """
    from adapters.implementations import ResolutionContext, resolve_primary

    context = {
        "claude_code": ResolutionContext("claude_code", "windows"),
        "codex": ResolutionContext("codex", "linux"),
        "opencode": ResolutionContext("opencode", "windows"),
        "workbuddy": ResolutionContext("workbuddy", "any"),
    }[adapter_name]
    return {cap: resolve_primary(cap, context).tool for cap in contract.portable_capabilities}
