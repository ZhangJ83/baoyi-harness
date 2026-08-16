"""Single source of truth for PPT tool effects and model exposure.

The executor keeps fine-grained operations for compatibility and tests.  The
model sees only the small canonical facade selected for the current intent and
lifecycle phase.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ToolEffect(str, Enum):
    OBSERVE = "observe"
    MUTATE = "mutate"
    COMMIT = "commit"
    VERIFY = "verify"


class ToolExposure(str, Enum):
    DIRECT = "direct"
    DEFERRED = "deferred"
    HIDDEN = "hidden"


@dataclass(frozen=True)
class ToolSpec:
    name: str
    effect: ToolEffect
    exposure: ToolExposure = ToolExposure.DIRECT
    repair: bool = False
    search_hint: str = ""


_PUBLIC = (
    ToolSpec("ppt_open", ToolEffect.OBSERVE, search_hint="open an existing PowerPoint and preserve the original"),
    ToolSpec("ppt_inspect", ToolEffect.OBSERVE, search_hint="inspect slide summary or editable shapes once"),
    ToolSpec("ppt_edit_text", ToolEffect.MUTATE, repair=True, search_hint="replace text, rewrite a whole text shape, rewrite a whole table, or append a same-level bullet preserving style"),
    ToolSpec("ppt_metadata", ToolEffect.MUTATE, repair=True, search_hint="set shape descr metadata for provenance and source binding"),
    ToolSpec("ppt_notes", ToolEffect.MUTATE, repair=True, search_hint="set speaker-notes/backstage text for one slide"),
    ToolSpec("ppt_style", ToolEffect.MUTATE, repair=True, search_hint="change font size color bold or shape fill"),
    ToolSpec("ppt_compose", ToolEffect.MUTATE, search_hint="create a cover slide layout table quadrant diagram or element"),
    ToolSpec("ppt_arrange", ToolEffect.MUTATE, ToolExposure.DEFERRED, repair=True, search_hint="move resize reorder or delete a specific slide shape"),
    ToolSpec("ppt_save", ToolEffect.COMMIT, search_hint="save the current deck to the task output"),
    ToolSpec("ppt_check", ToolEffect.VERIFY, search_hint="run current-revision structural and task-native checks"),
)

_LEGACY_OBSERVE = {"open_deck", "deck_info", "shape_inventory"}
_LEGACY_MUTATE = {
    "new_deck", "add_slide", "add_two_column_slide", "compose_quadrant_slide", "add_metric_slide",
    "add_table_slide", "add_process_slide", "add_image_slide", "add_textbox", "replace_shape_text",
    "replace_text", "append_bullet", "set_text_style", "set_shape_fill", "add_textbox_to_slide",
    "add_flowchart", "set_shape_geometry", "delete_shape", "delete_slide", "move_slide",
    "set_speaker_notes",
}
_LEGACY_COMMIT = {"save_deck"}
_LEGACY_REPAIR = {
    "replace_shape_text", "replace_text", "append_bullet", "set_text_style", "set_shape_fill",
    "add_textbox_to_slide", "set_shape_geometry", "delete_shape", "delete_slide", "move_slide",
}
_LEGACY_VERIFY = {"ppt_verify", "ppt_quality_check", "render_deck", "inspect_rendered_deck"}

PPT_SPECS: dict[str, ToolSpec] = {spec.name: spec for spec in _PUBLIC}
for _name in sorted(_LEGACY_OBSERVE):
    PPT_SPECS[_name] = ToolSpec(_name, ToolEffect.OBSERVE, ToolExposure.HIDDEN)
for _name in sorted(_LEGACY_MUTATE):
    PPT_SPECS[_name] = ToolSpec(_name, ToolEffect.MUTATE, ToolExposure.HIDDEN, _name in _LEGACY_REPAIR)
for _name in sorted(_LEGACY_COMMIT):
    PPT_SPECS[_name] = ToolSpec(_name, ToolEffect.COMMIT, ToolExposure.HIDDEN)
for _name in sorted(_LEGACY_VERIFY):
    PPT_SPECS[_name] = ToolSpec(_name, ToolEffect.VERIFY, ToolExposure.HIDDEN)

GENERIC_SPECS: dict[str, ToolSpec] = {
    spec.name: spec for spec in (
        ToolSpec("discover_workspace", ToolEffect.OBSERVE),
        ToolSpec("read_file", ToolEffect.OBSERVE),
        ToolSpec("read_many", ToolEffect.OBSERVE),
        ToolSpec("list_dir", ToolEffect.OBSERVE),
        ToolSpec("glob_files", ToolEffect.OBSERVE),
        ToolSpec("search_text", ToolEffect.OBSERVE),
        ToolSpec("git_status", ToolEffect.OBSERVE),
        ToolSpec("git_diff", ToolEffect.OBSERVE),
        ToolSpec("write_file", ToolEffect.MUTATE),
        ToolSpec("edit_file", ToolEffect.MUTATE),
        ToolSpec("apply_edits", ToolEffect.MUTATE),
        ToolSpec("update_tasks", ToolEffect.MUTATE),
        ToolSpec("verify_files", ToolEffect.VERIFY),
        ToolSpec("run_checks", ToolEffect.VERIFY),
        ToolSpec("run_python", ToolEffect.MUTATE, ToolExposure.HIDDEN),
        ToolSpec("run_shell", ToolEffect.MUTATE, ToolExposure.HIDDEN),
        ToolSpec("remember", ToolEffect.MUTATE, ToolExposure.HIDDEN),
        ToolSpec("run_task_evaluator", ToolEffect.VERIFY, ToolExposure.HIDDEN),
    )
}

TOOL_SPECS = {**GENERIC_SPECS, **PPT_SPECS}


def tool_names(*, effect: ToolEffect | None = None, exposure: ToolExposure | None = None) -> set[str]:
    return {
        name for name, spec in TOOL_SPECS.items()
        if (effect is None or spec.effect is effect)
        and (exposure is None or spec.exposure is exposure)
    }


def specialize_tools(tools: list[dict], contract) -> list[dict]:
    """Project an ExecutionContract into model-visible JSON schemas."""
    import copy

    operation = getattr(contract, "operation", "") if contract is not None else ""
    runner = getattr(contract, "test_runner", "") if contract is not None else ""
    if not operation and not runner:
        return tools
    result = copy.deepcopy(tools)
    for tool in result:
        fn = tool.get("function", {})
        properties = fn.get("parameters", {}).get("properties", {})
        if fn.get("name") == "ppt_edit_text" and operation and "operation" in properties:
            properties["operation"]["enum"] = [operation]
            properties["operation"]["description"] = f"ExecutionContract requires {operation!r}."
        if fn.get("name") == "run_checks" and runner and "runner" in properties:
            properties["runner"]["enum"] = [runner]
            properties["runner"]["description"] = f"Repository preflight selected {runner!r}."
    return result


def ppt_names(*, effect: ToolEffect | None = None, exposure: ToolExposure | None = None, repair: bool | None = None) -> set[str]:
    return {
        name for name, spec in PPT_SPECS.items()
        if (effect is None or spec.effect is effect)
        and (exposure is None or spec.exposure is exposure)
        and (repair is None or spec.repair is repair)
    }


def infer_ppt_intents(task: str) -> set[str]:
    """Infer a small set of semantic PPT mutations from the user action.

    Routing is action-first.  Artifact nouns such as ``presentation`` or
    ``text`` are not intents by themselves; otherwise an instruction like
    "change the presentation title font size" exposes both compose and text
    editing even though it is a pure style operation.
    """
    text = task.casefold()
    intents: set[str] = set()

    style_cues = (
        "font", "typeface", "font size", "pt", "color", "colour", "fill",
        "bold", "italic", "style", "字体", "字号", "颜色", "填充", "加粗", "斜体", "样式",
    )
    arrange_cues = (
        "layout", "overlap", "resize", "move", "reflow", "two-column",
        "two column", "position", "align", "spacing", "排版", "重叠", "缩小",
        "移动", "双栏", "两栏", "位置", "对齐", "间距",
    )
    compose_cues = (
        "flowchart", "diagram", "quadrant", "table", "metric", "textbox",
        "text box", "new slide", "insert slide", "combine", "merge",
        "流程图", "图示", "四象限", "表格", "文本框", "新幻灯片", "插入一页",
        "合并", "整合", "制作", "绘制", "创建", "两页",
    )
    create_artifact_cues = (
        "create deck", "generate deck", "new deck", "create presentation",
        "generate presentation", "build presentation", "create a deck",
        "make a deck", "build a deck", "two-page deck",
        "制作演示文稿", "生成演示文稿", "创建演示文稿", "新建演示文稿", "生成ppt", "制作ppt",
    )
    text_cues = (
        "replace", "substitute", "rename", "change the word", "change text",
        "edit text", "add bullet", "append bullet", "bullet point", "lecture number",
        "update the deck", "sync", "替换", "更名", "改文字", "修改文字", "文案",
        "修改标题", "更改标题", "新增项目符号", "添加项目符号", "项目符号", "同步",
        "更新这份", "更新演示",
    )

    if any(word in text for word in style_cues):
        intents.add("style")
    if any(word in text for word in arrange_cues):
        intents.add("arrange")
    if any(word in text for word in compose_cues) or any(word in text for word in create_artifact_cues):
        intents.add("compose")
    if any(word in text for word in text_cues):
        intents.add("text")
    return intents


def visible_ppt_tools(task: str, phase: str, *, repairing: bool = False) -> set[str]:
    if phase in {"intake", "understand"}:
        return {"ppt_open", "ppt_inspect"}
    if phase in {"deliver", "stopped"}:
        return set()
    if phase == "verify" and not repairing:
        return {"ppt_check", "ppt_save"}
    intents = infer_ppt_intents(task)
    names = {"ppt_open", "ppt_inspect", "ppt_save", "ppt_check"}
    if "text" in intents:
        names.add("ppt_edit_text")
    if "style" in intents:
        names.add("ppt_style")
    if "compose" in intents:
        names.add("ppt_compose")
    if "arrange" in intents or repairing:
        names.add("ppt_arrange")
    return names
