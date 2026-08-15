import copy
import json
from pathlib import Path

from benchmarks.validate_pptbench_model_eval_v2 import validate


ROOT = Path(__file__).resolve().parents[1]


def load_protocol():
    return json.loads((ROOT / "benchmarks/pptbench_model_eval_v2.json").read_text(encoding="utf-8"))


def test_frozen_ppt_protocol_and_six_input_hashes_are_valid():
    result = validate(load_protocol(), ROOT, credential_present=False)
    assert result["valid"] is True
    assert result["assets_ready"] is True
    assert result["runnable_now"] is False
    assert result["task_count"] == 12
    assert result["expected_decks"] == 36
    assert result["fixed_input_decks"] == 6


def test_protocol_fails_closed_on_input_hash_or_task_count_drift():
    protocol = copy.deepcopy(load_protocol())
    protocol["tasks"][6]["input"]["sha256"] = "0" * 64
    protocol["tasks"].pop()
    result = validate(protocol, ROOT, credential_present=True)
    assert result["valid"] is False
    assert result["runnable_now"] is False
    assert "task_count_must_equal_12" in result["errors"]
    assert any("input_deck_hash_mismatch" in error for error in result["errors"])


def test_protocol_fails_closed_on_unicode_corruption():
    protocol = copy.deepcopy(load_protocol())
    protocol["tasks"][3]["facts"][0] = "On track / \ufffd"
    result = validate(protocol, ROOT, credential_present=False)
    assert result["valid"] is False
    assert "unicode_replacement_or_mojibake_detected" in result["errors"]
