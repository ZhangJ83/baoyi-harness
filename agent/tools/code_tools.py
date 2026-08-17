"""Code-focused tools (aliases over the fs sandbox) — kept for interview clarity."""
from typing import Any

from .. import memory
from ..state import Status, TaskItem


def _make(name, description, params, required, fn):
    return (
        {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {"type": "object", "properties": params, "required": required},
            },
        },
        fn,
    )


def _note(h, text: str):
    memory.append_note(text)
    return "note appended to session memory."


def _finish(h, summary: str):
    if not summary.strip():
        raise ValueError("finish summary cannot be empty")
    # Action tasks may not be completed by an empty finish: a task that asks
    # for a mutation must show changed files / a saved final artifact / fresh
    # verification evidence. Read-only or question-answering turns remain free.
    current_task = getattr(h, "current_task", "")
    read_only_task = "do not modify" in current_task.lower() or "read-only" in current_task.lower()
    if current_task and not read_only_task and not getattr(h, "_done", None):
        try:
            if h._requires_action(current_task) and not h._has_completion_evidence(current_task):
                raise ValueError(
                    "cannot finish: this action task has no completed mutation, saved artifact, "
                    "or fresh verification evidence yet. Perform the required change, save it, "
                    "and rerun the affected check before finishing."
                )
        except AttributeError:
            pass
    if h.state.changed_files and not h.state.fresh_evidence():
        raise ValueError(f"cannot finish: no passing verification evidence for current mutation epoch {h.state.mutation_epoch}")
    ppt_changed = any(path.startswith("deck:") or path.lower().endswith(".pptx") for path in h.state.changed_files)
    if ppt_changed:
        evidence_kinds = {record.kind for record in h.state.fresh_evidence()}
        if "ppt_structural" not in evidence_kinds:
            raise ValueError("cannot finish PPT task: fresh ppt_structural evidence is required after the last mutation")
        if getattr(h.state, "verification_contract_terms", None) or h.state.facts.get("verification_contract_terms"):
            from .ppt_tools import _verify_contract
            contract_passed, contract_report = _verify_contract(h)
            if not contract_passed:
                raise ValueError(
                    "cannot finish PPT task: the task-local verification contract gate failed. "
                    "Repair only the cited missing/forbidden terms, save, run ppt_check, then finish.\n\n"
                    + contract_report
                )
        if getattr(h.state, "unresolved_checks", set()):
            raise ValueError("cannot finish PPT task: unresolved verification defects: " + ", ".join(sorted(h.state.unresolved_checks)))
        recorder = getattr(h, "recorder", None)
        artifacts = getattr(recorder, "manifest", {}).get("artifacts", []) if recorder else []
        final_rows = [row for row in artifacts if row.get("role") == "final-pptx"]
        if not final_rows:
            # A model may compose a valid deck but forget the explicit save.
            # finish owns persistence + rendering lifecycle, so auto-save the
            # in-memory deck to the contract output instead of stranding a
            # valid artifact behind a "no saved file" error.
            from .ppt_tools import _save
            try:
                _save(h, h.state.facts.get("required_output_pptx"))
                artifacts = getattr(recorder, "manifest", {}).get("artifacts", []) if recorder else []
                final_rows = [row for row in artifacts if row.get("role") == "final-pptx"]
            except Exception:
                final_rows = []
        if not final_rows:
            raise ValueError(
                "cannot finish PPT task: this run has no saved final-pptx artifact; "
                "call save_deck for the required output path, then verify and finish"
            )
        # Open-ended decks have no task-local contract/evaluator. Enforce the
        # generic completeness contract before finish so sparse pages cannot
        # be delivered as finished work.
        if not h.state.facts.get("verification_contract_terms") and h.state.facts.get("official_evaluator_present") != "true":
            from .ppt_tools import _deck_completeness_gate
            gap = _deck_completeness_gate(h)
            if gap:
                raise ValueError("cannot finish PPT task: content completeness gate failed. " + gap)
        # Generic non-loop immutability gate derived from trajectory evidence:
        # for localized edits, the saved deck may only change declared slides.
        # Global-edit tasks have no declared slide scope and skip this check.
        allowed = set(getattr(h.state, "ppt_allowed_slides", set()) or set())
        if allowed and final_rows:
            input_rel = h.state.facts.get("ppt_input_deck", "")
            if input_rel:
                from pathlib import Path as _Path
                from .. import config as _config
                from domains.ppt.transaction import diff_decks

                input_path = _Path(_config.sandbox_root()) / input_rel
                final_path = _Path(final_rows[-1]["path"])
                if input_path.is_file() and final_path.is_file():
                    try:
                        delta = diff_decks(input_path, final_path)
                    except Exception:
                        delta = None
                    if delta is not None:
                        shape_targets = getattr(h.state, "ppt_allowed_shapes", {}) or {}
                        violations = []
                        for change in delta.attribute_changes:
                            if change.slide not in allowed:
                                violations.append(change.summarize())
                                continue
                            if change.slide in shape_targets and change.shape_id not in shape_targets[change.slide]:
                                violations.append(change.summarize())
                        violations += [
                            f"slide {s} added/removed outside allowed slides"
                            for s in (*delta.added_slides, *delta.removed_slides)
                            if s not in allowed
                        ]
                        if violations:
                            preview = "; ".join(violations[:6])
                            if getattr(h.state, "ppt_scope_hard", False):
                                raise ValueError(
                                    "cannot finish PPT task: the saved deck modified objects outside the declared "
                                    f"mutation scope (allowed slides {sorted(allowed)}): {preview}"
                                )
                            h.state.record_fact("ppt_scope_violations", preview)
                            summary = summary.rstrip() + "\n\nScope audit (non-blocking): " + preview
        if h.state.facts.get("official_evaluator_present") == "true" and "task_evaluator" not in evidence_kinds:
            from .lifecycle_tools import _run_task_evaluator
            _run_task_evaluator(h)
            evidence_kinds = {record.kind for record in h.state.fresh_evidence()}
            if "task_evaluator" not in evidence_kinds:
                detail = getattr(h.state, "task_evaluator_output", "") or h.state.facts.get("task_evaluator_output", "")
                detail_note = f"\n\n官方评估器失败详情（尾部）：\n{detail}" if detail else ""
                raise ValueError(
                    "cannot finish PPT task: official task evaluator did not pass. "
                    "Read the failure details above, repair only the cited checks, "
                    "save and rerun the evaluator before finishing. "
                    "Continue editing the ACTIVE in-memory draft; do NOT call ppt_open "
                    "(the active deck already contains your edits)." + detail_note
                )
        # Rendering is a harness lifecycle responsibility, not another prompt
        # instruction.  Automatically buy fresh visual evidence before finish
        # whenever a real final artifact and recorder are available.
        if not {"ppt_render", "ppt_visual"}.issubset(evidence_kinds):
            from .ppt_tools import _inspect_rendered, _render
            final_path = final_rows[-1]["path"]
            render_dir = str(recorder.evidence / "final_render")
            try:
                _render(h, final_path, render_dir)
                _inspect_rendered(h, render_dir)
            except Exception as exc:
                diagnostic = f"{type(exc).__name__}: {exc}"
                h.state.record_fact("ppt_renderer_unavailable", diagnostic)
                recorder.check("ppt_render", False, diagnostic)
                summary = summary.rstrip() + f"\n\n渲染验证未执行：{diagnostic}"
            else:
                evidence_kinds = {record.kind for record in h.state.fresh_evidence()}
                if not {"ppt_render", "ppt_visual"}.issubset(evidence_kinds):
                    raise ValueError("cannot finish PPT task: automatic render did not produce fresh render and visual evidence")
    elif h.state.changed_files:
        from ..certificate import require_finish_certificates
        require_finish_certificates(h.state)
    h._done = h._build_completion_summary(summary) if hasattr(h, "_build_completion_summary") else summary.strip()
    h.state.final_summary = h._done
    if getattr(h, "recorder", None):
        h.recorder.finish(h._done, h.state)
    return "task marked complete"


