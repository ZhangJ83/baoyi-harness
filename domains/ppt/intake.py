"""PPT source normalization: turn raw inputs into a PresentationSourceIR.

Generic intake (core.intake) registers and hashes files; this layer gives each
kind a domain meaning: deck structure, workbook data, hierarchy, page
structure, visual reference.
"""
from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.intake import SourceRegistration, discover_sources

KIND_MAP = {
    ".pptx": "binary",
    ".xlsx": "binary",
    ".xmind": "binary",
    ".png": "binary",
    ".jpg": "binary",
    ".jpeg": "binary",
    ".webp": "binary",
    ".gif": "binary",
    ".html": "text",
    ".htm": "text",
    ".md": "text",
    ".json": "text",
    ".yaml": "text",
    ".yml": "text",
    ".csv": "text",
    ".txt": "text",
}


@dataclass
class WorkbookSheet:
    name: str
    cells: List[Tuple[str, str]] = field(default_factory=list)  # (cell_ref, text)


@dataclass
class PresentationSourceIR:
    task_dir: Path
    sources: List[SourceRegistration] = field(default_factory=list)
    slide_inventory: List[Dict[str, Any]] = field(default_factory=list)
    sheets: List[WorkbookSheet] = field(default_factory=list)
    hierarchy: List[Tuple[int, str]] = field(default_factory=list)  # (depth, title)
    page_structure: List[Tuple[str, str]] = field(default_factory=list)  # (tag, text)
    visual_refs: List[Path] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"sources={len(self.sources)} slides={len(self.slide_inventory)} "
            f"sheets={len(self.sheets)} nodes={len(self.hierarchy)} pages={len(self.page_structure)} "
            f"visual_refs={len(self.visual_refs)}"
        )


def normalize_pptx(path: Path) -> List[Dict[str, Any]]:
    """Deck -> slide structure inventory."""
    from domains.ppt.ir import from_pptx

    ir = from_pptx(path)
    inventory = []
    for slide in ir.slides:
        inventory.append({
            "index": slide.index,
            "layout": slide.layout,
            "shape_count": len(slide.shapes),
            "text_excerpt": slide.all_text()[:200],
        })
    return inventory


def _xlsx_sheets_stdlib(path: Path) -> List[WorkbookSheet]:
    sheets: List[WorkbookSheet] = []
    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())
        shared: List[str] = []
        if "xl/sharedStrings.xml" in names:
            xml = zf.read("xl/sharedStrings.xml").decode("utf-8", errors="replace")
            shared = re.findall(r"<t[^>]*>(.*?)</t>", xml, flags=re.S)
        wb_xml = ""
        if "xl/workbook.xml" in names:
            wb_xml = zf.read("xl/workbook.xml").decode("utf-8", errors="replace")
        sheet_names = re.findall(r'<sheet[^>]*name="([^"]+)"', wb_xml)
        for name in sheet_names:
            cells: List[Tuple[str, str]] = []
            sheet_path = f"xl/worksheets/sheet{len(sheets) + 1}.xml"
            if sheet_path in names:
                sheet_xml = zf.read(sheet_path).decode("utf-8", errors="replace")
                for ref, idx in re.findall(r'<c r="([A-Z]+[0-9]+)"(?:[^>]*t="(\w+)")?[^>]*>(?:<v>(.*?)</v>)?', sheet_xml):
                    value = idx or ""
                    if idx == "s" and value.isdigit():
                        value = shared[int(value)] if int(value) < len(shared) else value
                    cells.append((ref, value[:200]))
            sheets.append(WorkbookSheet(name=name, cells=cells))
    return sheets


