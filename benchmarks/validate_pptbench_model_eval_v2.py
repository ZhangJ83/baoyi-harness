"""Validate the frozen model-generated PPT evaluation before any model call."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from pathlib import Path


REQUIRED_SYSTEMS = {"xiaopu", "claude_code", "codex"}
REQUIRED_KINDS = {"create", "modify", "repair", "typography"}
REQUIRED_DIMENSIONS = {
    "content_fidelity", "narrative_hierarchy", "layout", "typography",
    "visual_consistency", "density", "edit_fidelity",
}
MOJIBAKE_MARKERS = ("\ufffd", "锛", "涓", "姝ｅ父", "椤圭洰")


def sha256(path: Path) -> str:
    data = path.read_bytes()
    if path.suffix.lower() in {".py", ".json", ".md", ".txt", ".yml", ".yaml", ".toml"}:
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def validate(protocol: dict, root: Path, *, credential_present: bool) -> dict:
    errors: list[str] = []
    protocol_text = json.dumps(protocol, ensure_ascii=False)
    if any(marker in protocol_text for marker in MOJIBAKE_MARKERS):
        errors.append("unicode_replacement_or_mojibake_detected")
    tasks = protocol.get("tasks", [])
    systems = protocol.get("systems", [])
    ids = [task.get("id") for task in tasks]
    if protocol.get("schema") != "pptbench-model-eval-protocol-v2":
        errors.append("schema_mismatch")
    if protocol.get("status") != "prospective_not_run":
        errors.append("status_must_remain_prospective_before_generation")
    if not protocol.get("anti_harking_boundary"):
        errors.append("missing_anti_harking_boundary")
    if not protocol.get("amended_at") or "before any model deck generation" not in protocol.get("amendment_boundary", ""):
        errors.append("pre_generation_amendment_boundary_missing")
    if len(tasks) != 12 or protocol.get("n_tasks") != 12:
        errors.append("task_count_must_equal_12")
    if len(ids) != len(set(ids)) or any(not isinstance(value, str) or not value for value in ids):
        errors.append("task_ids_invalid_or_duplicate")
    if set(systems) != REQUIRED_SYSTEMS or protocol.get("expected_decks") != 36:
        errors.append("three_system_36_deck_contract_mismatch")
    counts = Counter(task.get("kind") for task in tasks)
    if set(counts) != REQUIRED_KINDS or any(counts[kind] < 2 for kind in REQUIRED_KINDS):
        errors.append("task_kind_coverage_mismatch")
    input_count = 0
    for task in tasks:
        missing = [key for key in ("audience", "deck_job", "prompt", "facts", "min_slides", "max_slides", "required_text") if not task.get(key)]
        if missing:
            errors.append(f"{task.get('id')}:missing_fields:{','.join(missing)}")
        if not isinstance(task.get("facts"), list) or not isinstance(task.get("required_text"), list):
            errors.append(f"{task.get('id')}:facts_or_required_text_not_list")
        if not isinstance(task.get("min_slides"), int) or not isinstance(task.get("max_slides"), int) or task.get("min_slides", 0) > task.get("max_slides", -1):
            errors.append(f"{task.get('id')}:invalid_slide_bounds")
        source = task.get("input")
        if source is not None:
            input_count += 1
            path = root / str(source.get("path", ""))
            if not path.is_file():
                errors.append(f"{task.get('id')}:missing_input_deck")
            elif source.get("sha256") != sha256(path):
                errors.append(f"{task.get('id')}:input_deck_hash_mismatch")
    if input_count != 6:
        errors.append("exactly_six_fixed_input_tasks_required")
    if len(tasks) - input_count != 6:
        errors.append("exactly_six_from_scratch_tasks_required")
    review = protocol.get("blind_review", {})
    if review.get("required") is not True or review.get("n_reviewers") != 2:
        errors.append("two_reviewer_blind_contract_missing")
    if (review.get("anonymous_public_bundles_required") is not True
            or review.get("visible_system_identity_fails_packaging") is not True
            or set(review.get("reviewer_attestations", [])) != {"independent_from_generation", "reviewer_non_author", "conflicts_declared"}):
        errors.append("anonymous_bundle_or_reviewer_attestation_contract_missing")
    if set(review.get("dimensions", [])) != REQUIRED_DIMENSIONS:
        errors.append("blind_review_dimensions_mismatch")
    rendering = protocol.get("rendering", {})
    if rendering.get("same_renderer_for_all_systems") is not True or len(rendering.get("required_outputs_per_deck", [])) < 6:
        errors.append("rendering_contract_incomplete")
    presentation = protocol.get("presentation_contract", {})
    fonts = presentation.get("minimum_font_points", {})
    if fonts != {"deck_title": 50, "slide_title": 35, "subheading": 24, "body": 16}:
        errors.append("minimum_font_contract_mismatch")
    if presentation.get("sources_block_required_in_speaker_notes") is not True:
        errors.append("sources_notes_contract_missing")
    execution = protocol.get("execution", {})
    required_runtime = {
        "runner": "benchmarks/run_pptbench_model_eval_v2.py",
        "result_validator": "benchmarks/validate_model_generated_ppt_eval.py",
        "xiaopu_ppt_tools": "agent/tools/ppt_tools.py",
        "harness": "agent/harness.py",
        "runtime": "agent/runtime.py",
    }
    for name, expected_path in required_runtime.items():
        row = execution.get(name, {})
        path = root / row.get("path", "")
        if row.get("path") != expected_path or not path.is_file() or row.get("sha256") != sha256(path):
            errors.append(f"execution_runtime_hash_mismatch:{name}")
    if execution.get("cli_versions") != {
        "xiaopu": "repository-runtime",
        "claude_code": "2.1.228 (Claude Code)",
        "codex": "codex-cli 0.146.1",
    }:
        errors.append("cli_version_contract_mismatch")
    if execution.get("resumable_fail_closed") is not True or execution.get("independent_artifact_recompute") is not True:
        errors.append("execution_integrity_contract_missing")
    assets_ready = not errors
    return {
        "schema": "pptbench-model-eval-protocol-v2-validation",
        "valid": assets_ready,
        "assets_ready": assets_ready,
        "provider_credential_current_process": credential_present,
        "runnable_now": assets_ready and credential_present,
        "task_count": len(tasks),
        "system_count": len(systems),
        "expected_decks": protocol.get("expected_decks"),
        "kind_counts": dict(sorted(counts.items())),
        "fixed_input_decks": input_count,
        "errors": errors,
        "boundary": "Protocol and local-asset readiness only; no deck-generation or quality evidence.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=Path("benchmarks/pptbench_model_eval_v2.json"))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    protocol = json.loads(args.protocol.read_text(encoding="utf-8-sig"))
    credential = bool(os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY"))
    result = validate(protocol, args.root.resolve(), credential_present=credential)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
