import json
from pathlib import Path

from agent.run_bundle_validator import digest, validate_run_bundle as validate


def _write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _valid_bundle(root: Path, *, trace_name: str = "trajectory.md") -> Path:
    (root / "input").mkdir(parents=True)
    (root / "input" / "instruction.md").write_text("make one slide", encoding="utf-8")
    (root / "output.pptx").write_bytes(b"pptx-evidence")
    if trace_name.endswith(".jsonl"):
        (root / trace_name).write_text('{"kind":"tool"}\n', encoding="utf-8")
    else:
        (root / trace_name).write_text("# Trajectory\n\nDone.\n", encoding="utf-8")
    _write_json(root / "tool_calls.json", [{"name": "ppt_save"}])
    _write_json(root / "evaluation.json", {"score": 1})
    _write_json(root / "run_manifest.json", {"schema": "xiaopu-run-v1"})
    return root


def test_accepts_compact_bundle_with_markdown_trajectory(tmp_path):
    result = validate(_valid_bundle(tmp_path))

    assert result["valid"] is True
    assert result["components"] == {
        "input": "input",
        "output": "output.pptx",
        "trajectory": "trajectory.md",
        "tool_calls": "tool_calls.json",
        "evaluation": "evaluation.json",
        "manifest": "run_manifest.json",
    }


def test_accepts_recorder_steps_as_execution_trace(tmp_path):
    result = validate(_valid_bundle(tmp_path, trace_name="steps.jsonl"))

    assert result["valid"] is True
    assert result["components"]["trajectory"] == "steps.jsonl"


def test_reports_every_missing_component_clearly(tmp_path):
    result = validate(tmp_path)

    assert result["valid"] is False
    assert len(result["errors"]) == 6
    joined = "\n".join(result["errors"])
    for label in ("input", "output", "execution trace", "tool_calls", "evaluation", "manifest"):
        assert label in joined


def test_rejects_empty_component_and_malformed_json(tmp_path):
    _valid_bundle(tmp_path)
    (tmp_path / "output.pptx").write_bytes(b"")
    (tmp_path / "evaluation.json").write_text("{broken", encoding="utf-8")

    result = validate(tmp_path)

    assert result["valid"] is False
    assert any("missing output" in error for error in result["errors"])
    assert any("evaluation: invalid JSON" in error for error in result["errors"])


def test_reuses_evidence_manifest_hash_contract_when_files_are_declared(tmp_path):
    _valid_bundle(tmp_path)
    output = tmp_path / "output.pptx"
    manifest = {
        "schema": "evidence-manifest-v1",
        "files": [{"path": "output.pptx", "bytes": output.stat().st_size, "sha256": digest(output)}],
    }
    _write_json(tmp_path / "run_manifest.json", manifest)

    assert validate(tmp_path)["valid"] is True

    manifest["files"][0]["sha256"] = "0" * 64
    _write_json(tmp_path / "run_manifest.json", manifest)
    result = validate(tmp_path)
    assert result["valid"] is False
    assert "manifest: sha256 mismatch for output.pptx" in result["errors"]


def test_rejects_manifest_path_escape(tmp_path):
    _valid_bundle(tmp_path)
    _write_json(tmp_path / "run_manifest.json", {"files": [{"path": "../secret.txt"}]})

    result = validate(tmp_path)

    assert result["valid"] is False
    assert any("path escapes run directory" in error for error in result["errors"])
