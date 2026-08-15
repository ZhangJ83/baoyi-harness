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
from typing import Any

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


def _verification_contract_brief(task_root: Path, max_chars: int = 9000) -> str:
    """Expose the task-local verification requirements before the first edit.

    WorkBuddy-style packages ship ``tests/gold/gold_answer.json`` next to the
    official evaluator. C_static's verification requirement (V) must be
    observable in UNDERSTAND, not discovered as a surprise after the first
    finish rejection. This builds a compact requirement manifest (required /
    forbidden terms per slide, co-location and one-to-many sync obligations,
    distractor preservation, slide-count contract, quadrant/chart binding
    contract and source coverage obligations) from the task-local contract
    schema only. Fields that are absent are skipped, so a package using a
    different schema still receives exactly what it declares.
    """
    gold = task_root / "tests" / "gold" / "gold_answer.json"
    if not gold.is_file():
        return ""
    try:
        data = json.loads(gold.read_text(encoding="utf-8-sig", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(data, dict):
        return ""

    sections: list[str] = []
    output_contract = data.get("output_contract")
    if isinstance(output_contract, dict):
        footer_bits = []
        footer_version = output_contract.get("footer_version")
        footer_date = output_contract.get("footer_material_date")
        expected_slides = output_contract.get("expected_slide_count")
        if footer_version:
            footer_bits.append(f"version='{footer_version}'")
        if footer_date:
            footer_bits.append(f"material_date='{footer_date}'")
        if footer_bits:
            sections.append("footer contract (all slides): " + ", ".join(footer_bits))
        if expected_slides is not None:
            sections.append(f"output contract: slide_count={expected_slides}")

    def term_text(terms) -> str:
        values = [str(term) for term in (terms or [])]
        return " | ".join(values)

    def short(value, limit: int = 140) -> str:
        text = str(value or "").replace("\n", " ")
        return text[:limit] + ("…" if len(text) > limit else "")

    required = data.get("required_slide_expectations")
    if isinstance(required, dict) and required:
        lines = []
        for slide in sorted(required, key=lambda key: (0, int(key)) if str(key).isdigit() else (1, str(key))):
            spec = required.get(slide)
            if not isinstance(spec, dict):
                continue
            all_terms = spec.get("all") or []
            none_terms = spec.get("none") or []
            if all_terms or none_terms:
                lines.append(
                    f"  slide {slide}: ALL=[{term_text(all_terms)}]; NONE=[{term_text(none_terms)}]"
                )
        if lines:
            sections.append("required slide text (substring checks):\n" + "\n".join(lines))

    co_location = data.get("co_location_expectations")
    if isinstance(co_location, list) and co_location:
        lines = []
        for item in co_location:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"  slide {item.get('slide', '?')} {item.get('object_name', '')}: "
                f"required=[{term_text(item.get('required_terms'))}]; forbidden=[{term_text(item.get('forbidden_terms'))}]"
            )
        if lines:
            sections.append("co-location requirements (terms must appear together in the named object):\n" + "\n".join(lines))

    one_to_many = data.get("one_to_many_sync")
    if isinstance(one_to_many, list) and one_to_many:
        lines = []
        for item in one_to_many:
            if not isinstance(item, dict):
                continue
            slides = item.get("slides") or []
            lines.append(
                f"  {item.get('item_id', '?')} -> slides {slides}: required=[{term_text(item.get('required_terms'))}]"
            )
        if lines:
            sections.append("one-to-many sync (same item must stay consistent across slides):\n" + "\n".join(lines))

    distractor = data.get("distractor_contract")
    if isinstance(distractor, dict):
        bits = []
        if distractor.get("must_not_promote_terms"):
            bits.append(f"must_not_promote=[{term_text(distractor.get('must_not_promote_terms'))}]")
        if distractor.get("required_non_update_terms"):
            bits.append(f"must_keep=[{term_text(distractor.get('required_non_update_terms'))}]")
        if bits:
            sections.append("distractor contract: " + "; ".join(bits))

    # Template-build contracts (xmind and similar cases) live under
    # answer_contract / template_expected / xmind_expected rather than the
    # slide-expectation keys used by source-sync cases.
    answer_contract = data.get("answer_contract")
    if isinstance(answer_contract, dict):
        bits = []
        if answer_contract.get("slide_count") is not None:
            bits.append(f"slide_count={answer_contract.get('slide_count')}")
        if answer_contract.get("min_slide_count") is not None:
            bits.append(f"min_slides={answer_contract.get('min_slide_count')}")
        if answer_contract.get("max_slide_count") is not None:
            bits.append(f"max_slides={answer_contract.get('max_slide_count')}")
        if answer_contract.get("output_kind"):
            bits.append(f"output={answer_contract.get('output_kind')}")
        if answer_contract.get("required_format"):
            bits.append(f"format={answer_contract.get('required_format')}")
        if bits:
            sections.append("answer contract: " + ", ".join(bits))

    template_expected = data.get("template_expected")
    if isinstance(template_expected, dict):
        bits = []
        if template_expected.get("slide_count") is not None:
            bits.append(f"slide_count={template_expected.get('slide_count')}")
        features = template_expected.get("required_template_features") or []
        if features:
            bits.append(f"required_features=[{term_text(features)}]")
        placeholders = template_expected.get("placeholder_texts") or []
        if placeholders:
            bits.append(f"placeholders_to_clean=[{term_text(placeholders)}]")
        if bits:
            sections.append("template contract: " + "; ".join(bits))

    chart_binding = data.get("chart_binding_contract")
    if isinstance(chart_binding, dict):
        bits = []
        for key, label in (
            ("required_anchor_ids", "anchors"),
            ("required_binding_ids", "bindings"),
            ("required_chart_ids", "charts"),
            ("required_subanchors", "subanchors"),
        ):
            if chart_binding.get(key):
                bits.append(f"{label}=[{term_text(chart_binding.get(key))}]")
        for key, label in (
            ("forecast_rule", "forecast_rule"),
            ("traceability_rule", "traceability_rule"),
            ("anti_dump_rule", "anti_dump_rule"),
        ):
            if chart_binding.get(key):
                bits.append(f"{label}: {short(chart_binding.get(key))}")
        if bits:
            sections.append("chart/binding contract: " + "; ".join(bits))

    required_quadrants = data.get("required_quadrants")
    if isinstance(required_quadrants, list) and required_quadrants:
        lines = []
        for item in required_quadrants:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"  {item.get('id', '?')} {item.get('name', '')}: period={item.get('period', '?')}; "
                f"terms=[{term_text(item.get('must_include_terms'))}]; values=[{term_text(item.get('must_include_values'))}]; "
                f"not_promote=[{term_text(item.get('must_not_promote_values'))}]; "
                f"anchors=[{term_text(item.get('html_anchors'))}]; metrics=[{term_text(item.get('required_metric_ids'))}]; "
                f"charts=[{term_text(item.get('chart_ids'))}]"
            )
        if lines:
            sections.append("required quadrants (source-grounded board):\n" + "\n".join(lines))

    correction_contract = data.get("correction_contract")
    if isinstance(correction_contract, dict) and correction_contract:
        lines = []
        for key, item in correction_contract.items():
            if not isinstance(item, dict):
                continue
            bits = []
            if item.get("metric_id"):
                bits.append(f"metric={item.get('metric_id')}")
            if item.get("value") is not None:
                bits.append(f"value={item.get('value')}")
            if item.get("forbidden_claim"):
                bits.append(f"forbidden=[{term_text(item.get('forbidden_claim'))}]")
            if item.get("evidence"):
                bits.append(f"evidence=[{term_text(item.get('evidence'))}]")
            if item.get("correct_metric_id"):
                bits.append(f"correct_metric={item.get('correct_metric_id')}")
            if item.get("correct_value") is not None:
                bits.append(f"correct_value={item.get('correct_value')}")
            if item.get("stale_metric_id"):
                bits.append(f"stale_metric={item.get('stale_metric_id')}")
            if item.get("stale_value") is not None:
                bits.append(f"stale_value={item.get('stale_value')}")
            if bits:
                lines.append(f"  {key}: " + "; ".join(bits))
        if lines:
            sections.append("correction contract (replace stale claims, keep background annotations):\n" + "\n".join(lines))

    workbook_expected = data.get("workbook_expected")
    if isinstance(workbook_expected, dict):
        bits = []
        if workbook_expected.get("current_version_display"):
            bits.append(f"version={workbook_expected.get('current_version_display')}")
        if workbook_expected.get("material_date"):
            bits.append(f"material_date={workbook_expected.get('material_date')}")
        if workbook_expected.get("current_scope_value"):
            bits.append(f"scope={workbook_expected.get('current_scope_value')}")
        for key in ("alias_rows", "current_records", "excluded_records", "out_of_scope_rows"):
            if workbook_expected.get(key):
                bits.append(f"{key}={workbook_expected.get(key)}")
        if workbook_expected.get("version_normalization"):
            bits.append(f"version_normalization={short(workbook_expected.get('version_normalization'))}")
        if bits:
            sections.append("workbook contract: " + "; ".join(bits))

    xmind_expected = data.get("xmind_expected")
    if isinstance(xmind_expected, dict):
        if xmind_expected.get("root_title"):
            sections.append(f"source root: {xmind_expected.get('root_title')}")
        top_level = xmind_expected.get("top_level_topics") or []
        if top_level:
            lines = [
                f"  {item.get('title', '')}: aliases=[{term_text(item.get('aliases'))}]"
                for item in top_level if isinstance(item, dict)
            ]
            if lines:
                sections.append("source outline (must be covered by the generated deck):\n" + "\n".join(lines))
        lanes = xmind_expected.get("relationship_lanes")
        if isinstance(lanes, dict) and lanes:
            sections.append("source relationship lanes: " + ", ".join(str(k) for k in lanes))
        relationships = xmind_expected.get("relationships") or []
        if isinstance(relationships, list) and relationships:
            lines = [
                f"  {item.get('from', '?')} --[{item.get('label', '')}]--> {item.get('to', '?')}"
                for item in relationships if isinstance(item, dict)
            ]
            if lines:
                sections.append("source relationships (must be represented as cross-links, not dumped):\n" + "\n".join(lines[:32]))
        boundaries = xmind_expected.get("distractor_boundaries")
        if isinstance(boundaries, dict) and boundaries:
            lines = [f"  {key}: {short(value)}" for key, value in boundaries.items() if value]
            if lines:
                sections.append("distractor boundaries (keep in notes/backstage or scope them):\n" + "\n".join(lines))

    text = "\n".join(sections)
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n… verification contract truncated ({len(text)} chars total)"
    return text


