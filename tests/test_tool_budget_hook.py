import json

import pytest

from agent.tool_budget_hook import process_event


def event(tool_use_id, tool_name="Bash"):
    return {
        "hook_event_name": "PreToolUse",
        "tool_use_id": tool_use_id,
        "tool_name": tool_name,
        "tool_input": {"command": "echo ok"},
    }


def test_hook_allows_up_to_cap_then_denies_before_next_tool(tmp_path):
    state = tmp_path / "state.json"
    assert process_event(event("a"), state_path=state, max_tool_calls=2) is None
    assert process_event(event("b"), state_path=state, max_tool_calls=2) is None
    denied = process_event(event("c"), state_path=state, max_tool_calls=2)
    assert denied["hookSpecificOutput"]["permissionDecision"] == "deny"
    saved = json.loads(state.read_text(encoding="utf-8"))
    assert [row["tool_use_id"] for row in saved["allowed"]] == ["a", "b"]
    assert [row["tool_use_id"] for row in saved["denied"]] == ["c"]


def test_hook_deduplicates_replayed_tool_id(tmp_path):
    state = tmp_path / "state.json"
    assert process_event(event("same"), state_path=state, max_tool_calls=1) is None
    assert process_event(event("same"), state_path=state, max_tool_calls=1) is None
    saved = json.loads(state.read_text(encoding="utf-8"))
    assert len(saved["allowed"]) == 1
    assert saved["denied"] == []


def test_hook_rejects_unidentifiable_calls(tmp_path):
    with pytest.raises(ValueError, match="tool_use_id"):
        process_event({"tool_name": "Bash"}, state_path=tmp_path / "state.json", max_tool_calls=1)


def test_hook_rejects_nonpositive_cap(tmp_path):
    with pytest.raises(ValueError, match="positive"):
        process_event(event("a"), state_path=tmp_path / "state.json", max_tool_calls=0)