def normalize_xlsx(path: Path) -> List[WorkbookSheet]:
    """Workbook -> sheet + cell data source."""
    try:
        import openpyxl  # noqa: F401

        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        sheets = []
        for ws in wb.worksheets:
            cells = []
            for row in ws.iter_rows(max_row=200):
                for cell in row:
                    if cell.value is not None:
                        cells.append((cell.coordinate, str(cell.value)[:200]))
            sheets.append(WorkbookSheet(name=ws.title, cells=cells))
        return sheets
    except Exception:
        return _xlsx_sheets_stdlib(path)


def _walk_xmind_topics(node: Dict[str, Any], depth: int, out: List[Tuple[int, str]]) -> None:
    title = node.get("title") or node.get("text") or ""
    if title:
        out.append((depth, str(title)[:200]))
    children = node.get("children", {})
    attached = children.get("attached", []) if isinstance(children, dict) else children
    if isinstance(attached, list):
        for child in attached:
            if isinstance(child, dict):
                _walk_xmind_topics(child, depth + 1, out)


def normalize_xmind(path: Path) -> List[Tuple[int, str]]:
    """Mind-map package -> topic hierarchy."""
    out: List[Tuple[int, str]] = []
    with zipfile.ZipFile(path) as zf:
        for name in zf.namelist():
            if name.endswith("content.json"):
                try:
                    data = json.loads(zf.read(name).decode("utf-8", errors="replace"))
                except Exception:
                    continue
                for sheet in data if isinstance(data, list) else [data]:
                    root = sheet.get("rootTopic") if isinstance(sheet, dict) else None
                    if isinstance(root, dict):
                        _walk_xmind_topics(root, 0, out)
    return out


_TAG_RE = re.compile(r"<script.*?</script>|<style.*?</style>", flags=re.S | re.I)
_HEADING_RE = re.compile(r"<(h[1-6])[^>]*>(.*?)</\1>", flags=re.S | re.I)
_STRIP_RE = re.compile(r"<[^>]+>")


def normalize_html(path: Path) -> List[Tuple[str, str]]:
    """Page -> heading structure and visible text."""
    text = path.read_text(encoding="utf-8", errors="replace")
    text = _TAG_RE.sub(" ", text)
    structure: List[Tuple[str, str]] = []
    for tag, body in _HEADING_RE.findall(text):
        structure.append((tag, _STRIP_RE.sub("", body).strip()[:200]))
    if not structure:
        plain = _STRIP_RE.sub(" ", text)
        structure.append(("p", " ".join(plain.split())[:200]))
    return structure


def normalize_image(path: Path) -> Dict[str, Any]:
    """Visual reference: dimensions when the imaging backend is available."""
    info: Dict[str, Any] = {"path": str(path), "role": "visual_reference"}
    try:
        from PIL import Image  # noqa: F401

        with Image.open(path) as img:
            info["size"] = img.size
            info["mode"] = img.mode
    except Exception:
        pass
    return info


def build_presentation_source_ir(task_dir: Path) -> PresentationSourceIR:
    """Discover and normalize every source under a task's input directory."""
    task_dir = Path(task_dir)
    input_dir = task_dir / "input"
    search_dir = input_dir if input_dir.is_dir() else task_dir
    sources = discover_sources(search_dir.rglob("*"), kind_map=KIND_MAP)
    ir = PresentationSourceIR(task_dir=task_dir, sources=sources)
    for reg in sources:
        suffix = reg.path.suffix.lower()
        try:
            if suffix == ".pptx":
                ir.slide_inventory.extend(normalize_pptx(reg.path))
            elif suffix == ".xlsx":
                ir.sheets.extend(normalize_xlsx(reg.path))
            elif suffix == ".xmind":
                ir.hierarchy.extend(normalize_xmind(reg.path))
            elif suffix in (".html", ".htm"):
                ir.page_structure.extend(normalize_html(reg.path))
            elif suffix in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
                info = normalize_image(reg.path)
                if info.get("size"):
                    ir.visual_refs.append(reg.path)
        except Exception:
            # A source that cannot be normalized stays registered but does not
            # break intake of the remaining sources.
            continue
    return ir