def _tasks(h, items: list[dict]):
    parsed = []
    for item in items:
        try:
            status = Status(item.get("status", "pending"))
        except ValueError as exc:
            raise ValueError(f"invalid task status: {item.get('status')}") from exc
        parsed.append(TaskItem(id=str(item["id"]), content=str(item["content"]), status=status, evidence=list(item.get("evidence") or [])))
    active = sum(item.status is Status.IN_PROGRESS for item in parsed)
    if active > 1:
        raise ValueError("at most one task may be in_progress")
    h.state.tasks = parsed
    return h.state.compact()


code_tools = [
    _make(
        "update_tasks",
        "Replace the structured task list. Use for work with 3+ meaningful steps; keep at most one item in_progress.",
        {"items": {"type": "array", "items": {"type": "object", "properties": {"id": {"type": "string"}, "content": {"type": "string"}, "status": {"type": "string", "enum": ["pending", "in_progress", "completed", "blocked"]}, "evidence": {"type": "array", "items": {"type": "string"}}}, "required": ["id", "content", "status"]}}},
        ["items"],
        lambda h, **kw: _tasks(h, kw["items"]),
    ),
    _make(
        "remember",
        "Append a short note to persistent session memory (styles, user preferences, decisions).",
        {"text": {"type": "string"}},
        ["text"],
        lambda h, **kw: _note(h, kw["text"]),
    ),
    _make(
        "finish",
        "Declare the task complete. Provide the final summary for the user.",
        {"summary": {"type": "string"}},
        ["summary"],
        lambda h, **kw: _finish(h, kw["summary"]),
    ),
]
