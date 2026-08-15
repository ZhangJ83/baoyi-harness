from agent.task_profiles import (
    CAPABILITY_TOOL_GROUPS,
    TASK_PROFILES,
    profile_for_name,
    tools_for_profile,
)


CANONICAL_PPT_TOOLS = {
    "ppt_open",
    "ppt_inspect",
    "ppt_edit_text",
    "ppt_style",
    "ppt_compose",
    "ppt_arrange",
    "ppt_save",
    "ppt_check",
}

LEGACY_PPT_TOOLS = {
    "open_deck",
    "deck_info",
    "shape_inventory",
    "replace_shape_text",
    "replace_text",
    "append_bullet",
    "set_text_style",
    "set_shape_fill",
    "new_deck",
    "add_slide",
    "add_two_column_slide",
    "add_metric_slide",
    "add_table_slide",
    "add_process_slide",
    "add_image_slide",
    "compose_quadrant_slide",
    "add_textbox",
    "add_textbox_to_slide",
    "add_flowchart",
    "set_shape_geometry",
    "delete_shape",
    "delete_slide",
    "move_slide",
    "set_speaker_notes",
    "save_deck",
    "ppt_verify",
    "ppt_quality_check",
    "render_deck",
    "inspect_rendered_deck",
    "run_task_evaluator",
}


def test_capability_catalog_exposes_only_canonical_ppt_facade():
    catalog_tools = set().union(*CAPABILITY_TOOL_GROUPS.values())

    assert CANONICAL_PPT_TOOLS <= catalog_tools
    assert catalog_tools.isdisjoint(LEGACY_PPT_TOOLS)


def test_every_profile_capability_and_verifier_has_a_tool_binding():
    names = set(CAPABILITY_TOOL_GROUPS)

    for profile in TASK_PROFILES:
        assert set(profile.capabilities) <= names
        assert set(profile.verification) <= names


def test_legacy_fallback_is_derived_without_polluting_profile_catalog():
    edit_tools = tools_for_profile(profile_for_name("edit_existing"))

    assert {"ppt_open", "ppt_inspect", "ppt_edit_text", "ppt_save", "ppt_check"} <= edit_tools
    assert {"open_deck", "shape_inventory", "replace_text", "save_deck", "ppt_verify"} <= edit_tools
    assert "replace_text" not in CAPABILITY_TOOL_GROUPS["native_edit"]

