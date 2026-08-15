"""Typed, provenance-preserving content extraction for office-document tasks."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import csv
import hashlib
import html
import io
import re
from pathlib import Path
from xml.etree import ElementTree as ET
import zipfile


@dataclass(frozen=True)
class SourceRecord:
    path: str
    kind: str
    sha256: str
    text: str
    bindings: list[str] = field(default_factory=list)


@dataclass
class ContentIR:
    sources: list[SourceRecord] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"schema": "xiaopu-content-ir-v1", "sources": [asdict(source) for source in self.sources]}

    def to_model_dict(self, *, max_total_chars: int = 12000) -> dict:
        """Return a compact, source-balanced brief for the model.

        Full extracted text belongs in the run artifact, not in every model
        turn.  A per-source quota prevents one long HTML report from hiding
        the correction notes, bindings, or task contract at the end. The
        returned structure is hard-capped so metadata plus excerpts never
        exceed ``max_total_chars`` characters.
        """
        if not self.sources:
            return {"schema": "xiaopu-content-brief-v1", "sources": []}
        import json as _json

        # Reserve budget for per-source metadata and the envelope itself.
        envelope = 120
        per_source_meta = 140
        available = max(400, max_total_chars - envelope - per_source_meta * len(self.sources))
        quota = max(200, available // len(self.sources))
        sources = []
        for source in self.sources:
            sources.append({
                "path": source.path,
                "kind": source.kind,
                "sha256": source.sha256,
                "excerpt": _salient_excerpt(source.text, quota),
                "bindings": source.bindings,
            })
        brief = {"schema": "xiaopu-content-brief-v1", "sources": sources}
        rendered = _json.dumps(brief, ensure_ascii=False)
        if len(rendered) <= max_total_chars:
            return brief
        # Second pass: shrink excerpts proportionally to respect the hard cap.
        current_len = len(rendered)
        overflow = current_len - max_total_chars
        for item in sources:
            excerpt = item["excerpt"]
            if len(excerpt) <= 400:
                continue
            cut = min(len(excerpt) - 400, overflow // len(sources) + 80)
            if cut <= 0:
                continue
            item["excerpt"] = excerpt[: len(excerpt) - cut] + "\n[excerpt truncated]"
        brief = {"schema": "xiaopu-content-brief-v1", "sources": sources}
        rendered = _json.dumps(brief, ensure_ascii=False)
        if len(rendered) > max_total_chars:
            for item in sources:
                item["bindings"] = []
                item["sha256"] = item["sha256"][:16]
            brief = {"schema": "xiaopu-content-brief-v1", "sources": sources}
            rendered = _json.dumps(brief, ensure_ascii=False)
        if len(rendered) > max_total_chars:
            # Final safety: keep only the first excerpt at a hard budget and
            # mark the rest as present-but-elided.
            kept = []
            budget = max_total_chars - envelope - per_source_meta * len(sources)
            for item in sources:
                if not kept:
                    item["excerpt"] = item["excerpt"][: max(200, budget)]
                    kept.append(item)
                else:
                    item["excerpt"] = "[full text in IR artifact]"
            brief = {"schema": "xiaopu-content-brief-v1", "sources": kept + sources[len(kept):]}
        return brief


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _xml_text(data: bytes) -> str:
    raw = data.decode("utf-8", errors="replace")
    raw = re.sub(r"</(?:w:p|a:p|row|si)>", "\n", raw)
    raw = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"[ \t]+", " ", html.unescape(raw)).strip()


def _salient_excerpt(text: str, limit: int) -> str:
    """Select headings, constraints, metrics and corrections deterministically."""
    text = re.sub(r"[ \t]+", " ", text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    marker = re.compile(
        r"(^#{1,4}\s|^[-*]\s|^\d+[.)、]\s|\d+(?:\.\d+)?%?|"
        r"H-\d+|CH-\d+|M_[A-Z0-9_]+|CN-R\d+-\d+|"
        r"must|required|output|final|forecast|actual|superseded|correction|"
        r"要求|输出|最终|修订|预测|实际|风险|来源|象限|不得|不要)",
        re.IGNORECASE,
    )
    chosen: list[str] = []
    seen: set[str] = set()
    # Preserve the opening task context, then prioritize decision-bearing rows.
    for line in [*lines[:8], *(line for line in lines[8:] if marker.search(line))]:
        normalized = line[:700]
        if normalized in seen:
            continue
        seen.add(normalized)
        chosen.append(normalized)
        rendered = "\n".join(chosen)
        if len(rendered) >= limit:
            return rendered[:limit] + "\n[excerpt truncated]"
    rendered = "\n".join(chosen)
    return rendered[:limit]


def _extract_zip_xml(path: Path, prefixes: tuple[str, ...]) -> str:
    chunks: list[str] = []
    with zipfile.ZipFile(path) as archive:
        for name in sorted(archive.namelist()):
            if name.endswith(".xml") and name.startswith(prefixes):
                text = _xml_text(archive.read(name))
                if text:
                    chunks.append(f"[{name}]\n{text}")
    return "\n\n".join(chunks)


def _extract_xlsx(path: Path) -> str:
    """Extract cell values with sheet names instead of dumping OOXML."""
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rel_ns = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}
    office_rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        shared: list[str] = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.findall("m:si", ns):
                shared.append("".join(node.text or "" for node in item.iter() if node.tag.endswith("}t")))

        rels: dict[str, str] = {}
        if "xl/_rels/workbook.xml.rels" in names:
            root = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
            for rel in root.findall("r:Relationship", rel_ns):
                rels[rel.attrib.get("Id", "")] = rel.attrib.get("Target", "")

        sheets: list[tuple[str, str]] = []
        if "xl/workbook.xml" in names:
            root = ET.fromstring(archive.read("xl/workbook.xml"))
            for sheet in root.findall("m:sheets/m:sheet", ns):
                rid = sheet.attrib.get(f"{{{office_rel}}}id", "")
                target = rels.get(rid, "")
                if target:
                    target = target.lstrip("/")
                    if not target.startswith("xl/"):
                        target = "xl/" + target
                    sheets.append((sheet.attrib.get("name", "Sheet"), target))

        chunks: list[str] = []
        for sheet_name, target in sheets:
            if target not in names:
                continue
            root = ET.fromstring(archive.read(target))
            rows: list[str] = []
            for row in root.findall(".//m:sheetData/m:row", ns):
                values: list[str] = []
                for cell in row.findall("m:c", ns):
                    ref = cell.attrib.get("r", "")
                    cell_type = cell.attrib.get("t", "")
                    value_node = cell.find("m:v", ns)
                    inline = cell.find("m:is", ns)
                    value = value_node.text if value_node is not None and value_node.text is not None else ""
                    if cell_type == "s" and value.isdigit() and int(value) < len(shared):
                        value = shared[int(value)]
                    elif cell_type == "inlineStr" and inline is not None:
                        value = "".join(node.text or "" for node in inline.iter() if node.tag.endswith("}t"))
                    if value:
                        values.append(f"{ref}={value}")
                if values:
                    rows.append(" | ".join(values))
            chunks.append(f"[Sheet: {sheet_name}]\n" + "\n".join(rows))
        return "\n\n".join(chunks)


def _extract_xmind(path: Path) -> str:
    """Extract a readable mind-map summary from an XMind package (a ZIP).

    ``content.json`` carries the topic tree; ``manifest.xml`` and any ``*.txt``
    attachments/notes carry the human-readable material. Images and SVGs are
    intentionally excluded — the harness reads structure and text, not pixels.
    """
    import json as _json

    chunks: list[str] = []
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        if "content.json" in names:
            try:
                payload = _json.loads(archive.read("content.json").decode("utf-8", errors="replace"))
            except Exception:
                payload = None

            def walk(node, depth):
                title = (node or {}).get("title")
                if title:
                    titles.append("  " * depth + str(title))
                children = (node or {}).get("children", [])
                if isinstance(children, dict):
                    children = children.get("attached", []) or []
                for child in children or []:
                    if isinstance(child, dict):
                        walk(child, depth + 1)

            titles: list[str] = []
            if isinstance(payload, list):
                for sheet in payload:
                    walk(sheet.get("rootTopic"), 0)
            elif isinstance(payload, dict) and "workbook" in payload:
                walk(payload["workbook"].get("rootTopic"), 0)
            if titles:
                chunks.append("[mindmap topics]\n" + "\n".join(titles))
            if isinstance(payload, dict):
                comments = payload.get("comments") or []
                if comments:
                    chunks.append("[comments]\n" + "\n".join(
                        f"{c.get('topicRef', '')}: {c.get('text', '')}".strip() for c in comments
                    ))
                cues = payload.get("styleResourceCues")
                if isinstance(cues, dict):
                    chunks.append("[style cues]\n" + _json.dumps(cues, ensure_ascii=False)[:4000])
            elif titles is None and payload is not None:
                chunks.append("[content.json]\n" + str(payload)[:20000])
        if "manifest.xml" in names:
            text = _xml_text(archive.read("manifest.xml"))
            if text:
                chunks.append("[manifest.xml]\n" + text)
        for name in sorted(names):
            if name.endswith(".txt") or name.endswith(".md"):
                try:
                    text = archive.read(name).decode("utf-8", errors="replace").strip()
                except Exception:
                    continue
                if text:
                    chunks.append(f"[{name}]\n{text[:3000]}")
    return "\n\n".join(chunks)


def extract_source(path: Path, *, max_chars: int = 30000) -> SourceRecord:
    suffix = path.suffix.lower()
    kind = suffix.lstrip(".") or "text"
    if suffix in {".md", ".txt", ".json", ".yaml", ".yml"}:
        text = path.read_text(encoding="utf-8", errors="replace")
    elif suffix in {".html", ".htm"}:
        raw = path.read_text(encoding="utf-8", errors="replace")
        raw = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", raw, flags=re.I | re.S)
        raw = re.sub(r"</?(?:h[1-6]|p|li|tr|section|article|aside|blockquote|div|br)[^>]*>", "\n", raw, flags=re.I)
        text = re.sub(r"[ \t]+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw)))
        text = re.sub(r"\n\s*\n+", "\n", text).strip()
    elif suffix == ".csv":
        rows = csv.reader(io.StringIO(path.read_text(encoding="utf-8-sig", errors="replace")))
        text = "\n".join(" | ".join(row) for row in rows)
    elif suffix == ".pptx":
        text = _extract_zip_xml(path, ("ppt/slides/", "ppt/notesSlides/"))
    elif suffix == ".docx":
        text = _extract_zip_xml(path, ("word/",))
    elif suffix == ".xlsx":
        text = _extract_xlsx(path)
    elif suffix == ".xmind":
        text = _extract_xmind(path)
    elif suffix in {".png", ".jpg", ".jpeg", ".gif", ".svg"}:
        # Raster/vector assets are retained for provenance and style reference,
        # but the harness deliberately does not OCR or "understand" pixels.
        text = ""
    else:
        raise ValueError(f"unsupported office source: {suffix or path.name}")
    if len(text) > max_chars:
        text = text[: max_chars * 3 // 4] + f"\n[content truncated: {len(text) - max_chars} chars]\n" + text[-max_chars // 4 :]
    return SourceRecord(str(path), kind, _digest(path), text)


def build_content_ir(paths: list[Path], *, max_chars_per_source: int = 30000) -> ContentIR:
    return ContentIR([extract_source(path, max_chars=max_chars_per_source) for path in paths])


def persist_content_ir(ir: ContentIR, root: Path) -> Path:
    """Persist the complete IR once and return a workspace-local audit path."""
    import json

    full = json.dumps(ir.to_dict(), ensure_ascii=False, indent=2)
    digest = hashlib.sha256(full.encode("utf-8")).hexdigest()[:16]
    target_dir = root / ".xiaopu" / "content_ir"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{digest}.json"
    if not target.exists():
        target.write_text(full, encoding="utf-8")
    return target
