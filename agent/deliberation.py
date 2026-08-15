"""Interpretable cost/risk controller for harness meta-actions.

The controller intentionally exposes its assumptions.  It is a myopic index
policy, not a learned planner and not a claim of multi-step optimality.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class MetaAction:
    name: str
    expected_gain: float
    cost: float = 0.0
    latency: float = 0.0
    residual_risk: float = 0.0
    kind: str = "direct"
    requires_fresh_scope: str | None = None


@dataclass(frozen=True)
class ControllerConfig:
    cost_weight: float = 0.05
    latency_weight: float = 0.0
    risk_weight: float = 1.0
    min_margin: float = 0.0


@dataclass(frozen=True)
class Decision:
    action: MetaAction
    score: float
    runner_up_score: float
    margin: float
    reason: str


def action_score(action: MetaAction, config: ControllerConfig) -> float:
    return (
        action.expected_gain
        - config.cost_weight * action.cost
        - config.latency_weight * action.latency
        - config.risk_weight * action.residual_risk
    )


def choose_meta_action(
    actions: Iterable[MetaAction],
    config: ControllerConfig = ControllerConfig(),
) -> Decision:
    candidates = list(actions)
    if not candidates:
        raise ValueError("at least one meta-action is required")
    ranked = sorted(
        ((action_score(action, config), action) for action in candidates),
        key=lambda pair: (pair[0], pair[1].name),
        reverse=True,
    )
    score, action = ranked[0]
    runner_up = ranked[1][0] if len(ranked) > 1 else float("-inf")
    margin = score - runner_up
    if margin < config.min_margin:
        direct = [pair for pair in ranked if pair[1].kind == "direct"]
        if direct:
            score, action = direct[0]
            margin = score - runner_up
    terms = (
        f"gain={action.expected_gain:.4f}, cost_penalty={config.cost_weight * action.cost:.4f}, "
        f"latency_penalty={config.latency_weight * action.latency:.4f}, "
        f"risk_penalty={config.risk_weight * action.residual_risk:.4f}"
    )
    return Decision(action, score, runner_up, margin, terms)


def plugin_gate_regret(true_scores: dict[str, float], estimated_scores: dict[str, float]) -> float:
    """Return one-decision regret of the plug-in argmax policy."""
    if true_scores.keys() != estimated_scores.keys() or not true_scores:
        raise ValueError("true and estimated scores must share non-empty keys")
    oracle = max(true_scores, key=true_scores.get)  # type: ignore[arg-type]
    chosen = max(estimated_scores, key=estimated_scores.get)  # type: ignore[arg-type]
    return true_scores[oracle] - true_scores[chosen]

