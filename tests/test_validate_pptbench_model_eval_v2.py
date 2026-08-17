import copy
import hashlib
import json
from pathlib import Path

import pytest

from benchmarks.validate_pptbench_model_eval_v2 import validate


ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _create_hermetic_fixture(tmp_path: Path) -> tuple[dict, Path]:
    runner = tmp_path / "benchmarks/run_pptbench_model_eval_v2.py"
    val = tmp_path / "benchmarks/validate_model_generated_ppt_eval.py"
    tools = tmp_path / "agent/tools/ppt_tools.py"
    for f in (runner, val, tools):
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(f"dummy {f.name}", encoding="utf-8")

    kinds = [
        "create", "create", "create", "create", "create",
        "modify", "modify", "modify",
        "repair", "repair",
        "typography", "typography",
    ]
    tasks = []
    for i, kind in enumerate(kinds):
        task_id = f"task-{i+1:02d}"
        input_spec = None
        if i >= 6:
            input_file = tmp_path / f"inputs/deck_{i}.pptx"
            input_file.parent.mkdir(parents=True, exist_ok=True)
            input_file.write_bytes(b"dummy pptx content")
            input_spec = {
                "path": str(input_file.relative_to(tmp_path)).replace("\\", "/"),
                "sha256": _sha256(input_file),
            }
        tasks.append({
            "id": task_id,
            "kind": kind,
            "audience": "executive audience",
            "deck_job": "decision review",
            "prompt": f"Prompt for {task_id}",
            "facts": ["Fact 1", "Fact 2"],
            "min_slides": 1,
            "max_slides": 5,
            "required_text": ["Fact 1"],
            "input": input_spec,
        })

    protocol = {
        "schema": "pptbench-model-eval-protocol-v2",
        "status": "prospective_not_run",
        "anti_harking_boundary": "anti harking boundary description",
        "amended_at": "2026-08-18T00:00:00+08:00",
        "amendment_boundary": "before any model deck generation was performed",
        "systems": ["xiaopu", "claude_code", "codex"],
        "n_tasks": 12,
        "expected_decks": 36,
        "budget": {
            "max_generated_output_tokens": 4500,
            "max_covered_local_tool_calls": 60,
            "max_agent_wall_seconds": 300,
        },
        "execution": {
            "runner": {"path": str(runner.relative_to(tmp_path)).replace("\\", "/"), "sha256": _sha256(runner)},
            "result_validator": {"path": str(val.relative_to(tmp_path)).replace("\\", "/"), "sha256": _sha256(val)},
            "xiaopu_ppt_tools": {"path": str(tools.relative_to(tmp_path)).replace("\\", "/"), "sha256": _sha256(tools)},
            "cli_versions": {
                "xiaopu": "repository-runtime",
                "claude_code": "2.1.228 (Claude Code)",
                "codex": "codex-cli 0.146.1",
            },
            "resumable_fail_closed": True,
            "independent_artifact_recompute": True,
        },
        "presentation_contract": {
            "minimum_font_points": {"deck_title": 50, "slide_title": 35, "subheading": 24, "body": 16},
            "sources_block_required_in_speaker_notes": True,
        },
        "rendering": {
            "same_renderer_for_all_systems": True,
            "required_outputs_per_deck": ["pptx", "pdf", "slide_pngs", "montage", "structural_report", "pixel_audit"],
        },
        "blind_review": {
            "required": True,
            "n_reviewers": 2,
            "dimensions": [
                "content_fidelity", "narrative_hierarchy", "layout", "typography",
                "visual_consistency", "density", "edit_fidelity",
            ],
            "anonymous_public_bundles_required": True,
            "visible_system_identity_fails_packaging": True,
            "reviewer_attestations": [
                "independent_from_generation",
                "reviewer_non_author",
                "conflicts_declared",
            ],
        },
        "tasks": tasks,
    }
    return protocol, tmp_path


def test_validator_accepts_valid_hermetic_protocol(tmp_path: Path):
    protocol, root = _create_hermetic_fixture(tmp_path)
    result = validate(protocol, root, credential_present=False)
    assert result["valid"] is True
    assert result["assets_ready"] is True
    assert result["runnable_now"] is False
    assert result["task_count"] == 12
    assert result["expected_decks"] == 36
    assert result["fixed_input_decks"] == 6


def test_validator_rejects_input_hash_drift(tmp_path: Path):
    protocol, root = _create_hermetic_fixture(tmp_path)
    protocol["tasks"][6]["input"]["sha256"] = "0" * 64
    result = validate(protocol, root, credential_present=True)
    assert result["valid"] is False
    assert any("input_deck_hash_mismatch" in error for error in result["errors"])


def test_validator_rejects_missing_input_deck(tmp_path: Path):
    protocol, root = _create_hermetic_fixture(tmp_path)
    input_rel = protocol["tasks"][6]["input"]["path"]
    (root / input_rel).unlink()
    result = validate(protocol, root, credential_present=False)
    assert result["valid"] is False
    assert any("missing_input_deck" in error for error in result["errors"])


def test_validator_rejects_task_count_drift(tmp_path: Path):
    protocol, root = _create_hermetic_fixture(tmp_path)
    protocol["tasks"].pop()
    result = validate(protocol, root, credential_present=False)
    assert result["valid"] is False
    assert "task_count_must_equal_12" in result["errors"]


def test_validator_rejects_unicode_corruption(tmp_path: Path):
    protocol, root = _create_hermetic_fixture(tmp_path)
    protocol["tasks"][3]["facts"][0] = "On track / \ufffd"
    result = validate(protocol, root, credential_present=False)
    assert result["valid"] is False
    assert "unicode_replacement_or_mojibake_detected" in result["errors"]


@pytest.mark.protocol_lock
def test_canonical_frozen_pptbench_protocol_is_valid():
    protocol_path = ROOT / "benchmarks/pptbench_model_eval_v2.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    result = validate(protocol, ROOT, credential_present=False)
    assert result["valid"] is True
    assert result["assets_ready"] is True
    assert result["task_count"] == 12
    assert result["expected_decks"] == 36
    assert result["fixed_input_decks"] == 6
