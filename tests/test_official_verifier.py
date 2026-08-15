from pathlib import Path

from benchmarks.official_swe_verifier import verify


def test_official_sample_verifies_first_checkout(tmp_path):
    root = Path(__file__).parents[1]
    import json
    manifest = json.loads((root / "benchmarks" / "official_swe_sample.json").read_text())
    item = manifest["instances"][0]
    checkout = tmp_path / item["instance_id"].split("__", 1)[-1]
    checkout.mkdir()
    result = verify(root, tmp_path, 1)
    assert result["rows"][0]["status"] == "base_commit_mismatch"
