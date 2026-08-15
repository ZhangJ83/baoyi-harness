"""Production runtime control for CEGAR-H.

The phase is a safety envelope, not a fixed workflow.  Within that envelope
the controller uses the same interpretable meta-action objective as the
research implementation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from typing import Any
import os

from .deliberation import ControllerConfig, MetaAction, choose_meta_action
from .state import RunState, RuntimePhase
from .task_profiles import tools_for_profile
from .tools.tool_catalog import ToolEffect, ppt_names, visible_ppt_tools


OBSERVE_TOOLS = frozenset({
    "discover_workspace", "read_file", "read_many", "list_dir", "glob_files", "search_text",
    "git_status", "git_diff", *ppt_names(effect=ToolEffect.OBSERVE),
})
MUTATE_TOOLS = frozenset({
    "write_file", "edit_file", "apply_edits", "run_python", "run_shell", "new_deck",
    "add_slide", "add_two_column_slide", "add_metric_slide", "add_table_slide",
    "add_process_slide", "add_image_slide", "compose_quadrant_slide", "add_textbox", "replace_shape_text",
    "replace_text", "append_bullet", "set_text_style", "set_shape_fill", "add_textbox_to_slide", "add_flowchart",
    "set_shape_geometry", "delete_shape", "delete_slide", "move_slide",
    "set_speaker_notes", "save_deck", *ppt_names(effect=ToolEffect.MUTATE), *ppt_names(effect=ToolEffect.COMMIT),
})
VERIFY_TOOLS = frozenset({*ppt_names(effect=ToolEffect.VERIFY), "run_task_evaluator", "verify_files", "run_checks"})
TERMINAL_TOOLS = frozenset({"finish"})

GENERIC_OBSERVE_TOOLS = frozenset({
    "discover_workspace", "read_file", "read_many", "list_dir", "glob_files",
    "search_text", "git_status", "git_diff",
})
GENERIC_MUTATE_TOOLS = frozenset({"write_file", "edit_file", "apply_edits", "update_tasks"})
GENERIC_VERIFY_TOOLS = frozenset({"verify_files", "run_checks"})


def visible_generic_tools(state: RunState) -> set[str]:
    """Small, fail-closed model surface for ordinary local-agent work.

    Arbitrary shell/Python execution remains available to the explicit
    isolated benchmark adapter, but is not a default model-visible capability.
    Persistent notes and task evaluators are harness/user-owned services.
    """

    tools: set[str]
    if state.phase in {RuntimePhase.INTAKE, RuntimePhase.UNDERSTAND}:
        tools = set(GENERIC_OBSERVE_TOOLS) | {"finish"}
    elif state.phase == RuntimePhase.PRODUCE:
        tools = (
            set(GENERIC_OBSERVE_TOOLS)
            | set(GENERIC_MUTATE_TOOLS)
            | set(GENERIC_VERIFY_TOOLS)
            | {"finish"}
        )
    elif state.phase == RuntimePhase.VERIFY:
        tools = {"git_status", "git_diff", *GENERIC_VERIFY_TOOLS, "finish"}
    else:
        tools = {"finish"}
    # Arbitrary execution is an explicit benchmark escape hatch, not an
    # ordinary capability inferred from natural language.
    if os.getenv("ISOLATED_BENCHMARK", "").strip().lower() in {"1", "true", "yes", "on"}:
        tools |= {"run_python", "run_shell"}
    return tools


def canonical_call(name: str, arguments: str) -> str:
    try:
        parsed = json.loads(arguments or "{}")
        if isinstance(parsed, dict):
            for key, value in list(parsed.items()):
                if isinstance(value, str) and ("path" in key or key in {"pattern"}):
                    parsed[key] = value.replace("\\", "/").rstrip("/").lower()
        payload = json.dumps(parsed, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, json.JSONDecodeError):
        payload = arguments.strip()
    return f"{name}:{payload}"


@dataclass
class ObservationCache:
    """Per-run content replacement cache for deterministic observation calls."""

    values: dict[str, str] = field(default_factory=dict)

    def get(self, signature: str) -> str | None:
        return self.values.get(signature)

    def put(self, signature: str, value: str) -> None:
        self.values[signature] = value

    def clear_after_mutation(self) -> None:
        self.values.clear()


def bounded_tool_result(text: str, limit: int = 5000) -> str:
    """Bound model-visible context while the recorder retains the full result."""
    if len(text) <= limit:
        return text
    head = text[: limit * 3 // 4]
    tail = text[-limit // 4 :]
    digest = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:12]
    omitted = len(text) - len(head) - len(tail)
    return f"{head}\n[tool result replaced: {omitted} chars omitted, sha256={digest}]\n{tail}"


class RuntimeController:
    """Own phase transitions and online CEGAR-H recommendations."""

    def __init__(self, config: ControllerConfig | None = None):
        self.config = config or ControllerConfig(cost_weight=0.05, latency_weight=0.02, risk_weight=1.0)
        self.cache = ObservationCache()

    def decide(self, state: RunState, ppt_task: bool, contract=None, policy: str = "cegar_h") -> str:
        phase = state.phase
        actions: list[MetaAction]
        if phase == RuntimePhase.INTAKE:
            actions = [
                MetaAction("discover_scope", 0.80, cost=0.10, latency=0.05, residual_risk=0.05, kind="compute"),
                MetaAction("produce_candidate", 0.20, cost=0.20, residual_risk=0.55, kind="direct"),
            ]
        elif phase == RuntimePhase.UNDERSTAND:
            seen = min(state.observation_count, 8)
            compute_gain = max(0.05, 0.78 - 0.09 * seen)
            produce_gain = min(0.82, 0.16 + 0.09 * seen)
            if state.no_progress_streak >= 2:
                compute_gain = 0.0
                produce_gain = 0.90
            actions = [
                MetaAction("gather_missing_fact", compute_gain, cost=0.16, latency=0.12, residual_risk=0.08, kind="compute"),
                MetaAction("produce_candidate", produce_gain, cost=0.28, latency=0.20, residual_risk=max(0.08, 0.42 - 0.05 * seen), kind="direct"),
            ]
        elif phase == RuntimePhase.PRODUCE:
            if state.changed_files or state.mutation_epoch:
                actions = [
                    MetaAction("verify_current_artifact", 0.78, cost=0.16, latency=0.12, residual_risk=0.08, kind="evidence"),
                    MetaAction("continue_editing", 0.28, cost=0.24, latency=0.18, residual_risk=0.30, kind="direct"),
                ]
            else:
                actions = [
                    MetaAction("produce_candidate", 0.86, cost=0.28, latency=0.20, residual_risk=0.15, kind="direct"),
                    MetaAction("gather_missing_fact", 0.18, cost=0.16, latency=0.12, residual_risk=0.12, kind="compute"),
                ]
        elif phase == RuntimePhase.VERIFY:
            # Fresh evidence of any kind is not a finish certificate. Only a
            # passing, current-epoch record for every contract-required kind
            # may close the task; otherwise the controller buys more evidence
            # instead of locking the model out of repair tools in DELIVER.
            finish_certs = set(getattr(contract, "finish_certificates", set()) or set())
            evidence_kinds = {record.kind for record in state.fresh_evidence()}
            satisfied = finish_certs.issubset(evidence_kinds)
            if state.unresolved_checks:
                actions = [
                    MetaAction("repair_counterexample", 0.86, cost=0.25, latency=0.18, residual_risk=0.14, kind="direct"),
                    MetaAction("repeat_same_verifier", 0.10, cost=0.15, latency=0.12, residual_risk=0.34, kind="evidence"),
                ]
            elif satisfied and finish_certs:
                actions = [
                    MetaAction("finish_with_fresh_certificate", 0.92, cost=0.02, latency=0.01, residual_risk=0.03, kind="direct"),
                    MetaAction("buy_more_evidence", 0.20, cost=0.18, latency=0.15, residual_risk=0.02, kind="evidence"),
                ]
            elif state.fresh_evidence():
                # Some evidence exists but the contract is not satisfied yet.
                actions = [
                    MetaAction("buy_more_evidence", 0.84, cost=0.16, latency=0.12, residual_risk=0.08, kind="evidence"),
                    MetaAction("verify_current_artifact", 0.36, cost=0.16, latency=0.12, residual_risk=0.12, kind="evidence"),
                ]
            else:
                actions = [
                    MetaAction("verify_current_artifact", 0.84, cost=0.16, latency=0.12, residual_risk=0.08, kind="evidence"),
                    MetaAction("finish_without_certificate", 0.18, cost=0.02, residual_risk=0.70, kind="direct"),
                ]
        else:
            actions = [MetaAction("finish", 1.0, kind="direct")]

        try:
            from .controller_policies import eligible_meta_actions
            filtered = eligible_meta_actions(policy, actions)
            if filtered:
                actions = filtered
        except Exception:
            # Policy integration is an ablation control, not a correctness
            # dependency; if the policy module is unavailable the CEGAR-H
            # action table above remains the production default.
            pass

        decision = choose_meta_action(actions, self.config)
        state.last_meta_action = decision.action.name
        state.last_meta_reason = decision.reason
        self._apply_phase_recommendation(state, decision.action.name, ppt_task)
        return decision.action.name

    @staticmethod
    def _apply_phase_recommendation(state: RunState, action: str, ppt_task: bool) -> None:
        if state.phase == RuntimePhase.INTAKE and action == "discover_scope":
            return
        if state.phase == RuntimePhase.UNDERSTAND and (
            action == "produce_candidate" or (not ppt_task and state.observation_count >= 1)
        ):
            state.transition(RuntimePhase.PRODUCE)
        elif state.phase == RuntimePhase.PRODUCE and action == "verify_current_artifact":
            state.transition(RuntimePhase.VERIFY)
        elif state.phase == RuntimePhase.VERIFY and action == "finish_with_fresh_certificate":
            state.transition(RuntimePhase.DELIVER)

    def note_tool_result(self, state: RunState, name: str, arguments: str, output: str) -> bool:
        signature = canonical_call(name, arguments)
        if name in OBSERVE_TOOLS:
            novel = state.record_observation(signature, output)
            if name == "ppt_inspect" and novel:
                count = int(state.facts.get("ppt_inspect_count", "0")) + 1
                state.facts["ppt_inspect_count"] = str(count)
            if state.phase == RuntimePhase.INTAKE:
                state.transition(RuntimePhase.UNDERSTAND)
            # A batch ContentIR is the observation closure for an office task.
            # Full sources are preserved as an artifact; further broad reads
            # have lower expected value than producing the first candidate.
            if name == "read_many" and (
                state.facts.get("ppt_input_deck")
                or state.facts.get("ppt_input_candidates")
                or state.facts.get("official_evaluator_present") == "true"
            ):
                state.transition(RuntimePhase.PRODUCE)
            return novel
        if name in MUTATE_TOOLS:
            state.transition(RuntimePhase.PRODUCE)
            self.cache.clear_after_mutation()
            return True
        if name in VERIFY_TOOLS:
            state.transition(RuntimePhase.VERIFY)
            return True
        if name in TERMINAL_TOOLS:
            state.transition(RuntimePhase.DELIVER)
            return True
        return True

    @staticmethod
    def tool_names_for_phase(state: RunState, ppt_task: bool, profile=None, task: str | None = None) -> set[str] | None:
        contract = getattr(state, "execution_contract", None)
        if contract is not None:
            facade = contract.tools_for(state.phase, repairing=bool(state.unresolved_checks))
            # Observation is a bounded evidence channel for every PPT skill:
            # after one full-deck summary + one targeted shapes view, close
            # inspection and force mutate/save/check. Source-sync tasks use the
            # summary's stable shape names for set_shape_text/set_table.
            if ppt_task and int(state.facts.get("ppt_inspect_count", "0")) >= 2 and not state.unresolved_checks:
                facade.discard("ppt_inspect")
            if ppt_task and state.phase == RuntimePhase.VERIFY and state.facts.get("official_evaluator_present") == "true":
                facade.add("run_task_evaluator")
            return facade
        if not ppt_task:
            return visible_generic_tools(state)
        if task is not None:
            from .skill_contracts import visible_tools_for
            skill = state.facts.get("selected_skill", "")
            facade = visible_tools_for(skill, state.phase.value, repairing=bool(state.unresolved_checks))
            if not facade:
                facade = visible_ppt_tools(task, state.phase.value, repairing=bool(state.unresolved_checks))
            # Observation is bounded for every PPT skill. After one overview +
            # one targeted shapes view, close inspection and force
            # mutate/save/check; the overview carries stable shape names.
            if int(state.facts.get("ppt_inspect_count", "0")) >= 2 and not state.unresolved_checks:
                facade.discard("ppt_inspect")
            # Workspace observation remains available only until ContentIR
            # closes discovery; legacy PPT primitives stay registered/hidden.
            if state.phase in {RuntimePhase.INTAKE, RuntimePhase.UNDERSTAND} and not state.content_brief:
                facade |= {"discover_workspace", "read_file", "read_many"}
            if state.phase == RuntimePhase.VERIFY and state.facts.get("official_evaluator_present") == "true":
                facade.add("run_task_evaluator")
            return facade | {"finish"}
        # PPT provenance is bound deterministically by save_deck from the
        # preflight ContentIR source set.  Keeping a second, model-facing
        # bind_provenance tool caused redundant calls (and malformed empty
        # calls) without adding evidence.
        common = {"update_tasks", "remember"}
        profile_tools = tools_for_profile(profile) if profile is not None else None

        def scoped(candidates: set[str]) -> set[str]:
            if profile_tools is None:
                return candidates
            return (candidates & profile_tools) | common | {"finish"}

        if state.phase == RuntimePhase.INTAKE:
            return scoped(set(OBSERVE_TOOLS))
        if state.phase == RuntimePhase.UNDERSTAND:
            return scoped(set(OBSERVE_TOOLS) | set(MUTATE_TOOLS))
        if state.phase == RuntimePhase.PRODUCE:
            mutate = set(MUTATE_TOOLS)
            if state.content_brief:
                # Once ContentIR closes discovery, office work should use the
                # typed artifact tools. Generic shell/script calls reopen the
                # observation loop and recreate the long-script failure mode.
                mutate -= {"run_python", "run_shell", "write_file", "edit_file", "apply_edits"}
            return scoped(mutate | set(VERIFY_TOOLS) | {"open_deck", "deck_info", "shape_inventory", "finish"})
        if state.phase == RuntimePhase.VERIFY:
            repair = {"replace_shape_text", "replace_text", "append_bullet", "set_text_style", "set_shape_fill", "add_textbox_to_slide", "set_shape_geometry", "delete_shape", "delete_slide", "move_slide", "save_deck"}
            verify = {"ppt_verify"}
            if state.facts.get("official_evaluator_present") == "true":
                verify.add("run_task_evaluator")
            if not state.content_brief:
                verify = set(VERIFY_TOOLS)
            return scoped(verify | repair | {"deck_info", "shape_inventory", "finish"})
        return {"finish"}

    @staticmethod
    def recommendation_text(action: str) -> str:
        return {
            "discover_scope": "Discover the task scope once; prefer one batched observation over repeated directory reads.",
            "gather_missing_fact": "Acquire only a missing high-value fact. Do not reread unchanged resources.",
            "produce_candidate": "Information value has fallen below action value. Produce or modify the artifact now.",
            "verify_current_artifact": "The current artifact should be saved and verified with the cheapest relevant fresh evidence.",
            "repair_counterexample": "Repair only the concrete failed scope, then rerun the affected verifier once.",
            "finish_with_fresh_certificate": "Current-epoch evidence is sufficient; finish without further exploration.",
            "buy_more_evidence": "Acquire only evidence whose expected risk reduction exceeds its cost.",
            "finish": "Finish the active turn.",
        }.get(action, action)
