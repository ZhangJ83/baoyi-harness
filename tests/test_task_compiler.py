from agent.task_compiler import compile_task


def test_one_line_cross_slide_request_compiles_to_compose_skill():
    spec = compile_task(
        r"完成 tasks\4._Pre-Colonial_Filipino_Culture-005",
        {
            "task_instruction": "Combine slides 2 and 3 into a new slide after slide 3 with male/female table and both images.",
            "ppt_input_deck": r"tasks\4._Pre-Colonial_Filipino_Culture-005\4._Pre-Colonial_Filipino_Culture.pptx",
        },
    )
    assert spec.skill == "ppt.compose_from_slides"
    assert spec.source_slides == (2, 3)
    assert spec.mutation_slides == (4,)
    assert "ppt_render" in spec.verification


def test_atomic_request_gets_short_plan():
    spec = compile_task(
        "add a bullet on slide 2",
        {"ppt_input_deck": r"tasks\Aircraft_surface-004\Aircraft_surface.pptx"},
    )
    assert spec.skill == "ppt.atomic_edit"
    assert len(spec.plan) == 4
    assert spec.mutation_slides == (2,)
    assert spec.operation == "append_bullet"


def test_atomic_replace_contract_is_compiled_from_instruction():
    spec = compile_task(
        r"完成 tasks\3-002",
        {
            "task_capability": "precise text editing",
            "task_instruction": "Change Lecture 3 to Lecture 1 in the presentation title.",
            "ppt_input_deck": r"tasks\3-002\3.pptx",
        },
    )
    assert spec.operation == "replace"
