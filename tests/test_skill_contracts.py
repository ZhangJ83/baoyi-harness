import json

from agent.skill_contracts import contract_for, visible_tools_for
from agent.task_compiler import compile_task


def test_contract_loader_exposes_only_skill_facade():
    contract = contract_for("ppt.compose_from_slides")
    assert contract["evidence_runs"] == 6
    assert set(contract["visible_tools"]) == {
        "ppt_open", "ppt_inspect", "ppt_compose", "ppt_save", "ppt_check", "finish"
    }
    assert visible_tools_for("ppt.compose_from_slides", "produce") == set(contract["visible_tools"])
    assert visible_tools_for("ppt.compose_from_slides", "verify") == {"ppt_save", "ppt_check", "finish"}


def test_task_card_capability_overrides_keyword_noise():
    spec = compile_task(
        "完成 tasks/3-002",
        {
            "task_capability": "precise text editing",
            "task_instruction": "Change title text; inspect slide layout only if needed.",
            "ppt_input_deck": "tasks/3-002/3.pptx",
        },
        brief="diagram template layout image table",
    )
    assert spec.skill == "ppt.atomic_edit"
    assert spec.intent == "atomic_edit"


def test_complex_combined_skill_has_no_fixed_plan():
    spec = compile_task(
        "完成 tasks/Aircraft_surface-004",
        {
            "task_capability": "content editing plus overlap repair",
            "task_instruction": "Add bullet on slide 2 and resize image to avoid overlap.",
            "ppt_input_deck": "tasks/Aircraft_surface-004/Aircraft_surface.pptx",
        },
    )
    assert spec.skill == "ppt.content_and_layout"
    assert spec.plan == ()
