"""Deterministic task/workspace intake before the first model turn.

Codex and Claude Code assemble cwd, project instructions, permissions and
tool context before sampling the model.  Xiaopu extends that pattern with an
office-specific ContentIR brief so document tasks do not begin with a costly
model-driven directory crawl.
"""
from __future__ import annotations

import json
import csv
import re
from pathlib import Path

from . import config
from .office_ir import build_content_ir, persist_content_ir
from .permissions import path_within


OFFICE_SUFFIXES = {".md", ".txt", ".json", ".yaml", ".yml", ".html", ".htm", ".csv", ".xlsx", ".pptx", ".docx", ".xmind", ".png", ".jpg", ".jpeg", ".gif", ".svg"}


def bind_manifest_task(task: str, root: Path | None = None) -> tuple[str, str | None]:
    """Resolve a literal ``tasks/<task_id>`` batch placeholder to one task.

    This is deterministic intake, not model planning.  It prevents the model
    from treating the placeholder itself as a directory and guessing the
    first input filename.  The selected task id is returned for audit/UI use.
    """

    normalized = task.replace("/", "\\").casefold()
    if "workspace_manifest.csv" not in normalized or "tasks\\<task_id>" not in normalized:
        return task, None
    workspace = (root or config.sandbox_root()).resolve()
    manifest = workspace / "workspace_manifest.csv"
    if not manifest.is_file():
        return task, None
    with manifest.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        task_id = (row.get("task_id") or "").strip()
        task_dir = (row.get("task_dir") or f"tasks/{task_id}").strip()
        status = (row.get("status") or "").strip().casefold()
        candidate = (workspace / task_dir).resolve()
        output_dir = candidate / "output"
        already_done = output_dir.is_dir() and any(output_dir.glob("*.pptx"))
        if task_id and candidate.is_dir() and status not in {"completed", "done"} and not already_done:
            return task.replace("tasks\\<task_id>", task_dir.replace("/", "\\")), task_id
    return task, None


def task_root_from_prompt(task: str, root: Path | None = None) -> Path | None:
    """Resolve explicit paths *or bare task ids* against workspace facts.

    The user-facing contract is deliberately one-line: a task directory name
    is enough. Resolution is deterministic and precedes domain/skill routing;
    no PPT-specific keyword or prompt template is required.
    """
    workspace = (root or config.sandbox_root()).resolve()
    from .task_index import resolve_task
    indexed = resolve_task(workspace, task)
    if indexed is not None:
        return indexed
    tasks_dir = workspace / "tasks"
    if tasks_dir.is_dir():
        normalized = task.replace("/", "\\").casefold()
        matches = [
            path.resolve()
            for path in tasks_dir.iterdir()
            if path.is_dir() and (
                f"tasks\\{path.name}".casefold() in normalized
                or path.name.casefold() in normalized
            )
        ]
        if matches:
            resolved = max(matches, key=lambda path: len(path.name))
            return resolved if path_within(workspace, resolved) else None
    match = re.search(r"tasks[\\/]([^\\/\s`]+)", task, re.IGNORECASE)
    if not match:
        return None
    candidate = (workspace / "tasks" / match.group(1).rstrip("。，,.;:）)")) .resolve()
    return candidate if path_within(workspace, candidate) and candidate.is_dir() else None


