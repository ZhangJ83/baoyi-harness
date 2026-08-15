from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from enum import Enum
import hashlib


class Status(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"


class RuntimePhase(str, Enum):
    """Coarse safety envelope; CEGAR-H chooses actions inside each phase."""

    INTAKE = "intake"
    UNDERSTAND = "understand"
    PRODUCE = "produce"
    VERIFY = "verify"
    DELIVER = "deliver"
    STOPPED = "stopped"


@dataclass
class TaskItem:
    id: str
    content: str
    status: Status = Status.PENDING
    evidence: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EvidenceRecord:
    kind: str
    summary: str
    epoch: int
    passed: bool = True
    scope: str = "workspace"
    backend: str = "harness"
    artifact_revision: int = 0


@dataclass
class RunState:
    goal: str = ""
    tasks: list[TaskItem] = field(default_factory=list)
    operational_plan: list[dict[str, str]] = field(default_factory=list)
    tool_calls: int = 0
    total_tokens: int = 0
    input_tokens: int = 0
    generated_output_tokens: int = 0
    reasoning_observed: bool = False
    last_reasoning_chars: int = 0
    reasoning_chars: int = 0
    provider_usage_authoritative: bool = True
    failures: dict[str, int] = field(default_factory=dict)
    changed_files: set[str] = field(default_factory=set)
    mutation_epoch: int = 0
    evidence: list[EvidenceRecord] = field(default_factory=list)
    final_summary: str | None = None
    budget_overrun: bool = False
    repair_attempts: int = 0
    max_repairs: int = 3
    last_verification_failed: bool = False
    last_verification_epoch: int = -1
    unresolved_checks: set[str] = field(default_factory=set)
    phase: RuntimePhase = RuntimePhase.INTAKE
    facts: dict[str, str] = field(default_factory=dict)
    open_obligations: set[str] = field(default_factory=set)
    active_artifact: str | None = None
    observation_fingerprints: set[str] = field(default_factory=set)
    observation_count: int = 0
    no_progress_streak: int = 0
    progress_epoch: int = 0
    last_meta_action: str | None = None
    last_meta_reason: str | None = None
    controller_redirects: int = 0
    content_brief: str = ""
    source_paths: set[str] = field(default_factory=set)
    task_profile: str = "edit_existing"
    task_capabilities: tuple[str, ...] = field(default_factory=tuple)
    verification_plan: tuple[str, ...] = field(default_factory=tuple)
    design_policy: str = "preserve-template; minimal-mutation"
    # Existing decks may contain unrelated historical defects.  Freeze their
    # structural baseline on open, then hold this run accountable for every
    # affected slide plus any finding that is new or measurably worse.
    ppt_existing_deck: bool = False
    ppt_baseline_captured: bool = False
    ppt_baseline_findings: dict[str, float] = field(default_factory=dict)
    ppt_affected_slides: set[int] = field(default_factory=set)
    # Optional hard boundary supplied by a task/controller.  An empty set
    # means canonical local mutations are confined to their own requested
    # slides; it never means unrestricted access.
    ppt_allowed_slides: set[int] = field(default_factory=set)
    # Distinguishes an explicitly open whole-deck scope from a task that did
    # not state any trustworthy slide scope.  Both have an empty finite set.
    ppt_scope_explicit: bool = False
    # Runtime-only executable policy. Kept out of compact persistence; the
    # Task Compiler rebuilds it deterministically on every task turn.
    execution_contract: Any = None

    def _track_ppt_scope(self, path: str) -> None:
        parts = path.split(":")
        for index, part in enumerate(parts[:-1]):
            if part == "slide":
                try:
                    self.ppt_affected_slides.add(int(parts[index + 1]))
                except ValueError:
                    pass

    def record_change(self, path: str) -> None:
        self.mutation_epoch += 1
        self.progress_epoch += 1
        self.no_progress_streak = 0
        self.changed_files.add(path)
        self._track_ppt_scope(path)

    def record_commit(self, path: str) -> None:
        """Record a persisted artifact without advancing the mutation epoch.

        Saving a deck to its contract output is a commit, not a content
        mutation: it must satisfy the finish gate's ``changed_files`` check but
        must not invalidate fresh structural/render evidence produced for the
        current content epoch.
        """
        self.no_progress_streak = 0
        self.changed_files.add(path)
        self._track_ppt_scope(path)

    def record_changes(self, paths: list[str]) -> None:
        if not paths:
            return
        self.mutation_epoch += 1
        self.progress_epoch += 1
        self.no_progress_streak = 0
        self.changed_files.update(paths)
        for path in paths:
            self._track_ppt_scope(path)

    def record_evidence(self, kind: str, summary: str, passed: bool = True, scope: str = "workspace", backend: str = "harness") -> None:
        self.evidence.append(EvidenceRecord(kind=kind, summary=summary, epoch=self.mutation_epoch, passed=passed, scope=scope, backend=backend, artifact_revision=self.mutation_epoch))
        if passed:
            self.progress_epoch += 1
            self.no_progress_streak = 0

    def record_fact(self, key: str, value: str) -> bool:
        """Persist a compact task fact and report whether it is new information."""
        normalized = value[:2000]
        if self.facts.get(key) == normalized:
            return False
        self.facts[key] = normalized
        self.progress_epoch += 1
        self.no_progress_streak = 0
        return True

    def record_observation(self, signature: str, output: str) -> bool:
        """Track semantic novelty across non-consecutive observation cycles."""
        digest = hashlib.sha256(output.encode("utf-8", errors="replace")).hexdigest()
        fingerprint = f"{signature}|{digest}"
        self.observation_count += 1
        if fingerprint in self.observation_fingerprints:
            self.no_progress_streak += 1
            return False
        self.observation_fingerprints.add(fingerprint)
        self.progress_epoch += 1
        self.no_progress_streak = 0
        return True

    def transition(self, phase: RuntimePhase) -> None:
        if self.phase != phase:
            self.phase = phase
            self.progress_epoch += 1

    def fresh_evidence(self, scope: str = "workspace") -> list[EvidenceRecord]:
        return [record for record in self.evidence if record.passed and record.epoch == self.mutation_epoch and record.scope == scope]

    def compact(self) -> str:
        lines = [f"Goal: {self.goal}", f"Task profile: {self.task_profile}", f"Capabilities: {', '.join(self.task_capabilities)}", f"Verification plan: {', '.join(self.verification_plan)}", f"Design policy: {self.design_policy}", f"Phase: {self.phase.value}", f"Tool calls: {self.tool_calls}", f"Tokens: {self.total_tokens}", f"Input tokens: {self.input_tokens}", f"Generated output tokens: {self.generated_output_tokens}", f"Reasoning signal observed: {self.reasoning_observed}", f"Reasoning characters: {self.reasoning_chars}", f"Provider usage authoritative: {self.provider_usage_authoritative}", f"Mutation epoch: {self.mutation_epoch}", f"Progress epoch: {self.progress_epoch}", f"No-progress streak: {self.no_progress_streak}"]
        lines.extend(f"- [{item.status.value}] {item.id}: {item.content}" for item in self.tasks)
        if self.operational_plan:
            lines.append(
                "Operational plan:\n"
                + "\n".join(
                    f"- [{item.get('status', 'pending')}] {item.get('id', '')}: {item.get('content', '')}"
                    for item in self.operational_plan
                )
            )
        if self.changed_files:
            lines.append("Changed files: " + ", ".join(sorted(self.changed_files)))
        if self.ppt_baseline_captured:
            lines.append(
                f"PPT structural baseline: {len(self.ppt_baseline_findings)} finding(s); "
                f"affected slides: {', '.join(map(str, sorted(self.ppt_affected_slides))) or 'none'}"
            )
        if self.evidence:
            lines.append("Recent evidence:\n" + "\n".join(f"- epoch={record.epoch} {record.kind}: {record.summary}" for record in self.evidence[-8:]))
        if self.active_artifact:
            lines.append(f"Active artifact: {self.active_artifact}")
        if self.open_obligations:
            lines.append("Open obligations: " + ", ".join(sorted(self.open_obligations)))
        if self.facts:
            lines.append("Durable facts:\n" + "\n".join(f"- {key}: {value}" for key, value in list(self.facts.items())[-12:]))
        if self.content_brief:
            lines.append("ContentIR task brief (do not reread these sources):\n" + self.content_brief[:12000])
        if self.source_paths:
            lines.append("Bound source paths: " + ", ".join(sorted(self.source_paths)))
        if self.last_meta_action:
            lines.append(f"CEGAR-H decision: {self.last_meta_action} ({self.last_meta_reason or 'no reason recorded'})")
        return "\n".join(lines)
