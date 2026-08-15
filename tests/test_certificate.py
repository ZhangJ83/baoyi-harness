from agent.certificate import missing_requirements
from agent.execution_contract import compile_execution_contract
from agent.state import RunState


def test_certificate_alternatives_accept_current_revision_code_check():
    state = RunState()
    state.record_change("app.py")
    state.record_evidence("code_check", "pytest passed", backend="pytest")
    contract = compile_execution_contract(None, False)
    assert missing_requirements(contract, state.fresh_evidence()) == []


def test_stale_certificate_does_not_satisfy_finish_requirement():
    state = RunState()
    state.record_evidence("code_check", "old")
    state.record_change("app.py")
    contract = compile_execution_contract(None, False)
    assert missing_requirements(contract, state.fresh_evidence()) == ["file_verification|code_check"]

