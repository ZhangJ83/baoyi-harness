"""Merge the deterministic harness trace with the final rendered audit."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from benchmarks.ppt_score import score


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    result = root / "workspace" / "results" / "ppt_harness_demo"
    trace = json.loads((result / "demo-report.json").read_text(encoding="utf-8"))
    audit = json.loads((result / "rendered-audit.json").read_text(encoding="utf-8"))
    deck = result / "ppt-harness-demo.pptx"
    scored = score(deck, min_slides=4, required_text=["Evidence-Aware", "render-feedback"])
    merged = {
        "kind": "ppt_harness_final_evidence",
        "artifact": str(deck),
        "artifact_sha256": hashlib.sha256(deck.read_bytes()).hexdigest(),
        "slides": trace["slides"],
        "stale_evidence_intervention": trace["stale_evidence_intervention"],
        "structural_score": scored["score"],
        "structural_checks": scored["checks"],
        "rendered_png_count": len(list((result / "rendered").glob("slide-*.png"))),
        "montage": str(result / "rendered" / "montage.png"),
        "rendered_visual_audit": audit,
        "claim_boundary": "controlled rendered demo; not a full model-generated PPTBench evaluation",
    }
    target = result / "final-evidence-report.json"
    target.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(merged, ensure_ascii=False, indent=2))
    return 0 if merged["rendered_png_count"] == 4 and audit["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
