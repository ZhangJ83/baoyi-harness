import pytest

from agent.deliberation import ControllerConfig, MetaAction, choose_meta_action, plugin_gate_regret
from experiments.simulate_cegarh import run


def test_controller_trades_gain_against_cost_and_risk():
    actions = [
        MetaAction("direct", 0.6, cost=1, residual_risk=0.3, kind="direct"),
        MetaAction("verify", 0.75, cost=2, residual_risk=0.02, kind="evidence"),
    ]
    assert choose_meta_action(actions, ControllerConfig(cost_weight=0.05, risk_weight=1)).action.name == "verify"
    assert choose_meta_action(actions, ControllerConfig(cost_weight=0.5, risk_weight=0)).action.name == "direct"


def test_plugin_argmax_regret_bound_under_uniform_error():
    true = {"a": 0.4, "b": 0.5, "c": 0.1}
    estimated = {"a": 0.51, "b": 0.49, "c": 0.12}
    epsilon = max(abs(true[key] - estimated[key]) for key in true)
    # Multiclass argmax has a 2-epsilon bound; the tighter epsilon result in
    # THEORY.md applies to the binary zero-threshold gate.
    assert plugin_gate_regret(true, estimated) <= 2 * epsilon + 1e-12


def test_heterogeneous_simulation_is_deterministic_and_cegarh_wins_objective():
    config = ControllerConfig(cost_weight=0.05, risk_weight=1.0)
    first = run(7, 2000, False, config)
    second = run(7, 2000, False, config)
    assert first == second
    scores = {row.policy: row.objective for row in first}
    assert scores["cegarh"] >= max(value for key, value in scores.items() if key != "cegarh")


def test_homogeneous_controller_reduces_to_best_fixed_action():
    rows = run(7, 500, True, ControllerConfig(cost_weight=0.05, risk_weight=1.0))
    scores = {row.policy: row.objective for row in rows}
    assert scores["cegarh"] == pytest.approx(max(scores["direct"], scores["always_joint"], scores["compute_only"], scores["evidence_only"]))


def test_empty_action_set_is_rejected():
    with pytest.raises(ValueError):
        choose_meta_action([])
