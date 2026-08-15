import json
from pathlib import Path


def test_matched_manifest_has_explicit_provider_mapping():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "benchmarks/matched_eval_manifest.json").read_text())
    systems = set(manifest["systems"])
    assert systems == {"xiaopu", "claude_code", "codex", "opencode"}
    assert set(manifest["provider_mapping"]) == systems
    assert manifest["protocol"]["model"] == "deepseek-v4-flash"


def test_power_manifest_is_predeclared_and_separate_from_pilot():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "benchmarks/matched_12_task_manifest.json").read_text())
    assert manifest["status"] == "predeclared_not_yet_run"
    assert len(manifest["task_ids"]) == 12
    assert manifest["fixed_protocol"]["n_concurrent"] == 1
