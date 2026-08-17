import json
import io
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

from benchmarks.run_official_swe_verified_v2 import build_prompt, safe_extract, score_eligible


ROOT = Path(__file__).resolve().parents[1]
ARROW = ROOT.parent / "hf-cache/datasets/SWE-bench___swe-bench_verified/default/0.0.0/91aa3ed51b709be6457e12d00300a6a596d4c6a3/swe-bench_verified-test.arrow"


def test_prompt_excludes_gold_and_test_patch_content():
    row = {"instance_id": "x", "repo": "a/b", "base_commit": "abc", "problem_statement": "Fix public behavior",
           "patch": "SECRET GOLD", "test_patch": "SECRET TEST"}
    prompt = build_prompt(row)
    assert "Fix public behavior" in prompt
    assert "SECRET GOLD" not in prompt and "SECRET TEST" not in prompt


def test_score_eligibility_accepts_resolved_or_unresolved_completed_trial():
    base = {"total_instances": 1, "submitted_instances": 1, "completed_instances": 1,
            "empty_patch_instances": 0, "error_instances": 0, "completed_ids": ["x"], "submitted_ids": ["x"]}
    assert score_eligible(base, "x") is True
    base["error_instances"] = 1
    assert score_eligible(base, "x") is False


@pytest.mark.swebench
@pytest.mark.skipif(not ARROW.exists(), reason="official SWE-bench Arrow dataset not installed")
def test_dry_run_freezes_all_12_without_credential(tmp_path):
    run_root = tmp_path / "run"
    result = subprocess.run([sys.executable, str(ROOT / "benchmarks/run_official_swe_verified_v2.py"),
                             "--dataset-arrow", str(ARROW), "--run-root", str(run_root), "--dry-run"],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    manifest = json.loads((run_root / "run_manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["instance_ids"]) == len(set(manifest["instance_ids"])) == 12
    assert manifest["dry_run"] is True


def test_checkout_archive_rejects_path_traversal(tmp_path):
    archive = tmp_path / "bad.tar"
    with tarfile.open(archive, "w") as stream:
        payload = b"escape"
        member = tarfile.TarInfo("../escape.txt")
        member.size = len(payload)
        stream.addfile(member, io.BytesIO(payload))
    with pytest.raises(RuntimeError, match="path traversal"):
        safe_extract(archive, tmp_path / "out")
