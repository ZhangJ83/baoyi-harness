"""Two-level compiler: generic orchestration plus a complete DomainPack.

A DomainPack bundles everything a specialization contributes -- IR builders,
intake, ontology, profiles, skills, capabilities, tool facade, transaction,
verification, and provenance policies -- so a harness assembly can obtain the
whole specialization through one object instead of implicit global state.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

from core.contract import OutputContract, TaskContract
from core.model import Task
from core.verification import VerificationContract


@dataclass
class DomainProfile:
    name: str
    capabilities: tuple = ()
    verification: tuple = ()


@dataclass
class DomainPack:
    name: str
    classifier: Callable[[str], Tuple[str, tuple]]
    profiles: Dict[str, DomainProfile] = field(default_factory=dict)
    skills: Dict[str, Any] = field(default_factory=dict)
    capabilities: tuple = ()
    ir_builders: tuple = ()          # ((kind, builder), ...)
    intake_normalizer: Optional[Callable[[Path], Any]] = None
    tool_facade: Dict[str, tuple] = field(default_factory=dict)
    transaction_policy: Any = None
    verification_policy: Optional[Callable[[str], VerificationContract]] = None
    provenance_policy: Any = None
    mutation_policy_for: Optional[Callable[[str], Any]] = None

    def classify(self, instruction: str) -> Tuple[str, tuple]:
        return self.classifier(instruction)

    def profile_for(self, task_type: str) -> Optional[DomainProfile]:
        return self.profiles.get(task_type)

    def build_source_ir(self, task_dir: Path) -> Any:
        if self.intake_normalizer is None:
            raise RuntimeError(f"domain pack {self.name!r} has no intake normalizer")
        return self.intake_normalizer(Path(task_dir))

    def register(self) -> None:
        """Register the pack's contributions into the generic core registries."""
        from core.artifact import register_ir_builder
        from core.capability import register_capability
        from core.skill import register_skill

        for kind, builder in self.ir_builders:
            register_ir_builder(kind, builder)
        for cap in self.capabilities:
            register_capability(cap)
        for spec in self.skills.values():
            register_skill(spec)


def compile_task(task: Task, domain_pack: DomainPack) -> TaskContract:
    """Compile a task into a contract, refusing to guess when classification is unknown."""
    task_type, capabilities = domain_pack.classify(task.instruction)
    profile = domain_pack.profile_for(task_type)
    if profile is None:
        raise ValueError(f"domain {domain_pack.name!r} has no profile for task type {task_type!r}")
    capabilities = tuple(dict.fromkeys(capabilities))  # dedupe, keep order
    verification = profile.verification
    if domain_pack.verification_policy is not None:
        verification = domain_pack.verification_policy(task_type).required_kinds()
    return TaskContract(
        task_type=task_type,
        capabilities=capabilities,
        profile=profile,
        output=OutputContract(path=task.output),
        verification=VerificationContract.from_kinds(verification),
        mutation=domain_pack.mutation_policy_for(task_type) if domain_pack.mutation_policy_for else None,
    )
