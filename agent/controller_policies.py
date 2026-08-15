"""Executable intervention policies for the preregistered controller ablation."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Iterable

from .deliberation import MetaAction
from .tools.tool_catalog import ToolEffect, ppt_names

POLICY_NAMES = ("direct", "always_verify", "evidence_only", "cegar_h")
VERIFY_TOOLS = frozenset(ppt_names(effect=ToolEffect.VERIFY))
MUTATION_TOOLS = frozenset(ppt_names(effect=ToolEffect.MUTATE))


@dataclass(frozen=True)
class PolicySpec:
    name: str
    allowed_action_kinds: frozenset[str]
    verify_after_every_mutation: bool
    terminal_verification_only: bool
    adaptive_generation_compute: bool
    max_model_steps: int


POLICIES = {
    "direct": PolicySpec("direct", frozenset({"direct"}), False, True, False, 25),
    "always_verify": PolicySpec("always_verify", frozenset({"direct", "evidence"}), True, False, False, 25),
    "evidence_only": PolicySpec("evidence_only", frozenset({"direct", "evidence"}), False, False, False, 25),
    "cegar_h": PolicySpec("cegar_h", frozenset({"direct", "evidence", "compute", "joint"}), False, False, True, 50),
}


def resolve_policy(name: str) -> PolicySpec:
    try:
        return POLICIES[name]
    except KeyError as exc:
        raise ValueError(f"unknown controller policy: {name}") from exc


def eligible_meta_actions(policy: str, actions: Iterable[MetaAction]) -> list[MetaAction]:
    spec = resolve_policy(policy)
    return [action for action in actions if action.kind in spec.allowed_action_kinds]


def policy_instruction(name: str) -> str:
    resolve_policy(name)
    return {
        "direct": "Use the fixed generation baseline. Make content mutations before starting a single terminal verification phase; after verification starts, do not mutate content again.",
        "always_verify": "After each material content mutation, save the deck and obtain fresh structural verification, rendered PDF/PNGs, and pixel inspection before the next material mutation.",
        "evidence_only": "Use the fixed generation baseline. You may choose verification adaptively, but do not request extra compute or joint compute-plus-evidence actions.",
        "cegar_h": "Adaptively allocate generation steps and fresh evidence within the common token/tool/time caps. Any mutation invalidates prior evidence; re-verify the affected artifact before finishing.",
    }[name]


class PolicyGuard:
    """Enforce observable tool-order invariants without judging model quality."""

    def __init__(self, policy: str):
        self.spec = resolve_policy(policy)
        self.verification_started = False
        self.events: list[str] = []

    def before_tool(self, name: str, state) -> None:
        if name in MUTATION_TOOLS:
            if self.spec.terminal_verification_only and self.verification_started:
                raise RuntimeError("direct policy forbids mutation after terminal verification starts")
            evidence_kinds = {record.kind for record in state.fresh_evidence()}
            required = {"ppt_structural", "ppt_render", "ppt_visual"}
            if self.spec.verify_after_every_mutation and state.mutation_epoch > 0 and not required.issubset(evidence_kinds):
                raise RuntimeError("always_verify policy requires fresh structural, render, and pixel evidence before the next mutation")
        if name in VERIFY_TOOLS:
            self.verification_started = True
        self.events.append(name)

    def manifest(self) -> dict:
        return {
            "policy": self.spec.name,
            "policy_runtime_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "events": list(self.events),
            "verification_started": self.verification_started,
            "adaptive_generation_compute": self.spec.adaptive_generation_compute,
            "max_model_steps": self.spec.max_model_steps,
        }