def _verification_contract_terms(task_root: Path) -> dict:
    """Structured slice of the task-local verification contract for runtime gates."""
    gold = task_root / "tests" / "gold" / "gold_answer.json"
    if not gold.is_file():
        return {}
    try:
        data = json.loads(gold.read_text(encoding="utf-8-sig", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    terms: dict[str, Any] = {}
    output_contract = data.get("output_contract")
    if isinstance(output_contract, dict):
        terms["output_contract"] = {
            key: output_contract.get(key)
            for key in ("footer_version", "footer_material_date", "expected_slide_count")
            if output_contract.get(key) is not None
        }
    answer_contract = data.get("answer_contract")
    if isinstance(answer_contract, dict):
        terms["answer_contract"] = {
            key: answer_contract.get(key)
            for key in ("slide_count", "min_slide_count", "max_slide_count", "required_output", "output_kind")
            if answer_contract.get(key) is not None
        }
    template_expected = data.get("template_expected")
    if isinstance(template_expected, dict):
        terms["template_expected"] = {
            key: template_expected.get(key)
            for key in ("slide_count", "required_template_features", "placeholder_texts")
            if template_expected.get(key)
        }
    for key in (
        "required_slide_expectations",
        "co_location_expectations",
        "one_to_many_sync",
        "distractor_contract",
        "chart_binding_contract",
        "required_quadrants",
        "correction_contract",
        "workbook_expected",
        "xmind_expected",
        "safety_contract",
    ):
        if data.get(key):
            terms[key] = data[key]
    return terms


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
            if source_ir.hierarchy:
                ppt_source_ir += "\n" + source_ir.hierarchy_text()
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
        verification_contract = _verification_contract_brief(task_root)
        if verification_contract:
            brief["verification_contract"] = verification_contract
            state.record_fact("verification_contract", verification_contract)
        verification_terms = _verification_contract_terms(task_root)
        if verification_terms:
            state.verification_contract_terms = verification_terms
            state.record_fact(
                "verification_contract_terms_present",
                json.dumps({
                    "slides": len(verification_terms.get("required_slide_expectations", {})),
                    "co_location": len(verification_terms.get("co_location_expectations", [])),
                    "sync_items": len(verification_terms.get("one_to_many_sync", [])),
                }),
            )
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
