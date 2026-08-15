import json
from unittest.mock import patch

from agent.runtime import RuntimeController, bounded_tool_result, canonical_call
from agent.state import RunState, RuntimePhase


def test_generic_tool_surface_is_small_and_unsafe_exec_is_explicit():
    controller = RuntimeController()
    produce = RunState(phase=RuntimePhase.PRODUCE)
    with patch.dict("os.environ", {}, clear=True):
        names = controller.tool_names_for_phase(produce, ppt_task=False, task="edit the file")
    assert {"write_file", "edit_file", "apply_edits", "finish"}.issubset(names)
    assert "verify_files" in names
    assert "run_python" not in names
    assert "run_shell" not in names
    assert "remember" not in names
    assert "run_task_evaluator" not in names

    with patch.dict("os.environ", {"ISOLATED_BENCHMARK": "1"}, clear=False):
        isolated = controller.tool_names_for_phase(produce, ppt_task=False, task="run the tests")
    assert {"run_python", "run_shell"}.issubset(isolated)

    verify = RunState(phase=RuntimePhase.VERIFY)
    verify_names = controller.tool_names_for_phase(verify, ppt_task=False, task="verify the file")
    assert "verify_files" in verify_names


def test_canonical_call_normalizes_paths_and_key_order():
    a = canonical_call("read_file", json.dumps({"path": "Tasks\\Demo\\instruction.md", "max_chars": 10}))
    b = canonical_call("read_file", json.dumps({"max_chars": 10, "path": "tasks/demo/instruction.md"}))
    assert a == b


def test_online_cegarh_moves_from_observation_to_production_when_information_value_falls():
    state = RunState(phase=RuntimePhase.UNDERSTAND)
    controller = RuntimeController()
    for index in range(8):
        state.record_observation(f"read:{index}", f"fact {index}")
    assert controller.decide(state, ppt_task=True) == "produce_candidate"
    assert state.phase == RuntimePhase.PRODUCE
    assert state.last_meta_reason


def test_repeated_observation_is_semantically_detected_across_calls():
    state = RunState(phase=RuntimePhase.UNDERSTAND)
    controller = RuntimeController()
    assert controller.note_tool_result(state, "read_file", '{"path":"a.md"}', "same")
    assert not controller.note_tool_result(state, "read_file", '{"path":"a.md"}', "same")
    assert not controller.note_tool_result(state, "read_file", '{"path":"a.md"}', "same")
    assert state.no_progress_streak == 2
    assert controller.decide(state, ppt_task=True) == "produce_candidate"
    assert state.phase == RuntimePhase.PRODUCE


def test_phase_tool_exposure_prevents_exploration_after_production():
    controller = RuntimeController()
    state = RunState(phase=RuntimePhase.PRODUCE)
    names = controller.tool_names_for_phase(state, ppt_task=True)
    assert names is not None
    assert "save_deck" in names
    assert "ppt_verify" in names
    assert "list_dir" not in names
    assert "glob_files" not in names


def test_model_visible_tool_result_is_bounded_and_auditable():
    text = "a" * 20000
    visible = bounded_tool_result(text, limit=1000)
    assert len(visible) < 1300
    assert "tool result replaced" in visible
    assert "sha256=" in visible


def test_read_many_closes_observation_and_moves_to_produce():
    state = RunState(goal="create a PPT")
    state.record_fact("ppt_input_deck", "tasks/demo/input.pptx")
    controller = RuntimeController()
    controller.note_tool_result(state, "read_many", '{"paths":["a.md","b.xlsx"]}', "brief")

    assert state.phase == RuntimePhase.PRODUCE
    names = controller.tool_names_for_phase(state, ppt_task=True)
    assert names is not None
    assert "read_many" not in names
    assert "run_python" in names


def test_markdown_only_read_many_does_not_close_unbound_ppt_discovery():
    state = RunState(goal="complete the benchmark")
    controller = RuntimeController()
    controller.note_tool_result(
        state,
        "read_many",
        '{"paths":["README.md","RUN_PROTOCOL.md"]}',
        "documentation only",
    )
    assert state.phase == RuntimePhase.UNDERSTAND


def test_content_ir_production_prefers_typed_office_tools_over_ad_hoc_scripts():
    state = RunState(phase=RuntimePhase.PRODUCE, content_brief="authoritative brief")
    names = RuntimeController().tool_names_for_phase(state, ppt_task=True)
    assert names is not None
    assert "compose_quadrant_slide" in names
    assert "run_python" not in names
    assert "run_shell" not in names
    assert "bind_provenance" not in names


def test_content_ir_verification_leaves_rendering_to_finish_lifecycle():
    state = RunState(phase=RuntimePhase.VERIFY, content_brief="authoritative brief")
    names = RuntimeController().tool_names_for_phase(state, ppt_task=True)
    assert names is not None
    assert "ppt_verify" in names
    assert "finish" in names
    assert "render_deck" not in names
    assert "inspect_rendered_deck" not in names


def test_model_visible_ppt_facade_is_small_and_intent_routed():
    controller = RuntimeController()
    text_state = RunState(phase=RuntimePhase.PRODUCE, content_brief="ready")
    text_names = controller.tool_names_for_phase(text_state, True, task="把第二页标题文字从旧标题替换为新标题")
    assert text_names == {"ppt_open", "ppt_inspect", "ppt_edit_text", "ppt_save", "ppt_check", "finish"}
    verify_state = RunState(phase=RuntimePhase.VERIFY, content_brief="ready")
    verify_names = controller.tool_names_for_phase(verify_state, True, task="把第二页标题文字从旧标题替换为新标题")
    assert verify_names == {"ppt_save", "ppt_check", "finish"}


def test_ppt_intent_routing_uses_actions_not_artifact_nouns():
    controller = RuntimeController()
    state = RunState(phase=RuntimePhase.PRODUCE, content_brief="ready")

    style = controller.tool_names_for_phase(
        state, True, task="Change the presentation title font size to 48pt."
    )
    assert "ppt_style" in style
    assert "ppt_compose" not in style
    assert "ppt_edit_text" not in style

    textbox = controller.tool_names_for_phase(
        state, True, task="On slide 2, create a text box with the phrase Important Note."
    )
    assert "ppt_compose" in textbox
    assert "ppt_edit_text" not in textbox

    deliver = RunState(phase=RuntimePhase.DELIVER, content_brief="ready")
    assert controller.tool_names_for_phase(deliver, True, task="Create a presentation") == {"finish"}


def test_atomic_skill_closes_inspection_after_two_novel_observations():
    controller = RuntimeController()
    state = RunState(phase=RuntimePhase.PRODUCE, content_brief="ready")
    state.record_fact("selected_skill", "ppt.atomic_edit")
    controller.note_tool_result(state, "ppt_inspect", '{"detail":"summary"}', "deck summary")
    controller.note_tool_result(state, "ppt_inspect", '{"slide_number":2,"detail":"shapes"}', "target shapes")
    names = controller.tool_names_for_phase(state, True, task="完成 tasks/3-003")
    assert "ppt_inspect" not in names
    assert {"ppt_edit_text", "ppt_save", "ppt_check", "finish"}.issubset(names)
