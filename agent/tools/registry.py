import json
import re
import shlex
from typing import Any, Callable

from .ppt_tools import ppt_tools
from .fs_tools import fs_tools
from .code_tools import code_tools
from .lifecycle_tools import lifecycle_tools
from .tool_catalog import ToolEffect, ToolExposure, ppt_names

ToolDef = dict[str, Any]

_ALL: list[tuple[ToolDef, Callable]] = [*ppt_tools, *fs_tools, *code_tools, *lifecycle_tools]
TOOLS: list[ToolDef] = [t[0] for t in _ALL]
_PPT_NAMES = {item[0]["function"]["name"] for item in ppt_tools}
_PPT_MUTATORS = ppt_names(effect=ToolEffect.MUTATE) | ppt_names(effect=ToolEffect.COMMIT)
_PPT_CONTENT_MUTATORS = ppt_names(effect=ToolEffect.MUTATE)
_PPT_REPAIR_MUTATORS = ppt_names(effect=ToolEffect.MUTATE, repair=True)
_INDEX: dict[str, Callable] = {t[0]["function"]["name"]: t[1] for t in _ALL}
_SCHEMAS: dict[str, dict] = {t[0]["function"]["name"]: t[0]["function"]["parameters"] for t in _ALL}


def _normalize_compat_call(name: str, args: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Map only safe read-only legacy spellings to canonical tools.

    Some OpenAI-compatible models emit Claude-style ``sys_cat``/``sys_exec``
    despite receiving canonical schemas.  Arbitrary execution must not bypass
    the current phase tool surface, so only deterministic read/list commands
    are normalized here.
    """

    if name == "sys_cat":
        return "read_file", args
    if name != "sys_exec":
        return name, args
    command = args.get("command")
    if not isinstance(command, str):
        raise ValueError("sys_exec compatibility requires a string command")
    try:
        parts = shlex.split(command, posix=False)
    except ValueError as exc:
        raise ValueError("malformed sys_exec compatibility command") from exc
    if parts and parts[0].casefold() == "type" and len(parts) == 2:
        return "read_file", {"path": parts[1].strip('"')}
    if re.fullmatch(r"dir\s+/s\s+/b\s+.+", command.strip(), re.IGNORECASE):
        return "glob_files", {"pattern": "**/*", "limit": 500}
    raise ValueError(
        "unsupported sys_exec compatibility command; use a canonical tool advertised for the current phase"
    )


def _canonical_local_ppt_scope(name: str, args: dict[str, Any], harness) -> tuple[set[int], set[int]] | None:
    """Derive the closed-world slide scope for canonical local PPT facades.

    Keep this list deliberately narrow.  Compose, slide insert/delete/reorder,
    save/check, and every legacy primitive stay on their established paths.
    """
    deck = getattr(harness, "deck", None)
    if deck is None:
        return None

    requested: set[int]
    if name == "ppt_edit_text":
        operation = args.get("operation")
        if operation == "append_bullet":
            requested = {args["slide_number"]}
        elif operation == "replace":
            slide_number = args.get("slide_number")
            requested = ({slide_number} if isinstance(slide_number, int) else set(range(1, len(deck.slides) + 1)))
        elif operation == "batch_updates":
            requested = set()
            default_slide = args.get("slide_number")
            for update in args.get("updates", []):
                slide_number = update.get("slide_number", default_slide)
                if update.get("operation") == "replace" and slide_number is None:
                    requested.update(range(1, len(deck.slides) + 1))
                elif isinstance(slide_number, int):
                    requested.add(slide_number)
        else:
            return None
    elif name == "ppt_style":
        requested = {args["slide_number"]}
    elif name == "ppt_arrange" and args.get("operation") in {
        "geometry", "delete_shape", "reflow_two_columns",
    }:
        requested = {args["slide_number"]}
    else:
        return None

    # Validation errors such as an empty batch remain the tool's responsibility,
    # but the adapter still receives a closed scope and cannot widen it.
    configured = set(getattr(getattr(harness, "state", None), "ppt_allowed_slides", set()) or set())
    allowed = configured if configured else set(requested)
    return allowed, requested


def select_tools(
    task: str,
    has_deck: bool = False,
    allowed_tools: set[str] | None = None,
    phase_tools: set[str] | None = None,
) -> list[ToolDef]:
    text = task.lower()
    ppt_markers = ("ppt", "pptx", "powerpoint", "slide", "deck", "演示", "幻灯片", "排版")
    include_ppt = (
        has_deck
        or any(marker in text for marker in ppt_markers)
        or (phase_tools is not None and bool(set(phase_tools) & _PPT_NAMES))
    )
    selected = TOOLS if include_ppt else [tool for tool in TOOLS if tool["function"]["name"] not in _PPT_NAMES]
    if include_ppt:
        model_visible_ppt = ppt_names(exposure=ToolExposure.DIRECT) | ppt_names(exposure=ToolExposure.DEFERRED)
        selected = [
            tool for tool in selected
            if tool["function"]["name"] not in _PPT_NAMES
            or tool["function"]["name"] in model_visible_ppt
        ]
    return [
        tool for tool in selected
        if (not allowed_tools or tool["function"]["name"] in allowed_tools)
        and (phase_tools is None or tool["function"]["name"] in phase_tools)
    ]


def _validate(value: Any, schema: dict, path: str = "arguments") -> None:
    expected = schema.get("type")
    valid = {
        "object": lambda item: isinstance(item, dict),
        "array": lambda item: isinstance(item, list),
        "string": lambda item: isinstance(item, str),
        "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
        "number": lambda item: isinstance(item, (int, float)) and not isinstance(item, bool),
        "boolean": lambda item: isinstance(item, bool),
    }
    if expected in valid and not valid[expected](value):
        raise TypeError(f"{path} must be {expected}")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{path} must be one of {schema['enum']}")
    if expected in {"integer", "number"}:
        if "minimum" in schema and value < schema["minimum"]:
            raise ValueError(f"{path} must be >= {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            raise ValueError(f"{path} must be <= {schema['maximum']}")
    if expected == "string":
        if "minLength" in schema and len(value) < schema["minLength"]:
            raise ValueError(f"{path} must contain at least {schema['minLength']} characters")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            raise ValueError(f"{path} must contain at most {schema['maxLength']} characters")
    if expected == "object":
        for name in schema.get("required", []):
            if name not in value:
                raise ValueError(f"missing required argument: {path}.{name}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            unknown = sorted(set(value) - set(properties))
            if unknown:
                raise ValueError(f"unknown argument(s) at {path}: {', '.join(unknown)}")
        for name, item in value.items():
            if name in properties:
                _validate(item, properties[name], f"{path}.{name}")
    if expected == "array":
        if "minItems" in schema and len(value) < schema["minItems"]:
            raise ValueError(f"{path} requires at least {schema['minItems']} items")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            raise ValueError(f"{path} allows at most {schema['maxItems']} items")
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(value):
                _validate(item, item_schema, f"{path}[{index}]")


def _repair_truncated_json(text: str) -> dict | None:
    """Recover one common provider failure mode: a long JSON call truncated by
    the output cap.  Close open containers in reverse order, which preserves a
    valid prefix when the truncation happened inside a nested object/array."""
    stack: list[str] = []
    in_string = False
    escaped = False
    for char in text:
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        else:
            if char == '"':
                in_string = True
            elif char in "{[":
                stack.append(char)
            elif char in "}]":
                if stack and ((char == "}" and stack[-1] == "{") or (char == "]" and stack[-1] == "[")):
                    stack.pop()
    if in_string or not stack:
        return None
    closing = "".join("}" if char == "{" else "]" for char in reversed(stack))
    candidate = text + closing
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def dispatch(name: str, arguments_json: str, harness) -> str:
    args = None
    try:
        args = json.loads(arguments_json or "{}")
    except json.JSONDecodeError as exc:
        recovered = _repair_truncated_json(arguments_json or "")
        if recovered is not None:
            args = recovered
        else:
            raise ValueError(
                f"invalid JSON arguments at character {exc.pos}; send ONE valid JSON object. "
                "If the update list is too long, split it into several smaller tool calls."
            ) from exc
    if not isinstance(args, dict):
        raise TypeError("tool arguments must be a JSON object")
    # Argument-contract recovery: some providers emit
    # {"arguments": "{\"operation\": ...}"} instead of the inner object.
    if isinstance(args, dict) and set(args) == {"arguments"} and isinstance(args["arguments"], str):
        try:
            unwrapped = json.loads(args["arguments"])
        except json.JSONDecodeError:
            unwrapped = None
        if isinstance(unwrapped, dict):
            args = unwrapped
    requested_name = name
    name, args = _normalize_compat_call(name, args)
    fn = _INDEX.get(name)
    if fn is None:
        raise KeyError(
            f"unknown tool: {requested_name}; call one of the tools advertised for the current phase"
        )
    if requested_name != name and getattr(harness, "recorder", None):
        harness.recorder.event("deprecated_tool_alias_used", alias=requested_name, canonical=name)
    # Normalize rectangle geometry aliases before validation/dispatch. The
    # facade accepts ``h``/``width`` as spellings for ``height``/``w``, but the
    # executor functions use ``h`` as the harness parameter name, so a raw
    # ``h`` argument would collide. Rewrite it here instead.
    if isinstance(args, dict):
        if "h" in args and "height" not in args:
            args["height"] = args.pop("h")
        if "width" in args and "w" not in args:
            args["w"] = args.pop("width")
    _validate(args, _SCHEMAS[name])
    epoch_before = getattr(getattr(harness, "state", None), "mutation_epoch", None)
    deck_before = getattr(harness, "deck", None)
    slide_count_before = len(deck_before.slides) if deck_before is not None else 0

    def invoke():
        repair_candidate = name in _PPT_REPAIR_MUTATORS and bool(getattr(harness.state, "unresolved_checks", set()))
        if repair_candidate:
            # Bounded repair counts verifier-feedback *cycles*, not individual
            # mutation calls. A source-sync repair cycle legitimately rewrites
            # several surfaces before reverification; charging every successful
            # mutator would strand the cycle after its first edit. The first
            # mutation after a failed verification opens one cycle; later
            # mutations of the same cycle are free until a verifier fails again.
            if getattr(harness.state, "last_verification_failed", False):
                if harness.state.repair_attempts >= harness.state.max_repairs:
                    raise RuntimeError(f"repair budget exhausted ({harness.state.max_repairs}); stop and report unresolved defects")
                harness.state.repair_attempts += 1
                harness.state.last_verification_failed = False
                if getattr(harness, "recorder", None):
                    harness.recorder.event(
                        "repair_attempt",
                        number=harness.state.repair_attempts,
                        tool=name,
                        defect_epoch=harness.state.last_verification_epoch,
                    )
        out = fn(harness, **args)
        return out

    if name in _PPT_CONTENT_MUTATORS and getattr(harness, "deck", None) is not None:
        undo_stack = getattr(harness, "undo_stack", None)
        if undo_stack is not None:
            try:
                from io import BytesIO

                buffer = BytesIO()
                harness.deck.save(buffer)
                undo_stack.append(buffer.getvalue())
                del undo_stack[:-20]
            except Exception:
                pass

    transaction_scope = _canonical_local_ppt_scope(name, args, harness)
    if transaction_scope is None:
        out = invoke()
    else:
        from ..ppt_transaction_adapter import run_ppt_transaction

        allowed_slides, requested_slides = transaction_scope
        outcome = run_ppt_transaction(
            harness,
            allowed_slides=allowed_slides,
            requested_slides=requested_slides,
            action=lambda _deck: invoke(),
        )
        out = outcome.value
    if name in _PPT_CONTENT_MUTATORS:
        slide_number = args.get("slide_number")
        if isinstance(slide_number, int):
            harness.state.ppt_affected_slides.add(slide_number)
        deck_after = getattr(harness, "deck", None)
        slide_count_after = len(deck_after.slides) if deck_after is not None else 0
        if slide_count_after > slide_count_before:
            insert_after = args.get("insert_after") if name == "ppt_compose" else None
            if isinstance(insert_after, int):
                harness.state.ppt_affected_slides.add(insert_after + 1)
            else:
                harness.state.ppt_affected_slides.update(range(slide_count_before + 1, slide_count_after + 1))
        if (
            slide_count_after < slide_count_before
            or name == "move_slide"
            or (name == "ppt_arrange" and args.get("operation") == "move_slide")
        ):
            harness.state.ppt_affected_slides.update(range(1, slide_count_after + 1))
    # Keep the evidence contract complete even when a layout helper only
    # mutates the in-memory Presentation. Content mutators that already record
    # a more specific change are not double-counted. COMMIT tools (ppt_save) are
    # deliberately excluded: persisting the current content is a commit, not a
    # content mutation, and must not advance the mutation epoch.
    if name in _PPT_CONTENT_MUTATORS and epoch_before is not None and harness.state.mutation_epoch == epoch_before:
        harness.state.record_change(f"deck:{name}")
    if out is None:
        return ""
    return out if isinstance(out, str) else json.dumps(out, ensure_ascii=False)
