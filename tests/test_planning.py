from agent.execution_contract import compile_execution_contract
from agent.events import EventBus, EventKind
from agent.harness import Harness
from agent.planning import plan_next
from agent.state import RunState


def test_planner_moves_from_candidate_to_certificate_to_delivery():
    contract = compile_execution_contract(None, False)
    state = RunState(execution_contract=contract)
    assert plan_next(state, contract).gaps == ("candidate_artifact",)
    state.record_change("app.py")
    decision = plan_next(state, contract)
    assert decision.stage == "verify"
    assert decision.gaps == ("file_verification|code_check",)
    state.record_evidence("code_check", "pytest passed", backend="pytest")
    assert plan_next(state, contract).stage == "deliver"


def test_planner_prioritizes_counterexample_scoped_repair():
    contract = compile_execution_contract(None, False)
    state = RunState(execution_contract=contract)
    state.unresolved_checks.add("code_check")
    decision = plan_next(state, contract)
    assert decision.stage == "repair"
    assert decision.revised
    assert decision.gaps == ("code_check",)


def test_harness_only_publishes_a_plan_when_the_decision_changes():
    harness = Harness.__new__(Harness)
    harness.state = RunState(execution_contract=compile_execution_contract(None, False))
    harness.events = EventBus()
    harness.recorder = None
    harness._last_planning_signature = None
    observed = []
    harness.events.subscribe(lambda event: observed.append(event) if event.kind == EventKind.PLANNING_DECISION else None)

    harness._publish_planning()
    harness._publish_planning()
    assert len(observed) == 1

    harness.state.record_change("app.py")
    harness._publish_planning()
    assert len(observed) == 2
    assert observed[-1].payload["stage"] == "verify"
