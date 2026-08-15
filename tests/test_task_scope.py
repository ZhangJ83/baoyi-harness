from __future__ import annotations

from agent.harness import Harness
from agent.state import RunState
from agent.task_scope import (
    infer_ppt_mutation_scope,
    is_scope_continuation,
    ppt_scope_is_explicit,
)


def test_infers_supported_english_slide_expressions() -> None:
    assert infer_ppt_mutation_scope("Edit slide 2 only") == frozenset({2})
    assert infer_ppt_mutation_scope("Update slides 2 and 3") == frozenset({2, 3})
    assert infer_ppt_mutation_scope("Fix pages 3, 5 & 7") == frozenset({3, 5, 7})
    assert infer_ppt_mutation_scope("Review page 4") == frozenset({4})


def test_infers_supported_chinese_page_expressions() -> None:
    assert infer_ppt_mutation_scope("修改第2页") == frozenset({2})
    assert infer_ppt_mutation_scope("只调整第 2、3 页") == frozenset({2, 3})
    assert infer_ppt_mutation_scope("修改第2页和第3页") == frozenset({2, 3})


def test_global_scope_is_explicit_but_open() -> None:
    for task in (
        "Update all slides",
        "Rewrite the entire presentation",
        "修改所有页面",
        "全局统一字体",
    ):
        assert infer_ppt_mutation_scope(task) is None
        assert ppt_scope_is_explicit(task) is True


def test_ambiguous_text_never_guesses_a_page() -> None:
    for task in (
        "Update the presentation",
        "Fix the next slide",
        "根据报告修改相关页面",
        "Q2 results for 2026",
        "edit slide zero",
    ):
        assert infer_ppt_mutation_scope(task) is None
        assert ppt_scope_is_explicit(task) is False


def test_harness_binds_inferred_scope_to_run_state() -> None:
    harness = Harness.__new__(Harness)
    harness.state = RunState()

    harness._bind_ppt_mutation_scope("修改 PPT 的第 2、3 页")

    assert harness.state.ppt_allowed_slides == {2, 3}
    assert harness.state.ppt_scope_explicit is True


def test_standalone_continuation_preserves_previous_explicit_scope() -> None:
    for continuation in ("继续", "请继续。", "continue", "CONTINUE!", "resume"):
        harness = Harness.__new__(Harness)
        harness.state = RunState(ppt_allowed_slides={2, 3}, ppt_scope_explicit=True)

        harness._bind_ppt_mutation_scope(continuation)

        assert is_scope_continuation(continuation) is True
        assert harness.state.ppt_allowed_slides == {2, 3}
        assert harness.state.ppt_scope_explicit is True


def test_new_task_resets_previous_scope_even_when_new_scope_is_ambiguous() -> None:
    harness = Harness.__new__(Harness)
    harness.state = RunState(ppt_allowed_slides={2, 3}, ppt_scope_explicit=True)

    harness._bind_ppt_mutation_scope("根据最新报告调整相关页面")

    assert harness.state.ppt_allowed_slides == set()
    assert harness.state.ppt_scope_explicit is False


def test_continuation_with_new_page_is_a_new_scope() -> None:
    harness = Harness.__new__(Harness)
    harness.state = RunState(ppt_allowed_slides={2, 3}, ppt_scope_explicit=True)

    harness._bind_ppt_mutation_scope("continue editing slide 4")

    assert is_scope_continuation("continue editing slide 4") is False
    assert harness.state.ppt_allowed_slides == {4}
    assert harness.state.ppt_scope_explicit is True
