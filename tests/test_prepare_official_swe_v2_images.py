from pathlib import Path

import pytest

from benchmarks.prepare_official_swe_v2_images import expected_image_key, plan


ROOT = Path(__file__).resolve().parents[1]
ARROW = ROOT.parent / "hf-cache/datasets/SWE-bench___swe-bench_verified/default/0.0.0/91aa3ed51b709be6457e12d00300a6a596d4c6a3/swe-bench_verified-test.arrow"


@pytest.mark.swebench
@pytest.mark.skipif(not ARROW.exists(), reason="official SWE-bench Arrow dataset not installed")
def test_image_plan_covers_exact_frozen_12():
    manifest, rows = plan(ROOT / "benchmarks/official_swe_verified_v2.json", ARROW)
    assert manifest["n_instances"] == 12
    assert len(set(manifest["expected_images"])) == 12
    assert all(row["image_key"].startswith("sweb.eval.x86_64.") for row in rows)


def test_image_key_matches_official_convention():
    assert expected_image_key("Astropy__Astropy-12907") == "sweb.eval.x86_64.astropy__astropy-12907:latest"


@pytest.mark.swebench
@pytest.mark.skipif(not ARROW.exists(), reason="official SWE-bench Arrow dataset not installed")
def test_plan_rejects_nonfrozen_instance():
    with pytest.raises(ValueError, match="unique subset"):
        plan(ROOT / "benchmarks/official_swe_verified_v2.json", ARROW, ["astropy__astropy-99999"])