def prepare_task_brief(task: str, state, recorder=None, *, max_sources: int = 24) -> str:
    task_root = task_root_from_prompt(task)
    if task_root is None:
        return ""
    state.record_fact("task_root", str(task_root.relative_to(config.sandbox_root())))
    identity = f"preflight:{task_root}"
    if identity in state.facts and state.content_brief:
        return state.content_brief

    sources: list[Path] = []
    instruction = task_root / "instruction.md"
    if instruction.is_file():
        sources.append(instruction)
        instruction_text = instruction.read_text(encoding="utf-8-sig", errors="replace")
        state.record_fact("task_instruction", instruction_text.strip())
        output_match = re.search(r"output[\\/][^`\r\n]+?\.pptx", instruction_text, re.IGNORECASE)
        if output_match:
            required = task_root / output_match.group(0).replace("/", "\\")
            state.record_fact("required_output_pptx", str(required.relative_to(config.sandbox_root())))
        else:
            # Some task packages wrap the real instruction in
            # ``instruction_source.md`` while ``instruction.md`` stays a short
            # wrapper. Fall back to the detailed instruction before defaulting.
            detailed = task_root / "instruction_source.md"
            detailed_text = ""
            if detailed.is_file():
                detailed_text = detailed.read_text(encoding="utf-8-sig", errors="replace")
            output_match = re.search(r"output[\\/][^`\r\n]+?\.pptx", detailed_text, re.IGNORECASE)
            if output_match:
                required = task_root / output_match.group(0).replace("/", "\\")
                state.record_fact("required_output_pptx", str(required.relative_to(config.sandbox_root())))
            else:
                # One-line tasks deliberately omit delivery details. Keep output
                # placement deterministic and task-local instead of allowing the
                # model to invent a workspace-root ``deck.pptx``.
                required = task_root / "output" / "final.pptx"
                state.record_fact("required_output_pptx", str(required.relative_to(config.sandbox_root())))
    task_card = task_root / "task_card.md"
    if task_card.is_file():
        card_text = task_card.read_text(encoding="utf-8-sig", errors="replace")
        capability_match = re.search(r"^CAPABILITY:\s*(.+)$", card_text, re.MULTILINE | re.IGNORECASE)
        difficulty_match = re.search(r"^DIFFICULTY:\s*(.+)$", card_text, re.MULTILINE | re.IGNORECASE)
        if capability_match:
            state.record_fact("task_capability", capability_match.group(1).strip())
        if difficulty_match:
            state.record_fact("task_difficulty", difficulty_match.group(1).strip())
    input_root = task_root / "input"
    if input_root.is_dir():
        sources.extend(
            path for path in sorted(input_root.iterdir())
            if path.is_file() and path.suffix.lower() in OFFICE_SUFFIXES
        )
    sources.extend(
        path for path in sorted(task_root.iterdir())
        if path.is_file()
        and path != instruction
        and path.name != "TRAJECTORY_CAPTURE_CONTRACT.md"
        and path.suffix.lower() in OFFICE_SUFFIXES
    )
    # Keep order stable while removing duplicates and generated deliverables.
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in sources:
        resolved = path.resolve()
        if resolved not in seen and "output" not in resolved.parts and "intermediate" not in resolved.parts:
            seen.add(resolved)
            unique.append(resolved)
    unique = unique[:max_sources]
    if not unique:
        return ""

    # Deterministic discovery knows the exact task-local filenames.  Bind one
    # unambiguous source deck now instead of making the model guess conventional
    # names such as input.pptx or source.pptx.
    deck_candidates = [path for path in unique if path.suffix.lower() == ".pptx"]
    if len(deck_candidates) == 1:
        state.record_fact(
            "ppt_input_deck",
            str(deck_candidates[0].relative_to(config.sandbox_root())),
        )
    elif len(deck_candidates) > 1:
        state.record_fact(
            "ppt_input_candidates",
            json.dumps(
                [str(path.relative_to(config.sandbox_root())) for path in deck_candidates],
                ensure_ascii=False,
            ),
        )

    # Compatibility bridge: generic source registration (core.intake) and the
    # PPT source normalizer (domains.ppt.intake) now feed the model-facing
    # brief. The legacy ContentIR persists as the full on-disk artifact.
    try:
        from core.intake import IntakePolicy, balance_brief, discover_sources
        from domains.ppt.intake import build_presentation_source_ir

        text_suffixes = {".md", ".txt", ".json", ".yaml", ".yml", ".html", ".htm", ".csv"}
        kind_map = {suffix: ("text" if suffix in text_suffixes else "binary") for suffix in OFFICE_SUFFIXES}
        registrations = discover_sources(unique, kind_map=kind_map)
        portable_brief = balance_brief(
            registrations, IntakePolicy(max_total_chars=12000, max_per_source=30000)
        )
        ppt_source_ir = ""
        try:
            source_ir = build_presentation_source_ir(task_root)
            ppt_source_ir = source_ir.summary()
            state.record_fact("ppt_source_ir", ppt_source_ir)
        except Exception:
            ppt_source_ir = ""
    except Exception:
        registrations = []
        portable_brief = ""
        ppt_source_ir = ""

    ir = build_content_ir(unique, max_chars_per_source=30000)
    artifact = persist_content_ir(ir, config.sandbox_root())
    brief = ir.to_model_dict(max_total_chars=12000)
    if not isinstance(brief, dict):
        brief = {"legacy_brief": brief}
    brief["task_root"] = str(task_root.relative_to(config.sandbox_root()))
    brief["full_ir_artifact"] = str(artifact.relative_to(config.sandbox_root()))
    if portable_brief:
        brief["content_brief"] = portable_brief
    if ppt_source_ir:
        brief["ppt_source_ir"] = ppt_source_ir
    if len(deck_candidates) == 1:
        brief["input_pptx"] = str(deck_candidates[0].relative_to(config.sandbox_root()))
    evaluator = task_root / "tests" / "grading" / "test_verify.py"
    if evaluator.is_file():
        evaluator_rel = str(evaluator.relative_to(config.sandbox_root()))
        brief["official_evaluator"] = evaluator_rel
        state.record_fact("official_evaluator", evaluator_rel)
        state.record_fact("official_evaluator_present", "true")
    state.content_brief = json.dumps(brief, ensure_ascii=False)
    state.source_paths.update(str(path) for path in unique)
    state.record_fact(identity, f"{len(unique)} sources; full_ir={artifact.relative_to(config.sandbox_root())}")
    for source in ir.sources:
        state.record_fact(f"source:{source.path}", f"kind={source.kind} sha256={source.sha256} chars={len(source.text)}")
    # New-core registrations win over legacy source facts.
    for registration in registrations:
        state.record_fact(
            f"source:{registration.path}",
            f"kind={registration.kind} sha256={registration.sha256} chars={len(registration.text)}",
        )
    if recorder is not None:
        for path in unique:
            recorder.record_input(path, purpose="preflight-content-ir-source")
        recorder.event("content_ir_prepared", sources=[str(path) for path in unique], artifact=str(artifact))
    return state.content_brief
