"""Source-to-output provenance bindings for multi-source tasks."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple

from domains.ppt.intake import PresentationSourceIR

ANCHOR_RE = re.compile(r"\b(?:H|CH|CN|M|CN-R)[-_]?\d+(?:[-_][a-z])?", flags=re.IGNORECASE)


@dataclass
class SourceBinding:
    source_id: str
    kind: str
    anchors: Tuple[str, ...] = ()
    output_ref: str = ""

    def as_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "kind": self.kind,
            "anchors": list(self.anchors),
            "output_ref": self.output_ref,
        }


def collect_bindings(source_ir: PresentationSourceIR, output_path: Path) -> List[SourceBinding]:
    """Produce one binding per registered source, with extracted anchors when present."""
    bindings: List[SourceBinding] = []
    for reg in source_ir.sources:
        anchors = tuple(dict.fromkeys(ANCHOR_RE.findall(reg.text))) if reg.text else ()
        bindings.append(SourceBinding(
            source_id=reg.path.name,
            kind=reg.kind,
            anchors=anchors,
            output_ref=str(output_path),
        ))
    return bindings
