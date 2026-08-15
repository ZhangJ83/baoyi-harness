from agent.execution_contract import Domain, compile_execution_contract
from agent.state import RuntimePhase
from agent.task_compiler import compile_task
from agent.code_task_compiler import CodeTaskSpec


def test_generic_contract_supports_safe_edit_and_real_checks():
    contract = compile_execution_contract(None, False, CodeTaskSpec("python", "pytest", ("app.py",)))
    assert contract.domain is Domain.CODE
    assert {"edit_file", "apply_edits", "run_checks", "verify_files"}.issubset(
        contract.tools_for(RuntimePhase.PRODUCE)
    )
    assert "run_shell" not in contract.tools_for(RuntimePhase.PRODUCE)
    assert contract.finish_certificates == {"file_verification|code_check"}
    assert contract.language == "python"
    assert contract.test_runner == "pytest"


def test_ppt_contract_specializes_operation_and_stage_surface():
    spec = compile_task(
        "add a bullet on slide 2",
        {"ppt_input_deck": "tasks/demo/source.pptx"},
    )
    contract = compile_execution_contract(spec, True)
    assert contract.domain is Domain.PPT
    assert contract.operation == "append_bullet"
    assert "ppt_edit_text" in contract.tools_for(RuntimePhase.PRODUCE)
    assert contract.tools_for(RuntimePhase.VERIFY) == {"ppt_save", "ppt_check", "finish"}
