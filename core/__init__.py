"""Generic Harness Core public API.

This package is domain-free by construction and by test: no file here may
mention any domain vocabulary, and no module here may import anything above it.
"""
from core.artifact import ArtifactIR, IR_BUILDERS, build_ir, register_ir_builder
from core.capability import Capability, all_capabilities, get_capability, register_capability
from core.compiler import DomainPack, DomainProfile, compile_task
from core.contract import OutputContract, TaskContract
from core.discovery import DiscoverySpec, TaskCandidate, discover_tasks
from core.intake import IntakePolicy, SourceRegistration, balance_brief, discover_sources
from core.model import Artifact, Task
from core.skill import SKILLS, SkillSpec, get_skill, register_skill
from core.tool import TOOLS, ToolSpec, all_tools, get_tool, register_tool, tools_for_capability
from core.transaction import (
    AllowedMutation,
    Baseline,
    Certificate,
    Delta,
    ImmutabilityPolicy,
    MutationScope,
    Postcondition,
    Transaction,
)
from core.verification import (
    Evidence,
    VerificationContract,
    VerificationRequirement,
    is_fresh,
)

__all__ = [
    "Artifact",
    "ArtifactIR",
    "IR_BUILDERS",
    "build_ir",
    "register_ir_builder",
    "Capability",
    "all_capabilities",
    "get_capability",
    "register_capability",
    "DomainPack",
    "DomainProfile",
    "compile_task",
    "OutputContract",
    "TaskContract",
    "DiscoverySpec",
    "TaskCandidate",
    "discover_tasks",
    "IntakePolicy",
    "SourceRegistration",
    "balance_brief",
    "discover_sources",
    "Task",
    "SKILLS",
    "SkillSpec",
    "get_skill",
    "register_skill",
    "TOOLS",
    "ToolSpec",
    "all_tools",
    "get_tool",
    "register_tool",
    "tools_for_capability",
    "AllowedMutation",
    "Baseline",
    "Certificate",
    "Delta",
    "ImmutabilityPolicy",
    "MutationScope",
    "Postcondition",
    "Transaction",
    "Evidence",
    "VerificationContract",
    "VerificationRequirement",
    "is_fresh",
]
