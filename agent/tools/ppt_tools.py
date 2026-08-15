"""PPT tools: build, edit, verify a deck with python-pptx.

Deck state lives on the harness (`h.deck`), so tools compose across calls.
Visual layout: a minimal editorial theme — title band, low-contrast body,
an accent underline — built from plain shapes (no templates / no external assets).
"""
import math
import json
import platform
import shutil
import subprocess
from copy import deepcopy
from io import BytesIO
from types import SimpleNamespace
from typing import Any, Callable

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, MSO_SHAPE_TYPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

Schema = dict[str, Any]

# --- theme ---
_PRIMARY = RGBColor(0x1F, 0x38, 0x64)   # deep navy
_ACCENT = RGBColor(0xF0, 0x9A, 0x1A)    # amber
_TEXT = RGBColor(0x2B, 0x2B, 0x2B)
_MUTED = RGBColor(0x87, 0x87, 0x87)
_BG = RGBColor(0xFB, 0xFA, 0xF7)        # warm paper
_WHITE = RGBColor(0xFF, 0xFF, 0xFF)
_HEAD = RGBColor(0x25, 0x47, 0x7C)      # lighter navy for content titles

_W = 13.333
_H = 7.5


def _schema(name: str, description: str, params: dict[str, dict], required: list[str]):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": params, "required": required, "additionalProperties": False},
        },
    }


def _deck(h: Any) -> Presentation:
    if getattr(h, "deck", None) is None:
        h.deck = Presentation()
        h.deck.slide_width = Inches(_W)
        h.deck.slide_height = Inches(_H)
    return h.deck


def _open_deck(h, path: str) -> str:
    from .. import config
    from ..permissions import path_within
    root = config.sandbox_root()
    source = (root / path).resolve()
    if not path_within(root, source):
        raise PermissionError("presentation path escapes workspace")
    if not source.exists():
        raise FileNotFoundError(
            f"{path} (no such presentation; if this is a create-from-scratch task, call new_deck instead of ppt_open)"
        )
    opened = source
    if getattr(h, "recorder", None):
        opened = h.recorder.working_copy(source)
    h.deck = Presentation(str(opened))
    h.deck_source_path = source
    h.deck_working_path = opened
    if getattr(h, "state", None) is not None:
        h.state.active_artifact = str(opened)
        h.state.ppt_existing_deck = True
        h.state.ppt_affected_slides.clear()
        baseline = _collect_structural_findings(h)
        h.state.ppt_baseline_findings = {item["key"]: item["severity"] for item in baseline}
        h.state.ppt_baseline_captured = True
        h.state.record_fact("ppt_source", str(source))
        h.state.record_fact("ppt_working_artifact", str(opened))
        h.state.record_fact(
            "ppt_structural_baseline",
            f"{len(baseline)} finding(s) frozen across {len(h.deck.slides)} source slides",
        )
    return f"opened editable working copy of {path}; original preserved: {len(h.deck.slides)} slides, {h.deck.slide_width / 914400:.2f}x{h.deck.slide_height / 914400:.2f}in"


def _blank_slide(prs: Presentation):
    layouts = prs.slide_layouts
    # Prefer the conventional blank layout (index 6), but minimal templates may
    # expose fewer layouts. Fall back to the first available layout instead of
    # crashing on a deck whose layout table is shorter than the default.
    index = 6 if len(layouts) > 6 else 0
    return prs.slides.add_slide(layouts[index])


def _rect(slide, x: float, y: float, w: float, h: float, fill, line=None) -> "Shape":
    """Full-bleed helper: plain rectangle with a solid fill."""
    sp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    sp.fill.solid()
    sp.fill.fore_color.rgb = fill
    if line is None:
        sp.line.fill.background()
    else:
        sp.line.color.rgb = line
        sp.line.width = Pt(1)
    sp.shadow.inherit = False
    return sp


def _style_run(run, size: int, bold: bool, color: RGBColor) -> None:
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.name = "Microsoft YaHei"


def _fit_lines(tf, lines, size: int, bold: bool, color: RGBColor, space: float = 1.25) -> None:
    tf.clear()
    tf.word_wrap = True
    tf.margin_left = 0
    tf.margin_top = 0
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.line_spacing = space
        run = p.add_run()
        run.text = line
        _style_run(run, size, bold, color)


def _put_lines(tf, text: str, size: int, bold: bool, color: RGBColor = _TEXT) -> None:
    _fit_lines(tf, text.split("\n"), size, bold, color)


def _new_deck(h, title: str, subtitle: str) -> str:
    # A "new deck" is a fresh 16:9 presentation, never an append to whatever
    # template the intake pre-opened. Reusing the open deck here silently
    # turned template-driven tasks into template-editing tasks and polluted the
    # structural check with the template's background shapes.
    prs = Presentation()
    prs.slide_width = Inches(_W)
    prs.slide_height = Inches(_H)
    h.deck = prs
    if getattr(h, "state", None) is not None:
        h.state.ppt_existing_deck = False
        h.state.ppt_baseline_captured = False
        h.state.ppt_baseline_findings.clear()
        h.state.ppt_affected_slides.clear()
    s = _blank_slide(prs)
    # warm paper background
    _rect(s, 0, 0, _W, _H, _BG)
    # left accent bar
    _rect(s, 0, 0, 0.25, _H, _ACCENT)
    # eyebrow
    tb = s.shapes.add_textbox(Inches(1.1), Inches(1.3), Inches(11), Inches(0.5))
    _fit_lines(tb.text_frame, ["P R E S E N T A T I O N"], 15, True, _ACCENT)
    # title (auto-shrink long titles)
    size = 44 if len(title) <= 16 else 36 if len(title) <= 24 else 30
    tb = s.shapes.add_textbox(Inches(1.1), Inches(2.1), Inches(11), Inches(2.4))
    _fit_lines(tb.text_frame, [title], size, True, _PRIMARY)
    # accent underline
    _rect(s, 1.15, 4.35, 1.4, 0.06, _ACCENT)
    if subtitle:
        tb = s.shapes.add_textbox(Inches(1.1), Inches(4.6), Inches(11), Inches(1.2))
        _fit_lines(tb.text_frame, subtitle.split("\n"), 18, False, _MUTED)
    return "new deck created: 16:9, one cover slide."


def _content_slide(h, title: str, bullets: list[str], size: int) -> str:
    prs = _deck(h)
    s = _blank_slide(prs)
    _rect(s, 0, 0, _W, _H, _BG)
    # header band
    _rect(s, 0, 0, _W, 1.1, _HEAD)
    _rect(s, 0, 1.1, _W, 0.07, _ACCENT)
    tb = s.shapes.add_textbox(Inches(0.55), Inches(0.12), Inches(12.2), Inches(0.9))
    _put_lines(tb.text_frame, title, 26, True, _WHITE)
    if bullets:
        tb2 = s.shapes.add_textbox(Inches(0.9), Inches(1.7), Inches(11.5), Inches(5.2))
        body = [f"•  {b}" for b in bullets]
        _fit_lines(tb2.text_frame, body, size, False, _TEXT)
    return f"added slide {len(prs.slides)}: '{title}' ({len(bullets)} bullets)"


def _two_column(h, title: str, left_title: str, left: list[str], right_title: str, right: list[str]) -> str:
    prs = _deck(h)
    s = _blank_slide(prs)
    _rect(s, 0, 0, _W, _H, _BG)
    _rect(s, 0, 0, _W, 1.1, _HEAD)
    _rect(s, 0, 1.1, _W, 0.07, _ACCENT)
    title_box = s.shapes.add_textbox(Inches(0.55), Inches(0.12), Inches(12.2), Inches(0.9))
    _put_lines(title_box.text_frame, title, 26, True, _WHITE)
    for x, heading, bullets in ((0.7, left_title, left), (6.85, right_title, right)):
        card = _rect(s, x, 1.6, 5.75, 5.1, _WHITE, RGBColor(0xDD, 0xDD, 0xD8))
        heading_box = s.shapes.add_textbox(Inches(x + 0.35), Inches(1.9), Inches(5.05), Inches(0.65))
        _put_lines(heading_box.text_frame, heading, 20, True, _PRIMARY)
        body = s.shapes.add_textbox(Inches(x + 0.35), Inches(2.75), Inches(5.05), Inches(3.55))
        _fit_lines(body.text_frame, [f"•  {item}" for item in bullets], 17, False, _TEXT, 1.2)
    return f"added two-column slide {len(prs.slides)}: '{title}'"


def _quadrant_slide(h, title: str, subtitle: str, quadrants: list[dict], slide_number: int | None = None) -> str:
    """Create a complete executive four-quadrant page in one semantic action.

    This deliberately sits above primitive textbox calls: the model decides
    the content and evidence mapping, while the harness owns spacing,
    typography, source chips and notes provenance.
    """
    if len(quadrants) != 4:
        raise ValueError("quadrant slide requires exactly four quadrants")
    prs = _deck(h)
    if slide_number is None:
        slide = _blank_slide(prs)
        target = len(prs.slides)
    else:
        if not 1 <= slide_number <= len(prs.slides):
            raise ValueError("slide_number is out of range")
        slide = prs.slides[slide_number - 1]
        target = slide_number
        for shape in list(slide.shapes):
            shape._element.getparent().remove(shape._element)

    # Predominantly black and white, with one restrained amber signal color.
    _rect(slide, 0, 0, _W, _H, _WHITE)
    _rect(slide, 0, 0, _W, 0.92, RGBColor(0x12, 0x12, 0x12))
    heading = slide.shapes.add_textbox(Inches(0.48), Inches(0.16), Inches(9.8), Inches(0.52))
    _put_lines(heading.text_frame, title, 25, True, _WHITE)
    if subtitle:
        sub = slide.shapes.add_textbox(Inches(10.15), Inches(0.20), Inches(2.7), Inches(0.4))
        _put_lines(sub.text_frame, subtitle, 11, False, RGBColor(0xD0, 0xD0, 0xD0))

    positions = ((0.48, 1.18), (6.83, 1.18), (0.48, 4.12), (6.83, 4.12))
    sources: list[str] = []
    for index, (item, (x, y)) in enumerate(zip(quadrants, positions), 1):
        card = _rect(slide, x, y, 6.02, 2.58, _WHITE, RGBColor(0xC8, 0xC8, 0xC8))
        card.line.width = Pt(1.1)
        _rect(slide, x, y, 0.08, 2.58, _ACCENT)
        qlabel = slide.shapes.add_textbox(Inches(x + 0.25), Inches(y + 0.18), Inches(0.55), Inches(0.32))
        _put_lines(qlabel.text_frame, f"Q{index}", 11, True, _MUTED)
        # Reserve a stable metric column instead of letting the model repair
        # title/metric collisions shape by shape after verification.
        qtitle = slide.shapes.add_textbox(Inches(x + 0.82), Inches(y + 0.13), Inches(2.95), Inches(0.45))
        _put_lines(qtitle.text_frame, str(item.get("title", "")), 16, True, RGBColor(0x16, 0x16, 0x16))
        metric = str(item.get("metric", "")).strip()
        if metric:
            metric_box = slide.shapes.add_textbox(Inches(x + 3.85), Inches(y + 0.10), Inches(1.85), Inches(0.48))
            metric_box.text_frame.paragraphs[0].alignment = PP_ALIGN.RIGHT
            _put_lines(metric_box.text_frame, metric, 18, True, RGBColor(0x16, 0x16, 0x16))
        bullets = [str(value).strip() for value in item.get("bullets", []) if str(value).strip()][:3]
        detail = str(item.get("detail", "")).strip()
        lines = ([detail] if detail else []) + [f"• {value}" for value in bullets]
        body = slide.shapes.add_textbox(Inches(x + 0.28), Inches(y + 0.72), Inches(5.42), Inches(1.42))
        _fit_lines(body.text_frame, lines, 11, False, _TEXT, 1.08)
        source = str(item.get("source", "")).strip()
        if source:
            sources.append(f"Q{index}: {source}")
            chip = slide.shapes.add_textbox(Inches(x + 0.28), Inches(y + 2.19), Inches(5.35), Inches(0.22))
            _put_lines(chip.text_frame, source, 8, False, _MUTED)
            try:
                chip.name = f"Q{index}_provenance_{source[:36]}"
            except (AttributeError, ValueError):
                pass
    if sources:
        _set_speaker_notes(h, target, "[Sources]\n" + "\n".join(sources))
    return f"composed executive quadrant slide {target}: '{title}' with 4 provenance-bound quadrants"


def _metric_slide(h, title: str, metrics: list[dict], takeaway: str = "") -> str:
    if not 1 <= len(metrics) <= 4:
        raise ValueError("metric slide requires 1-4 metrics")
    prs = _deck(h)
    s = _blank_slide(prs)
    _rect(s, 0, 0, _W, _H, _PRIMARY)
    title_box = s.shapes.add_textbox(Inches(0.75), Inches(0.55), Inches(11.8), Inches(0.75))
    _put_lines(title_box.text_frame, title, 28, True, _WHITE)
    gap = 0.25
    card_w = (11.85 - gap * (len(metrics) - 1)) / len(metrics)
    for index, metric in enumerate(metrics):
        x = 0.75 + index * (card_w + gap)
        _rect(s, x, 1.75, card_w, 3.45, _WHITE)
        value_box = s.shapes.add_textbox(Inches(x + 0.25), Inches(2.15), Inches(card_w - 0.5), Inches(1.05))
        _put_lines(value_box.text_frame, str(metric.get("value", "—")), 32, True, _ACCENT)
        label_box = s.shapes.add_textbox(Inches(x + 0.25), Inches(3.3), Inches(card_w - 0.5), Inches(0.7))
        _put_lines(label_box.text_frame, str(metric.get("label", "")), 17, True, _PRIMARY)
        detail_box = s.shapes.add_textbox(Inches(x + 0.25), Inches(4.15), Inches(card_w - 0.5), Inches(0.7))
        _put_lines(detail_box.text_frame, str(metric.get("detail", "")), 13, False, _MUTED)
    if takeaway:
        note = s.shapes.add_textbox(Inches(0.85), Inches(5.75), Inches(11.65), Inches(0.85))
        _put_lines(note.text_frame, takeaway, 18, False, _WHITE)
    return f"added metric slide {len(prs.slides)}: '{title}'"


def _table_slide(h, title: str, columns: list[str], rows: list[list[str]]) -> str:
    if not columns or len(columns) > 6:
        raise ValueError("table requires 1-6 columns")
    if not rows or len(rows) > 10:
        raise ValueError("table requires 1-10 rows")
    if any(len(row) != len(columns) for row in rows):
        raise ValueError("every row must match the column count")
    prs = _deck(h)
    s = _blank_slide(prs)
    _rect(s, 0, 0, _W, _H, _BG)
    _rect(s, 0, 0, _W, 1.1, _HEAD)
    _rect(s, 0, 1.1, _W, 0.07, _ACCENT)
    title_box = s.shapes.add_textbox(Inches(0.55), Inches(0.12), Inches(12.2), Inches(0.9))
    _put_lines(title_box.text_frame, title, 26, True, _WHITE)
    table_shape = s.shapes.add_table(len(rows) + 1, len(columns), Inches(0.65), Inches(1.55), Inches(12.0), Inches(5.35))
    table = table_shape.table
    for col_index, label in enumerate(columns):
        cell = table.cell(0, col_index)
        cell.text = label
        cell.fill.solid()
        cell.fill.fore_color.rgb = _PRIMARY
    for row_index, row in enumerate(rows, 1):
        for col_index, value in enumerate(row):
            cell = table.cell(row_index, col_index)
            cell.text = str(value)
            cell.fill.solid()
            cell.fill.fore_color.rgb = _WHITE if row_index % 2 else RGBColor(0xF1, 0xF0, 0xEC)
    for table_row_index, row in enumerate(table.rows):
        for cell in row.cells:
            cell.margin_left = Inches(0.1)
            cell.margin_right = Inches(0.1)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            for paragraph in cell.text_frame.paragraphs:
                paragraph.alignment = PP_ALIGN.LEFT
                for run in paragraph.runs:
                    _style_run(run, 13, table_row_index == 0, _WHITE if table_row_index == 0 else _TEXT)
    return f"added table slide {len(prs.slides)}: '{title}' ({len(rows)} rows)"


def _process_slide(h, title: str, steps: list[dict], takeaway: str = "") -> str:
    if not 3 <= len(steps) <= 5:
        raise ValueError("process slide requires 3-5 steps")
    prs = _deck(h)
    s = _blank_slide(prs)
    _rect(s, 0, 0, _W, _H, _BG)
    title_box = s.shapes.add_textbox(Inches(0.7), Inches(0.45), Inches(12), Inches(0.7))
    _put_lines(title_box.text_frame, title, 28, True, _PRIMARY)
    start_x, y, total_w = 0.75, 1.65, 11.85
    gap = 0.18
    step_w = (total_w - gap * (len(steps) - 1)) / len(steps)
    for index, step in enumerate(steps, 1):
        x = start_x + (index - 1) * (step_w + gap)
        _rect(s, x, y, step_w, 3.7, _WHITE, RGBColor(0xDD, 0xDD, 0xD8))
        badge = _rect(s, x + 0.25, y + 0.3, 0.52, 0.52, _ACCENT)
        badge.text_frame.clear()
        badge.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        paragraph = badge.text_frame.paragraphs[0]
        paragraph.alignment = PP_ALIGN.CENTER
        run = paragraph.add_run()
        run.text = str(index)
        _style_run(run, 14, True, _WHITE)
        heading = s.shapes.add_textbox(Inches(x + 0.25), Inches(y + 1.15), Inches(step_w - 0.5), Inches(0.75))
        _put_lines(heading.text_frame, str(step.get("title", "")), 19, True, _PRIMARY)
        detail = s.shapes.add_textbox(Inches(x + 0.25), Inches(y + 2.05), Inches(step_w - 0.5), Inches(1.15))
        _put_lines(detail.text_frame, str(step.get("detail", "")), 14, False, _TEXT)
    if takeaway:
        note = s.shapes.add_textbox(Inches(0.85), Inches(5.85), Inches(11.6), Inches(0.75))
        _put_lines(note.text_frame, takeaway, 18, True, _PRIMARY)
    return f"added process slide {len(prs.slides)}: '{title}'"


def _image_slide(h, title: str, image_path: str, caption: str = "") -> str:
    from .. import config
    from ..permissions import path_within
    root = config.sandbox_root().resolve()
    source = (root / image_path).resolve()
    if not path_within(root, source) or not source.is_file():
        raise FileNotFoundError(image_path)
    prs = _deck(h)
    s = _blank_slide(prs)
    _rect(s, 0, 0, _W, _H, _BG)
    title_box = s.shapes.add_textbox(Inches(0.7), Inches(0.35), Inches(12), Inches(0.7))
    _put_lines(title_box.text_frame, title, 27, True, _PRIMARY)
    from PIL import Image
    with Image.open(source) as image:
        ratio = image.width / image.height
    max_w, max_h = 11.7, 5.35
    width = min(max_w, max_h * ratio)
    height = width / ratio
    x = (_W - width) / 2
    y = 1.25 + (max_h - height) / 2
    s.shapes.add_picture(str(source), Inches(x), Inches(y), width=Inches(width), height=Inches(height))
    if caption:
        caption_box = s.shapes.add_textbox(Inches(0.9), Inches(6.8), Inches(11.5), Inches(0.4))
        _put_lines(caption_box.text_frame, caption, 11, False, _MUTED)
    return f"added image slide {len(prs.slides)}: '{title}'"


def _walk_shapes(shapes, parent_path: tuple[int, ...] = ()):
    """Yield every shape in visual-tree order, including nested group members.

    PowerPoint stores child geometry in the coordinate system of its parent
    group.  The path lets callers identify that context without incorrectly
    presenting a nested shape's ``left``/``top`` as slide-absolute values.
    """
    for shape in shapes:
        path = parent_path + (shape.shape_id,)
        yield shape, path
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from _walk_shapes(shape.shapes, path)


def _shape_inventory(h, slide_number: int | None = None) -> str:
    if getattr(h, "deck", None) is None:
        return "no deck yet."
    selected = range(len(h.deck.slides)) if slide_number is None else [slide_number - 1]
    lines = []
    for index in selected:
        if index < 0 or index >= len(h.deck.slides):
            raise IndexError(f"slide number out of range: {slide_number}")
        for shape, path in _walk_shapes(h.deck.slides[index].shapes):
            text = shape.text.strip().replace("\n", " | ")[:100] if getattr(shape, "has_text_frame", False) else ""
            path_label = "/".join(str(shape_id) for shape_id in path)
            geometry_label = "box_slide" if len(path) == 1 else "box_group_local"
            kind = "group" if shape.shape_type == MSO_SHAPE_TYPE.GROUP else "shape"
            lines.append(
                f"slide={index + 1} path={path_label} id={shape.shape_id} kind={kind} name={shape.name!r} "
                f"{geometry_label}=({shape.left/914400:.2f},{shape.top/914400:.2f},"
                f"{shape.width/914400:.2f},{shape.height/914400:.2f}) text={text!r}"
            )
    return "\n".join(lines)


def _replace_text(h, slide_number: int, shape_id: int, text: str) -> str:
    if getattr(h, "deck", None) is None:
        raise ValueError("no deck loaded")
    if slide_number < 1 or slide_number > len(h.deck.slides):
        raise IndexError("slide number out of range")
    _, shape = _find_shape(h, slide_number, shape_id)
    if not shape.has_text_frame:
        raise TypeError("target shape has no text frame")
    style = None
    for paragraph in shape.text_frame.paragraphs:
        if paragraph.runs:
            run = paragraph.runs[0]
            try:
                rgb = run.font.color.rgb
            except (AttributeError, ValueError):
                rgb = None
            style = (run.font.size, run.font.bold, run.font.name, rgb)
            break
    shape.text_frame.text = text
    if style and shape.text_frame.paragraphs[0].runs:
        run = shape.text_frame.paragraphs[0].runs[0]
        run.font.size, run.font.bold, run.font.name = style[:3]
        if style[3] is not None:
            run.font.color.rgb = style[3]
    h.state.record_change(f"deck:slide:{slide_number}:shape:{shape_id}:text")
    return f"updated slide {slide_number} shape {shape_id}"


def _replace_text_semantic(h, old: str, new: str, slide_number: int | None = None, match_case: bool = True) -> str:
    """Replace text even when a match spans multiple runs.

    The first run keeps the paragraph's dominant style. This is more faithful
    than rebuilding the whole text frame and is deterministic for benchmark
    edits such as a title split into ``Lecture `` and ``3`` runs.
    """
    if not old:
        raise ValueError("old text cannot be empty")
    if getattr(h, "deck", None) is None:
        raise ValueError("no deck loaded")
    indices = range(len(h.deck.slides)) if slide_number is None else [slide_number - 1]
    replacements = 0
    touched: list[str] = []
    for index in indices:
        if index < 0 or index >= len(h.deck.slides):
            raise IndexError("slide number out of range")
        for shape, _ in _walk_shapes(h.deck.slides[index].shapes):
            if not getattr(shape, "has_text_frame", False):
                continue
            for paragraph in shape.text_frame.paragraphs:
                runs = list(paragraph.runs)
                if not runs:
                    continue

                # Build the searchable paragraph text in XML order.  A soft
                # line break is represented by ``a:br`` (``\v`` in the public
                # paragraph text), not by a run, so keep it as an immutable
                # separator instead of flattening the runs.
                parts: list[str] = []
                run_index = 0
                for child in paragraph._p.content_children:
                    kind = child.tag.rsplit("}", 1)[-1]
                    if kind == "r":
                        parts.append(runs[run_index].text)
                        run_index += 1
                    elif kind == "br":
                        parts.append("\v")
                    else:
                        # Do not let a semantic match cross an unsupported
                        # field or other non-run paragraph child.
                        parts.append("\ufffc")
                combined = "".join(parts)

                import re
                flags = 0 if match_case else re.IGNORECASE
                matches = [
                    match.span()
                    for match in re.finditer(re.escape(old), combined, flags=flags)
                    if "\v" not in match.group(0) and "\ufffc" not in match.group(0)
                ]
                if not matches:
                    continue

                # Work from right to left.  Later replacements cannot shift
                # the coordinates of an earlier match, while rebuilding the
                # run map after each edit preserves all existing run elements,
                # their formatting, and every a:br node.
                for start, end in reversed(matches):
                    cursor = 0
                    segments = []
                    run_index = 0
                    for child in paragraph._p.content_children:
                        kind = child.tag.rsplit("}", 1)[-1]
                        if kind == "r":
                            run = list(paragraph.runs)[run_index]
                            run_index += 1
                            segment_end = cursor + len(run.text)
                            segments.append((run, cursor, segment_end))
                            cursor = segment_end
                        elif kind == "br":
                            cursor += 1
                        else:
                            cursor += 1

                    affected = [
                        (run, segment_start, segment_end)
                        for run, segment_start, segment_end in segments
                        if segment_start < end and segment_end > start
                    ]
                    if not affected:
                        continue

                    replacement_offset = 0
                    for affected_index, (run, segment_start, segment_end) in enumerate(affected):
                        overlap_start = max(start, segment_start)
                        overlap_end = min(end, segment_end)
                        quota = overlap_end - overlap_start
                        is_first = affected_index == 0
                        is_last = affected_index == len(affected) - 1
                        if is_last:
                            chunk = new[replacement_offset:]
                        else:
                            chunk = new[replacement_offset:replacement_offset + quota]
                        replacement_offset += len(chunk)
                        prefix = run.text[:overlap_start - segment_start] if is_first else ""
                        suffix = run.text[overlap_end - segment_start:] if is_last else ""
                        run.text = prefix + chunk + suffix

                replacements += len(matches)
                touched.append(f"{index + 1}:{shape.shape_id}")
    if not replacements:
        raise ValueError(f"text not found: {old!r}")
    h.state.ppt_affected_slides.update(int(item.split(":", 1)[0]) for item in touched)
    h.state.record_change("deck:semantic_text_replace:" + ",".join(touched))
    return f"replaced {replacements} occurrence(s) in {len(set(touched))} shape(s): {', '.join(touched)}"


def _target_text_shape(h, slide_number: int, shape_id: int | None = None, text_contains: str = ""):
    slide, explicit = (None, None)
    if shape_id is not None:
        return _find_shape(h, slide_number, shape_id)
    if slide_number < 1 or slide_number > len(h.deck.slides):
        raise IndexError("slide number out of range")
    slide = h.deck.slides[slide_number - 1]
    candidates = [shape for shape, _ in _walk_shapes(slide.shapes) if getattr(shape, "has_text_frame", False)]
    if text_contains:
        candidates = [shape for shape in candidates if text_contains.casefold() in shape.text.casefold()]
    if not candidates:
        raise ValueError("no matching text shape")
    # Prefer the body/list shape over a short title box.
    target = max(candidates, key=lambda shape: (len(shape.text_frame.paragraphs), len(shape.text), shape.height))
    return slide, target


def _append_bullet(h, slide_number: int, text: str, shape_id: int | None = None, text_contains: str = "") -> str:
    if getattr(h, "deck", None) is None:
        raise ValueError("no deck loaded")
    _, shape = _target_text_shape(h, slide_number, shape_id, text_contains)
    if not shape.has_text_frame:
        raise TypeError("target shape has no text frame")
    paragraphs = list(shape.text_frame.paragraphs)
    template = paragraphs[-1]
    anchor_index = len(paragraphs) - 1
    if text_contains:
        matches = [
            (index, candidate)
            for index, candidate in enumerate(paragraphs)
            if text_contains.casefold() in candidate.text.casefold()
        ]
        if not matches:
            raise ValueError(f"anchor paragraph not found: {text_contains!r}")
        anchor_index, template = matches[-1]
    paragraph = shape.text_frame.add_paragraph()
    if template._p.pPr is not None:
        paragraph._p.insert(0, deepcopy(template._p.pPr))
    paragraph.level = template.level
    # Insert after the anchor's child bullet subtree but before the next peer.
    # add_paragraph() initially appends at the end; moving the XML element
    # preserves the paragraph object and formatting we just constructed.
    insertion_index = anchor_index
    for index in range(anchor_index + 1, len(paragraphs)):
        if paragraphs[index].level <= template.level:
            break
        insertion_index = index
    paragraphs[insertion_index]._p.addnext(paragraph._p)
    run = paragraph.add_run()
    run.text = text
    if template.runs:
        source = template.runs[0]
        run.font.size = source.font.size
        run.font.bold = source.font.bold
        run.font.italic = source.font.italic
        run.font.name = source.font.name
        try:
            if source.font.color.rgb is not None:
                run.font.color.rgb = source.font.color.rgb
        except (AttributeError, ValueError):
            pass
    h.state.record_change(f"deck:slide:{slide_number}:shape:{shape.shape_id}:append_bullet")
    return (
        f"appended peer bullet on slide {slide_number} shape {shape.shape_id} "
        f"at level {paragraph.level} after anchor {text_contains!r}"
    )


def _set_text_style(h, slide_number: int, shape_id: int | None = None, text_contains: str = "", size: int | None = None, color: str | None = None, bold: bool | None = None) -> str:
    _, shape = _target_text_shape(h, slide_number, shape_id, text_contains)
    if size is None and color is None and bold is None:
        raise ValueError("provide at least one style property")
    rgb = RGBColor.from_string(color.lstrip("#").upper()) if color else None
    runs = 0
    for paragraph in shape.text_frame.paragraphs:
        for run in paragraph.runs:
            if size is not None:
                run.font.size = Pt(size)
            if rgb is not None:
                run.font.color.rgb = rgb
            if bold is not None:
                run.font.bold = bold
            runs += 1
    h.state.record_change(f"deck:slide:{slide_number}:shape:{shape.shape_id}:text_style")
    return f"updated style on {runs} run(s), slide {slide_number} shape {shape.shape_id}"


def _set_shape_fill(h, slide_number: int, color: str, shape_id: int | None = None, text_contains: str = "") -> str:
    _, shape = _target_text_shape(h, slide_number, shape_id, text_contains)
    shape.fill.solid()
    shape.fill.fore_color.rgb = RGBColor.from_string(color.lstrip("#").upper())
    h.state.record_change(f"deck:slide:{slide_number}:shape:{shape.shape_id}:fill")
    return f"updated fill on slide {slide_number} shape {shape.shape_id}"


def _add_textbox_to_slide(h, slide_number: int, box: dict) -> str:
    if getattr(h, "deck", None) is None:
        raise ValueError("no deck loaded")
    if slide_number < 1 or slide_number > len(h.deck.slides):
        raise IndexError("slide number out of range")
    tb = h.deck.slides[slide_number - 1].shapes.add_textbox(
        Inches(box["x"]), Inches(box["y"]), Inches(box["w"]), Inches(box["h"])
    )
    _fit_lines(tb.text_frame, str(box.get("text", "")).split("\n"), box.get("size", 18), box.get("bold", False), _TEXT)
    h.state.record_change(f"deck:slide:{slide_number}:textbox:{tb.shape_id}")
    return f"added text box to slide {slide_number}, shape {tb.shape_id}"


def _add_flowchart(h, slide_number: int, nodes: list[str], title: str = "") -> str:
    if getattr(h, "deck", None) is None:
        raise ValueError("no deck loaded")
    if slide_number < 1 or slide_number > len(h.deck.slides):
        raise IndexError("slide number out of range")
    if not 3 <= len(nodes) <= 5:
        raise ValueError("flowchart requires 3-5 nodes")
    slide = h.deck.slides[slide_number - 1]
    if title:
        title_box = slide.shapes.add_textbox(Inches(0.7), Inches(0.35), Inches(12), Inches(0.55))
        _put_lines(title_box.text_frame, title, 24, True, _PRIMARY)
    margin, gap, y, height = 0.75, 0.28, 3.0, 1.0
    arrow_w = 0.42
    node_w = (_W - 2 * margin - (len(nodes) - 1) * (gap + arrow_w)) / len(nodes)
    for index, label in enumerate(nodes):
        x = margin + index * (node_w + gap + arrow_w)
        node = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(node_w), Inches(height))
        node.fill.solid(); node.fill.fore_color.rgb = _WHITE
        node.line.color.rgb = _PRIMARY
        _put_lines(node.text_frame, label, 15, True, _PRIMARY)
        if index < len(nodes) - 1:
            arrow = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x + node_w + gap / 2), Inches(y + 0.31), Inches(arrow_w), Inches(0.38))
            arrow.fill.solid(); arrow.fill.fore_color.rgb = _ACCENT
            arrow.line.fill.background()
    h.state.record_change(f"deck:slide:{slide_number}:flowchart")
    return f"added {len(nodes)}-node flowchart to slide {slide_number}"


# --- compact model-facing facade -------------------------------------------------

def _ppt_inspect(h, detail: str = "summary", slide_number: int | None = None) -> str:
    if getattr(h, "deck", None) is None:
        known = getattr(getattr(h, "state", None), "facts", {}).get("ppt_input_deck", "")
        suffix = f" The discovered input is '{known}'." if known else ""
        raise RuntimeError(f"no active deck; open a real task-local PPTX before inspection.{suffix}")
    if detail == "summary":
        return _deck_info(h)
    return _shape_inventory(h, slide_number)


def _validate_batch_update(update: dict, index: int) -> None:
    """Validate operation-specific fields before starting an atomic batch."""
    operation = update["operation"]
    if operation == "replace":
        if not update.get("old"):
            raise ValueError(f"updates[{index}] replace requires non-empty old text")
        if "new" not in update:
            raise ValueError(f"updates[{index}] replace requires new text")
        return
    if operation != "style":
        raise ValueError(f"updates[{index}] has unsupported operation: {operation!r}")
    if update.get("slide_number") is None:
        raise ValueError(f"updates[{index}] style requires slide_number")
    if update.get("shape_id") is None and not update.get("text_contains"):
        raise ValueError(f"updates[{index}] style requires shape_id or text_contains")
    if update.get("all_matches") and (not update.get("text_contains") or update.get("shape_id") is not None):
        raise ValueError(f"updates[{index}] all_matches requires text_contains and no shape_id")
    target = update.get("target", "text")
    if target == "fill":
        if not update.get("color"):
            raise ValueError(f"updates[{index}] fill style requires color")
    elif all(update.get(name) is None for name in ("size", "color", "bold")):
        raise ValueError(f"updates[{index}] text style requires size, color, or bold")


def _ppt_batch_updates(h, updates: list[dict]) -> str:
    """Apply many independent text changes as one all-or-nothing mutation.

    Work happens against a deep-copied presentation and state.  The live deck
    is swapped only after every item succeeds, and the real RunState receives
    one merged change record so a large spreadsheet-driven update consumes one
    mutation epoch instead of one epoch per cell.
    """
    if getattr(h, "deck", None) is None:
        raise ValueError("no deck loaded")
    if not updates:
        raise ValueError("batch_updates requires at least one update")
    for index, update in enumerate(updates):
        _validate_batch_update(update, index)

    transaction_buffer = BytesIO()
    h.deck.save(transaction_buffer)
    transaction_buffer.seek(0)
    tx = SimpleNamespace(deck=Presentation(transaction_buffer), state=deepcopy(h.state))
    # Track this transaction's scope independently from earlier edits.
    tx.state.ppt_affected_slides = set()
    results: list[str] = []
    for update in updates:
        if update["operation"] == "replace":
            results.append(_replace_text_semantic(
                tx,
                update["old"],
                update["new"],
                update.get("slide_number"),
                update.get("match_case", True),
            ))
            continue
        results.append(_ppt_style(
            tx,
            slide_number=update["slide_number"],
            target=update.get("target", "text"),
            shape_id=update.get("shape_id"),
            text_contains=update.get("text_contains", ""),
            size=update.get("size"),
            color=update.get("color"),
            bold=update.get("bold"),
            all_matches=update.get("all_matches", False),
        ))

    affected = set(tx.state.ppt_affected_slides)
    h.deck = tx.deck
    h.state.ppt_affected_slides.update(affected)
    paths = [f"deck:slide:{slide}:batch_update" for slide in sorted(affected)]
    h.state.record_changes(paths or ["deck:batch_update"])
    return f"applied {len(updates)} updates atomically across {len(affected)} slide(s): " + "; ".join(results)


def _ppt_edit_text(h, operation: str, slide_number: int | None = None, shape_id: int | None = None,
                   text_contains: str = "", old: str = "", new: str = "", text: str = "",
                   match_case: bool = True, all_matches: bool = False, updates: list[dict] | None = None) -> str:
    if operation == "batch_updates":
        return _ppt_batch_updates(h, updates or [])
    if operation == "replace":
        if not old:
            raise ValueError("replace requires non-empty old text")
        return _replace_text_semantic(h, old, new, slide_number, match_case)
    if slide_number is None or not text:
        raise ValueError("append_bullet requires slide_number and non-empty text")
    return _append_bullet(h, slide_number, text, shape_id, text_contains)


def _ppt_style(h, slide_number: int, target: str, shape_id: int | None = None, text_contains: str = "",
               size: int | None = None, color: str | None = None, bold: bool | None = None,
               all_matches: bool = False) -> str:
    if all_matches:
        if not text_contains or shape_id is not None:
            raise ValueError("all_matches requires text_contains and no shape_id")
        slide = h.deck.slides[slide_number - 1]
        targets = [
            shape for shape, _ in _walk_shapes(slide.shapes)
            if getattr(shape, "has_text_frame", False) and text_contains.casefold() in shape.text.casefold()
        ]
        if not targets:
            raise ValueError("no matching shapes")
        results = []
        for shape in targets:
            if target == "fill":
                if not color:
                    raise ValueError("fill styling requires color")
                results.append(_set_shape_fill(h, slide_number, color, shape.shape_id, ""))
            else:
                results.append(_set_text_style(h, slide_number, shape.shape_id, "", size, color, bold))
        return f"styled {len(targets)} matching shapes: " + "; ".join(results)
    if target == "fill":
        if not color:
            raise ValueError("fill styling requires color")
        return _set_shape_fill(h, slide_number, color, shape_id, text_contains)
    return _set_text_style(h, slide_number, shape_id, text_contains, size, color, bold)


def _source_slide_material(slide) -> tuple[list[str], list[bytes], list[list[str]]]:
    """Extract text, image blobs, and table rows without copying relationships."""
    title_id = slide.shapes.title.shape_id if slide.shapes.title is not None else None
    lines: list[str] = []
    images: list[bytes] = []
    table_rows: list[list[str]] = []
    for shape, _ in _walk_shapes(slide.shapes):
        if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
            images.append(shape.image.blob)
        elif getattr(shape, "has_table", False):
            table_rows.extend([[cell.text.strip() for cell in row.cells] for row in shape.table.rows])
        elif shape.shape_id != title_id and getattr(shape, "has_text_frame", False):
            lines.extend(paragraph.text.strip() for paragraph in shape.text_frame.paragraphs if paragraph.text.strip())
    return lines, images, table_rows


def _add_picture_fitted(slide, blob: bytes, x: float, y: float, w: float, height: float) -> None:
    """Re-add an image blob with a valid target-slide media relationship."""
    picture = slide.shapes.add_picture(BytesIO(blob), 0, 0)
    ratio = picture.width / picture.height
    picture_width = min(w, height * ratio)
    picture_height = picture_width / ratio
    picture.left = Inches(x + (w - picture_width) / 2)
    picture.top = Inches(y + (height - picture_height) / 2)
    picture.width = Inches(picture_width)
    picture.height = Inches(picture_height)


def _compose_from_slides(h, source_slides: list[int], insert_after: int, title: str = "",
                         left_title: str = "Male", right_title: str = "Female") -> str:
    """Synthesize two source slides into one inserted visual comparison page."""
    if getattr(h, "deck", None) is None:
        raise ValueError("from_slides requires an open deck")
    if not isinstance(source_slides, list) or len(source_slides) != 2:
        raise ValueError("from_slides requires exactly two source_slides")
    if any(isinstance(number, bool) or not isinstance(number, int) for number in source_slides):
        raise ValueError("source_slides must contain integer slide numbers")
    if len(set(source_slides)) != 2:
        raise ValueError("source_slides must identify two distinct slides")
    count = len(h.deck.slides)
    if any(number < 1 or number > count for number in source_slides):
        raise IndexError("source slide number out of range")
    if isinstance(insert_after, bool) or not isinstance(insert_after, int) or not 1 <= insert_after <= count:
        raise IndexError("insert_after must identify an existing slide")
    if not left_title.strip() or not right_title.strip():
        raise ValueError("from_slides requires non-empty left_title and right_title")

    materials = [_source_slide_material(h.deck.slides[number - 1]) for number in source_slides]
    if not any(lines or images or tables for lines, images, tables in materials):
        raise ValueError("source slides contain no composable content")

    prs = h.deck
    slide = _blank_slide(prs)
    width, height = prs.slide_width / 914400, prs.slide_height / 914400
    margin, gap = max(0.36, width * 0.045), max(0.22, width * 0.025)
    content_width = width - 2 * margin
    column_width = (content_width - gap) / 2
    _rect(slide, 0, 0, width, height, _WHITE)
    heading = slide.shapes.add_textbox(Inches(margin), Inches(0.22), Inches(content_width), Inches(0.64))
    _put_lines(heading.text_frame, title.strip() or "Clothing: Male and Female", 25, True, RGBColor(0x18, 0x18, 0x18))
    _rect(slide, margin, 0.96, content_width, 0.025, RGBColor(0x22, 0x22, 0x22))

    image_top = 1.12
    image_height = min(2.65, max(1.75, height * 0.36))
    for column, (_, images, _) in enumerate(materials):
        column_x = margin + column * (column_width + gap)
        selected = images[:2]
        image_gap = 0.10
        image_width = (column_width - image_gap * (len(selected) - 1)) / max(1, len(selected))
        for index, blob in enumerate(selected):
            _add_picture_fitted(slide, blob, column_x + index * (image_width + image_gap), image_top,
                                image_width, image_height)

    table_top = image_top + image_height + 0.20
    table_height = height - table_top - 0.30
    table_shape = slide.shapes.add_table(2, 2, Inches(margin), Inches(table_top),
                                         Inches(content_width), Inches(table_height))
    table = table_shape.table
    table.columns[0].width = Inches(column_width)
    table.columns[1].width = Inches(column_width)
    for column, label in enumerate((left_title.strip(), right_title.strip())):
        header, body = table.cell(0, column), table.cell(1, column)
        header.text = label
        header.fill.solid(); header.fill.fore_color.rgb = RGBColor(0x1C, 0x1C, 0x1C)
        header.vertical_anchor = MSO_ANCHOR.MIDDLE
        lines, _, table_rows = materials[column]
        table_lines = [" | ".join(value for value in row if value) for row in table_rows]
        body.text = "\n".join(lines + [value for value in table_lines if value])
        body.fill.solid(); body.fill.fore_color.rgb = _WHITE
        body.vertical_anchor = MSO_ANCHOR.TOP
        for cell, color, font_size, bold in ((header, _WHITE, 15, True), (body, _TEXT, 11, False)):
            cell.margin_left = Inches(0.14); cell.margin_right = Inches(0.14)
            cell.margin_top = Inches(0.08); cell.margin_bottom = Inches(0.06)
            for paragraph in cell.text_frame.paragraphs:
                paragraph.space_after = Pt(2)
                for run in paragraph.runs:
                    _style_run(run, font_size, bold, color)

    slide_id = prs.slides._sldIdLst[-1]
    prs.slides._sldIdLst.remove(slide_id)
    prs.slides._sldIdLst.insert(insert_after, slide_id)
    inserted_slide = insert_after + 1
    # Baseline findings are keyed by one-based slide number. Preserve their
    # identity across insertion so historical defects do not become false new
    # failures merely because all later source pages shifted by one position.
    baseline = getattr(h.state, "ppt_baseline_findings", {})
    shifted_baseline: dict[str, float] = {}
    for key, severity in baseline.items():
        parts = key.split(":")
        if len(parts) > 1 and parts[0] == "slide":
            try:
                if int(parts[1]) > insert_after:
                    parts[1] = str(int(parts[1]) + 1)
            except ValueError:
                pass
        shifted_baseline[":".join(parts)] = severity
    h.state.ppt_baseline_findings = shifted_baseline
    prs.slides[inserted_slide - 1].notes_slide.notes_text_frame.text = (
        "[Sources]\n" + ", ".join(f"source slide {number}" for number in source_slides)
    )
    h.state.record_change(f"deck:slide:{inserted_slide}:from_slides")
    h.state.record_fact("ppt_last_compose_scope",
                        f"inserted slide {inserted_slide}; sources {source_slides}; originals preserved")
    return (f"inserted comparison slide {inserted_slide} after slide {insert_after}; "
            f"copied text/table material and {sum(len(item[1][:2]) for item in materials)} image(s) "
            f"from source slides {source_slides}; source slides preserved")


_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _clone_template_slide(prs: Presentation, source_slide):
    """Clone one slide inside a deck while rebuilding its local relationships.

    Shape XML alone is insufficient for pictures, charts, and hyperlinks because
    relationship ids are local to each slide part.  Rebinding them here keeps the
    public ``from_outline`` operation transactional and template-faithful.
    """
    target_slide = prs.slides.add_slide(source_slide.slide_layout)
    relationship_map: dict[str, str] = {}
    for relationship in source_slide.part.rels.values():
        leaf = relationship.reltype.rsplit("/", 1)[-1]
        if leaf in {"slideLayout", "notesSlide"}:
            continue
        target = relationship.target_ref if relationship.is_external else relationship.target_part
        relationship_map[relationship.rId] = target_slide.part.relate_to(
            target, relationship.reltype, relationship.is_external
        )

    for shape in source_slide.shapes:
        element = deepcopy(shape._element)
        for node in element.iter():
            for attribute in (
                f"{{{_REL_NS}}}id", f"{{{_REL_NS}}}embed", f"{{{_REL_NS}}}link",
            ):
                old_id = node.get(attribute)
                if old_id in relationship_map:
                    node.set(attribute, relationship_map[old_id])
        target_slide.shapes._spTree.insert_element_before(element, "p:extLst")
    return target_slide


def _replace_named_shape_text(slide, shape_name: str, text: str) -> None:
    matches = [shape for shape, _ in _walk_shapes(slide.shapes) if shape.name == shape_name]
    if len(matches) != 1:
        raise ValueError(f"template shape {shape_name!r} matched {len(matches)} shapes")
    shape = matches[0]
    if not getattr(shape, "has_text_frame", False):
        raise TypeError(f"template shape {shape_name!r} has no text frame")

    source_paragraphs = list(shape.text_frame.paragraphs)
    paragraph_styles = []
    for paragraph in source_paragraphs:
        ppr = deepcopy(paragraph._p.pPr) if paragraph._p.pPr is not None else None
        rpr = None
        if paragraph.runs and paragraph.runs[0]._r.rPr is not None:
            rpr = deepcopy(paragraph.runs[0]._r.rPr)
        paragraph_styles.append((ppr, rpr))

    lines = str(text).split("\n") or [""]
    text_frame = shape.text_frame
    text_frame.clear()
    for index, line in enumerate(lines):
        paragraph = text_frame.paragraphs[0] if index == 0 else text_frame.add_paragraph()
        style_index = min(index, len(paragraph_styles) - 1)
        ppr, rpr = paragraph_styles[style_index]
        if ppr is not None:
            if paragraph._p.pPr is not None:
                paragraph._p.remove(paragraph._p.pPr)
            paragraph._p.insert(0, deepcopy(ppr))
        run = paragraph.add_run()
        run.text = line
        if rpr is not None:
            if run._r.rPr is not None:
                run._r.remove(run._r.rPr)
            run._r.insert(0, deepcopy(rpr))


def _replace_named_table(slide, shape_name: str, rows: list[list[str]]) -> None:
    matches = [shape for shape, _ in _walk_shapes(slide.shapes) if shape.name == shape_name]
    if len(matches) != 1:
        raise ValueError(f"template table {shape_name!r} matched {len(matches)} shapes")
    shape = matches[0]
    if not getattr(shape, "has_table", False):
        raise TypeError(f"template shape {shape_name!r} is not a table")
    table = shape.table
    if len(rows) != len(table.rows) or any(len(row) != len(table.columns) for row in rows):
        raise ValueError(
            f"table {shape_name!r} requires {len(table.rows)}x{len(table.columns)} values"
        )
    for row_index, row in enumerate(rows):
        for column_index, value in enumerate(row):
            cell = table.cell(row_index, column_index)
            source_runs = [run for paragraph in cell.text_frame.paragraphs for run in paragraph.runs]
            rpr = deepcopy(source_runs[0]._r.rPr) if source_runs and source_runs[0]._r.rPr is not None else None
            cell.text = str(value)
            if rpr is not None and cell.text_frame.paragraphs[0].runs:
                run = cell.text_frame.paragraphs[0].runs[0]
                if run._r.rPr is not None:
                    run._r.remove(run._r.rPr)
                run._r.insert(0, deepcopy(rpr))


def _set_slide_notes_text(slide, text: str) -> None:
    notes_slide = slide.notes_slide
    notes_frame = notes_slide.notes_text_frame
    if notes_frame is not None:
        notes_frame.text = text
        return
    editable = [shape for shape in notes_slide.shapes if getattr(shape, "has_text_frame", False)]
    if editable:
        target = max(editable, key=lambda shape: len(shape.text))
        target.text_frame.text = text
        return
    raise ValueError("template notes slide has no editable text surface")


def _compose_from_outline(h, slides: list[dict], replace_template: bool = True) -> str:
    """Generate several template-faithful slides from a compact ContentIR batch."""
    if getattr(h, "deck", None) is None:
        raise ValueError("from_outline requires an open template deck")
    if not slides:
        raise ValueError("from_outline requires at least one slide specification")
    template_count = len(h.deck.slides)
    baseline_state = SimpleNamespace(
        deck=h.deck,
        state=SimpleNamespace(
            ppt_existing_deck=False,
            ppt_baseline_captured=False,
            ppt_baseline_findings={},
            ppt_affected_slides=set(),
        ),
    )
    template_findings = _collect_structural_findings(baseline_state)
    prepared: list[tuple[int, list[dict], dict | None, str]] = []
    for index, spec in enumerate(slides, 1):
        template_slide = spec.get("template_slide")
        if isinstance(template_slide, bool) or not isinstance(template_slide, int):
            raise ValueError(f"outline slide {index} requires integer template_slide")
        if template_slide < 1 or template_slide > template_count:
            raise IndexError(f"outline slide {index} template_slide out of range")
        replacements = spec.get("replacements") or []
        names = [item.get("shape_name") for item in replacements]
        if any(not name for name in names) or len(names) != len(set(names)):
            raise ValueError(f"outline slide {index} replacement names must be non-empty and unique")
        prepared.append((template_slide, replacements, spec.get("table"), spec.get("speaker_notes", "")))

    # Validate and mutate a deep copy so a bad shape name or table size cannot
    # leave half a generated deck in the live session.
    transaction_buffer = BytesIO()
    h.deck.save(transaction_buffer)
    transaction_buffer.seek(0)
    generated = Presentation(transaction_buffer)
    source_slides = [generated.slides[index] for index in range(template_count)]
    source_notes = []
    for source_slide in source_slides:
        source_notes.append([
            deepcopy(shape._element) for shape in source_slide.notes_slide.shapes
            if getattr(shape, "has_text_frame", False)
        ])
    clones = []
    for template_slide, replacements, table_spec, notes in prepared:
        clone = _clone_template_slide(generated, source_slides[template_slide - 1])
        for replacement in replacements:
            _replace_named_shape_text(clone, replacement["shape_name"], replacement.get("text", ""))
        if table_spec:
            _replace_named_table(clone, table_spec["shape_name"], table_spec["rows"])
        if notes:
            notes_slide = clone.notes_slide
            if not any(getattr(shape, "has_text_frame", False) for shape in notes_slide.shapes):
                for element in source_notes[template_slide - 1]:
                    notes_slide.shapes._spTree.insert_element_before(deepcopy(element), "p:extLst")
            _set_slide_notes_text(clone, notes)
        clones.append(clone)

    if replace_template:
        for _ in range(template_count):
            slide_id = generated.slides._sldIdLst[0]
            generated.part.drop_rel(slide_id.rId)
            generated.slides._sldIdLst.remove(slide_id)

    h.deck = generated
    # The template itself is a visual source. Freeze its structural baseline
    # before content replacement so unchanged design devices (e.g. a full-size
    # text-bearing canvas) remain warnings, while new/worse defects still block.
    h.state.ppt_existing_deck = True
    h.state.ppt_baseline_captured = True
    h.state.ppt_baseline_findings = {
        item["key"]: item["severity"] for item in template_findings
    }
    final_numbers = list(range(1 if replace_template else template_count + 1, len(generated.slides) + 1))
    # Baseline-delta verification checks every generated page for new or worse
    # findings even when it is not in the explicit affected set. Leaving this
    # empty avoids treating unchanged template fixtures as blocking defects.
    h.state.ppt_affected_slides.clear()
    # Record one mutation without feeding generated pages back into the explicit
    # existing-deck scope tracker; delta verification still checks new/worse
    # findings globally against the frozen template baseline.
    h.state.record_change("deck:from_outline")
    h.state.record_fact(
        "ppt_last_compose_scope",
        f"generated {len(clones)} template-faithful slides in one transaction; template_replaced={replace_template}",
    )
    return (
        f"generated {len(clones)} slides from {len(set(item[0] for item in prepared))} template layouts "
        f"in one atomic operation; final deck has {len(generated.slides)} slides"
    )


def _ppt_compose(h, kind: str, **kw) -> str:
    if kind == "new_deck":
        return _new_deck(h, kw.get("title", "Untitled"), kw.get("subtitle", ""))
    if kind == "content":
        return _content_slide(h, kw.get("title", ""), kw.get("bullets") or [], kw.get("size", 18))
    if kind == "comparison":
        if not kw.get("left_title") or not kw.get("right_title"):
            raise ValueError("comparison requires left_title and right_title")
        return _two_column(h, kw.get("title", ""), kw.get("left_title", ""), kw.get("left_bullets") or [], kw.get("right_title", ""), kw.get("right_bullets") or [])
    if kind == "from_slides":
        if kw.get("insert_after") is None:
            raise ValueError("from_slides requires insert_after")
        return _compose_from_slides(
            h, kw.get("source_slides") or [], kw["insert_after"], kw.get("title", ""),
            kw.get("left_title", "Male"), kw.get("right_title", "Female"),
        )
    if kind == "from_outline":
        return _compose_from_outline(h, kw.get("slides") or [], kw.get("replace_template", True))
    if kind == "table":
        if not kw.get("columns") or not kw.get("rows"):
            raise ValueError("table requires non-empty columns and rows")
        return _table_slide(h, kw.get("title", ""), kw.get("columns") or [], kw.get("rows") or [])
    if kind == "quadrant":
        quadrants = kw.get("quadrants") or []
        if len(quadrants) != 4:
            raise ValueError("quadrant requires exactly four quadrant objects")
        required = {"title", "metric", "detail", "bullets", "source"}
        for index, item in enumerate(quadrants, 1):
            if not isinstance(item, dict):
                raise ValueError(f"quadrant {index} must be an object")
            missing = sorted(required - set(item))
            if missing:
                raise ValueError(f"quadrant {index} missing: {', '.join(missing)}")
            if not isinstance(item["bullets"], list) or len(item["bullets"]) > 3:
                raise ValueError(f"quadrant {index} bullets must be an array of at most 3 strings")
        slide_number = kw.get("slide_number")
        # ``replace_template`` is the model-facing way to say "rebuild the
        # auto-opened template slide instead of appending a second page".
        # Honor it generically by targeting the first slide when no explicit
        # slide_number was provided.
        if slide_number is None and kw.get("replace_template"):
            deck = getattr(h, "deck", None)
            if deck is not None and len(deck.slides) >= 1:
                slide_number = 1
        return _quadrant_slide(h, kw.get("title", ""), kw.get("subtitle", ""), quadrants, slide_number)
    if kind == "flowchart":
        if kw.get("slide_number") is None:
            raise ValueError("flowchart requires slide_number")
        return _add_flowchart(h, kw["slide_number"], kw.get("nodes") or [], kw.get("title", ""))
    if kind == "textbox":
        if kw.get("slide_number") is None:
            raise ValueError("textbox requires slide_number")
        x, y, w, height = _geometry_args(kw)
        if any(value is None for value in (x, y, w, height)):
            raise ValueError("textbox requires x, y, w (or width), and height (or h)")
        return _add_textbox_to_slide(h, kw["slide_number"], {
            "x": x, "y": y, "w": w, "h": height,
            "text": kw.get("text", ""), "size": kw.get("size", 18), "bold": kw.get("bold", False),
        })
    raise ValueError(f"unsupported compose kind: {kind}")


def _is_explicit_list_paragraph(paragraph) -> bool:
    """Return whether *paragraph* carries a real DrawingML bullet marker."""
    properties = paragraph._p.pPr
    if properties is None:
        return False
    return any(
        child.tag.rsplit("}", 1)[-1] in {"buChar", "buAutoNum", "buBlip"}
        for child in properties
    )


def _inherited_text_size(shape, paragraph) -> int | None:
    """Resolve the theme font size that a new non-placeholder text box would lose.

    A copied paragraph keeps its explicit run formatting, but placeholder body
    text often inherits its size from the slide master.  Materializing only that
    missing value keeps both columns visually identical without restyling the
    source paragraph.
    """
    explicit = next(
        (run.font.size for run in paragraph.runs if run.font.size is not None),
        paragraph.font.size,
    )
    if explicit is not None:
        return int(round(explicit.pt * 100))
    try:
        master = shape.part.slide.slide_layout.slide_master._element
        style = "bodyStyle" if getattr(shape, "is_placeholder", False) else "otherStyle"
        level = max(1, min(9, int(paragraph.level) + 1))
        nodes = master.xpath(f"./p:txStyles/p:{style}/a:lvl{level}pPr/a:defRPr")
        if nodes and nodes[0].get("sz"):
            return int(nodes[0].get("sz"))
    except (AttributeError, TypeError, ValueError):
        pass
    return None


def _copy_paragraph_for_textbox(shape, paragraph):
    copied = deepcopy(paragraph._p)
    inherited_size = _inherited_text_size(shape, paragraph)
    if inherited_size is None:
        return copied
    # Runs without an explicit size would otherwise fall back from the source
    # placeholder's body style (28 pt in MOD-038) to generic text-box styling.
    for run_properties in copied.xpath("./a:r/a:rPr | ./a:fld/a:rPr | ./a:endParaRPr"):
        if run_properties.get("sz") is None:
            run_properties.set("sz", str(inherited_size))
    return copied


def _replace_text_frame_paragraphs(text_frame, paragraphs) -> None:
    body = text_frame._txBody
    for paragraph in list(body.xpath("./a:p")):
        body.remove(paragraph)
    for paragraph in paragraphs:
        body.append(paragraph)


def _reflow_two_columns(
    h,
    slide_number: int,
    shape_id: int | None = None,
    text_contains: str = "",
    split_after: int | None = None,
    gutter: float = 0.35,
) -> str:
    """Split one checklist text frame into two columns, preserving paragraph XML."""
    if getattr(h, "deck", None) is None:
        raise ValueError("no deck loaded")
    if slide_number < 1 or slide_number > len(h.deck.slides):
        raise IndexError("slide number out of range")
    if not 0.15 <= gutter <= 1.5:
        raise ValueError("reflow_two_columns gutter must be between 0.15 and 1.5 inches")

    slide = h.deck.slides[slide_number - 1]
    if shape_id is not None:
        _, target = _find_shape(h, slide_number, shape_id)
        path = next(path for candidate, path in _walk_shapes(slide.shapes) if candidate.shape_id == shape_id)
        if len(path) > 1:
            raise ValueError("reflow_two_columns requires a top-level text shape")
        candidates = [target]
    else:
        needle = text_contains.strip().casefold()
        candidates = [
            shape for shape in slide.shapes
            if getattr(shape, "has_text_frame", False)
            and (not needle or needle in shape.text.casefold())
        ]
        candidates.sort(
            key=lambda shape: sum(
                _is_explicit_list_paragraph(paragraph)
                for paragraph in shape.text_frame.paragraphs
            ),
            reverse=True,
        )
    target = next(
        (
            shape for shape in candidates
            if getattr(shape, "has_text_frame", False)
            and sum(_is_explicit_list_paragraph(p) for p in shape.text_frame.paragraphs) >= 2
        ),
        None,
    )
    if target is None:
        qualifier = f" containing {text_contains!r}" if text_contains else ""
        raise ValueError(f"no text shape{qualifier} with at least two checklist paragraphs")

    source_paragraphs = list(target.text_frame.paragraphs)
    first_item = next(
        index for index, paragraph in enumerate(source_paragraphs)
        if _is_explicit_list_paragraph(paragraph)
    )
    leading = [paragraph for paragraph in source_paragraphs[:first_item] if paragraph.text.strip()]
    checklist = [paragraph for paragraph in source_paragraphs[first_item:] if paragraph.text.strip()]
    if len(checklist) < 2:
        raise ValueError("reflow_two_columns requires at least two non-empty checklist paragraphs")
    split = math.ceil(len(checklist) / 2) if split_after is None else split_after
    if not isinstance(split, int) or not 1 <= split < len(checklist):
        raise ValueError(f"split_after must be between 1 and {len(checklist) - 1}")

    original_left, original_top = target.left, target.top
    original_width, original_height = target.width, target.height
    total_width = original_width / 914400
    if total_width - gutter < 3.0:
        raise ValueError("source text shape is too narrow for a readable two-column reflow")
    column_width = (total_width - gutter) / 2
    original_right = (original_left + original_width) / 914400
    right_x = original_left / 914400 + column_width + gutter
    if right_x + column_width > h.deck.slide_width / 914400 + 1e-6:
        raise ValueError("two-column reflow would cross the slide boundary")

    left_xml = [deepcopy(paragraph._p) for paragraph in leading + checklist[:split]]
    right_xml = [_copy_paragraph_for_textbox(target, paragraph) for paragraph in checklist[split:]]
    _replace_text_frame_paragraphs(target.text_frame, left_xml)
    # A placeholder can inherit its geometry. Setting only width materializes
    # an incomplete xfrm whose untouched dimensions become zero; write the
    # entire resolved rectangle when detaching it from inherited geometry.
    target.left, target.top = original_left, original_top
    target.width = Inches(column_width)
    target.height = original_height

    right = slide.shapes.add_textbox(
        Inches(right_x), original_top, Inches(column_width), original_height,
    )
    # Preserve the source frame's wrapping/autofit/margins in both columns.
    source_body_properties = deepcopy(target.text_frame._txBody.bodyPr)
    right_body = right.text_frame._txBody
    right_body.replace(right_body.bodyPr, source_body_properties)
    _replace_text_frame_paragraphs(right.text_frame, right_xml)

    # The split remains wholly inside the source shape's former footprint, so
    # it cannot introduce overlap with surrounding template elements.
    if abs((right.left + right.width) / 914400 - original_right) > 0.02:
        raise RuntimeError("two-column geometry did not preserve the source footprint")
    h.state.record_change(f"deck:slide:{slide_number}:reflow_two_columns")
    return (
        f"reflowed slide {slide_number} shape {target.shape_id} into two columns "
        f"({split}+{len(checklist) - split} checklist items); "
        f"created shape {right.shape_id}; affected slide {slide_number}"
    )


def _geometry_args(kw: dict) -> tuple:
    """Normalize rectangle geometry args, accepting w/width and height/h aliases.

    The model-facing schema historically mixed ``w`` with ``height``. Accepting
    both spellings keeps the facade forgiving without task-specific patches.
    """
    def pick(primary: str, alias: str):
        value = kw.get(primary)
        return value if value is not None else kw.get(alias)

    return pick("x", "x"), pick("y", "y"), pick("w", "width"), pick("height", "h")


def _ppt_arrange(h, operation: str, slide_number: int, shape_id: int | None = None, **kw) -> str:
    if operation == "geometry":
        if shape_id is None:
            raise ValueError("geometry requires shape_id")
        x, y, w, height = _geometry_args(kw)
        if any(value is None for value in (x, y, w, height)):
            raise ValueError("geometry requires x, y, w (or width), and height (or h)")
        return _set_shape_geometry(h, slide_number, shape_id, x, y, w, height)
    if operation == "delete_shape":
        if shape_id is None:
            raise ValueError("delete_shape requires shape_id")
        return _delete_shape(h, slide_number, shape_id)
    if operation == "delete_slide":
        return _delete_slide(h, slide_number)
    if operation == "move_slide":
        if kw.get("new_position") is None:
            raise ValueError("move_slide requires new_position")
        return _move_slide(h, slide_number, kw["new_position"])
    if operation == "reflow_two_columns":
        return _reflow_two_columns(
            h,
            slide_number,
            shape_id,
            kw.get("text_contains", ""),
            kw.get("split_after"),
            kw.get("gutter", 0.35),
        )
    raise ValueError(f"unsupported arrange operation: {operation}")


def _ppt_check(h, policy: str = "auto") -> str:
    if (
        policy == "full"
        and getattr(h.state, "ppt_existing_deck", False)
        and bool(getattr(h.state, "ppt_affected_slides", set()))
    ):
        # A local edit is accountable for its delta, not unrelated historical
        # defects elsewhere in the source deck.  Full lint remains appropriate
        # for newly generated decks; scoped existing-deck tasks use auto.
        policy = "auto"
        h.state.record_fact("ppt_full_check_downgraded", "existing deck local edit uses baseline-delta verification")
    reports = {"structural": _verify(h, policy)}
    if policy == "full":
        reports["quality"] = _quality_check(h)
    # Task evaluators are intentionally run by finish after the required path
    # is saved; render/visual checks are also finish-lifecycle services.
    return json.dumps(reports, ensure_ascii=False, indent=2)


def _find_shape(h, slide_number: int, shape_id: int):
    if getattr(h, "deck", None) is None:
        raise ValueError("no deck loaded")
    if slide_number < 1 or slide_number > len(h.deck.slides):
        raise IndexError("slide number out of range")
    slide = h.deck.slides[slide_number - 1]
    for shape, _ in _walk_shapes(slide.shapes):
        if shape.shape_id == shape_id:
            return slide, shape
    raise KeyError(f"shape id not found: {shape_id}")


def _set_shape_geometry(h, slide_number: int, shape_id: int, x: float, y: float, w: float, height: float) -> str:
    if min(x, y) < 0 or w <= 0 or height <= 0:
        raise ValueError("shape geometry must be non-negative with positive width and height")
    if x + w > _W or y + height > _H:
        raise ValueError("shape geometry crosses the 16:9 slide boundary")
    slide, shape = _find_shape(h, slide_number, shape_id)
    # python-pptx may return a fresh proxy for the same XML element on each
    # traversal, so match the slide-unique shape id instead of object identity.
    path = next(path for candidate, path in _walk_shapes(slide.shapes) if candidate.shape_id == shape_id)
    if len(path) > 1:
        raise ValueError(
            "nested shape geometry is group-local, not slide-absolute; "
            "style the nested shape directly or arrange its top-level group"
        )
    shape.left, shape.top = Inches(x), Inches(y)
    shape.width, shape.height = Inches(w), Inches(height)
    h.state.record_change(f"deck:slide:{slide_number}:shape:{shape_id}:geometry")
    return f"moved/resized slide {slide_number} shape {shape_id} -> ({x:.2f},{y:.2f},{w:.2f},{height:.2f})"


def _delete_shape(h, slide_number: int, shape_id: int) -> str:
    _, shape = _find_shape(h, slide_number, shape_id)
    shape._element.getparent().remove(shape._element)
    h.state.record_change(f"deck:slide:{slide_number}:shape:{shape_id}:deleted")
    return f"deleted slide {slide_number} shape {shape_id}"


def _delete_slide(h, slide_number: int) -> str:
    if getattr(h, "deck", None) is None:
        raise ValueError("no deck loaded")
    if slide_number < 1 or slide_number > len(h.deck.slides):
        raise IndexError("slide number out of range")
    slide_id = h.deck.slides._sldIdLst[slide_number - 1]
    relationship_id = slide_id.rId
    h.deck.part.drop_rel(relationship_id)
    h.deck.slides._sldIdLst.remove(slide_id)
    h.state.record_change(f"deck:slide:{slide_number}:deleted")
    return f"deleted slide {slide_number}; {len(h.deck.slides)} slides remain"


def _move_slide(h, slide_number: int, new_position: int) -> str:
    if getattr(h, "deck", None) is None:
        raise ValueError("no deck loaded")
    count = len(h.deck.slides)
    if slide_number < 1 or slide_number > count or new_position < 1 or new_position > count:
        raise IndexError("slide number or destination out of range")
    slide_id = h.deck.slides._sldIdLst[slide_number - 1]
    h.deck.slides._sldIdLst.remove(slide_id)
    h.deck.slides._sldIdLst.insert(new_position - 1, slide_id)
    h.state.record_change(f"deck:slide:{slide_number}:moved:{new_position}")
    return f"moved slide {slide_number} to position {new_position}"


def _set_speaker_notes(h, slide_number: int, text: str) -> str:
    if getattr(h, "deck", None) is None:
        raise ValueError("no deck loaded")
    if slide_number < 1 or slide_number > len(h.deck.slides):
        raise IndexError("slide number out of range")
    notes = h.deck.slides[slide_number - 1].notes_slide.notes_text_frame
    notes.text = text
    h.state.record_change(f"deck:slide:{slide_number}:speaker_notes")
    return f"updated speaker notes on slide {slide_number}"


def _render(h, path: str, output_dir: str = "rendered") -> str:
    from .. import config
    from ..permissions import path_within

    root = config.sandbox_root().resolve()
    source = (root / path).resolve()
    target = (root / output_dir).resolve()
    if not path_within(root, source) or not path_within(root, target):
        raise PermissionError("render path escapes workspace")
    if not source.is_file():
        raise FileNotFoundError(path)
    target.mkdir(parents=True, exist_ok=True)
    for stale in target.iterdir():
        if stale.is_file() and stale.suffix.lower() == ".png":
            stale.unlink()
    if platform.system() == "Windows":
        try:
            import win32com.client
        except ImportError as exc:
            raise RuntimeError("pywin32 is required for PowerPoint rendering") from exc

        def _render_once() -> None:
            app = None
            presentation = None
            try:
                app = win32com.client.DispatchEx("PowerPoint.Application")
            except Exception as exc:
                # COM can be installed but unavailable in a headless/service
                # session. Surface a stable diagnostic so the harness can report
                # a renderer limitation instead of an opaque traceback.
                raise RuntimeError(
                    "PowerPoint COM renderer unavailable in this session; "
                    "use an interactive Windows session or LibreOffice fallback"
                ) from exc
            try:
                presentation = app.Presentations.Open(str(source), ReadOnly=True, Untitled=False, WithWindow=False)
                pdf = target / f"{source.stem}.pdf"
                presentation.SaveCopyAs(str(pdf), 32)
                presentation.Export(str(target), "PNG")
            finally:
                if presentation is not None:
                    presentation.Close()
                app.Quit()

        # PowerPoint COM occasionally raises a transient "发生意外" fault when
        # the automation server is briefly busy. One fresh-DispatchEx retry
        # turns that into a successful render instead of a missing certificate.
        last_error: Exception | None = None
        for _attempt in range(2):
            try:
                _render_once()
                break
            except Exception as exc:
                last_error = exc
        else:
            raise RuntimeError(f"PowerPoint COM render failed after retry: {last_error}") from last_error
    else:
        soffice = shutil.which("soffice") or shutil.which("libreoffice")
        pdftoppm = shutil.which("pdftoppm")
        if not soffice or not pdftoppm:
            raise RuntimeError("Linux PPT rendering requires soffice/libreoffice and pdftoppm")
        pdf = target / f"{source.stem}.pdf"
        convert = subprocess.run(
            [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(target), str(source)],
            capture_output=True, text=True, timeout=120,
        )
        if convert.returncode != 0 or not pdf.exists():
            raise RuntimeError(f"LibreOffice conversion failed: {(convert.stderr or convert.stdout).strip()}")
        raster = subprocess.run(
            [pdftoppm, "-png", "-r", "120", str(pdf), str(target / "slide")],
            capture_output=True, text=True, timeout=120,
        )
        if raster.returncode != 0:
            raise RuntimeError(f"pdftoppm conversion failed: {(raster.stderr or raster.stdout).strip()}")
    images = sorted({image.resolve() for image in target.iterdir() if image.is_file() and image.suffix.lower() == ".png" and image.name.lower() != "montage.png"})
    pdf = target / f"{source.stem}.pdf"
    if not pdf.is_file() or pdf.stat().st_size == 0:
        raise RuntimeError("renderer produced no PDF")
    if not images:
        raise RuntimeError("renderer produced no PNG slides")
    from PIL import Image, ImageDraw
    opened = [Image.open(image).convert("RGB") for image in images]
    try:
        thumb_w = 640
        thumbs = []
        for index, slide_image in enumerate(opened, 1):
            thumb_h = round(slide_image.height * thumb_w / slide_image.width)
            thumb = slide_image.resize((thumb_w, thumb_h))
            canvas = Image.new("RGB", (thumb_w, thumb_h + 36), "white")
            canvas.paste(thumb, (0, 36))
            ImageDraw.Draw(canvas).text((12, 10), f"Slide {index}", fill=(35, 35, 35))
            thumbs.append(canvas)
        columns = 2
        rows = math.ceil(len(thumbs) / columns)
        cell_h = max(thumb.height for thumb in thumbs)
        montage = Image.new("RGB", (columns * thumb_w, rows * cell_h), (225, 225, 225))
        for index, thumb in enumerate(thumbs):
            montage.paste(thumb, ((index % columns) * thumb_w, (index // columns) * cell_h))
        montage_path = target / "montage.png"
        montage.save(montage_path)
    finally:
        for slide_image in opened:
            slide_image.close()
    h.state.record_evidence("ppt_render", f"ppt rendered: {len(images)} PNG slides from {path}")
    h.state.unresolved_checks.discard("ppt_render")
    h.state.last_verification_failed = bool(h.state.unresolved_checks)
    h.state.last_verification_epoch = h.state.mutation_epoch
    if getattr(h, "recorder", None):
        h.recorder.check("ppt_render", True, f"{len(images)} PNG slides; pdf={pdf}")
        h.recorder.artifact(pdf, "rendered-pdf")
        for image in images:
            h.recorder.artifact(image, "rendered-slide")
    return "rendered slides:\n" + "\n".join(str(image.relative_to(root)) for image in images) + f"\nmontage: {montage_path.relative_to(root)}"


def _inspect_rendered(h, output_dir: str = "rendered") -> str:
    """Turn rendered pixels into auditable, deterministic visual evidence.

    This is intentionally a coarse gate, not an aesthetic judge. It catches
    blank renders and content pressed against the slide edge, while leaving
    semantic visual quality to a human or vision model review.
    """
    from PIL import Image, ImageStat
    from .. import config
    from ..permissions import path_within

    root = config.sandbox_root().resolve()
    target = (root / output_dir).resolve()
    if not path_within(root, target):
        raise PermissionError("render inspection path escapes workspace")
    images = sorted(path for path in target.glob("*.png") if path.name.lower() != "montage.png")
    if not images:
        raise FileNotFoundError("no rendered slide PNGs found")
    findings: list[str] = []
    warnings: list[str] = []
    rows: list[str] = []
    for index, path in enumerate(images, 1):
        with Image.open(path) as source:
            gray = source.convert("L")
            width, height = gray.size
            stat = ImageStat.Stat(gray)
            variance = stat.var[0]
            margin = max(2, round(min(width, height) * 0.015))
            pixels = gray.load()
            edge_dark = 0
            edge_total = 0
            for y in range(height):
                for x in range(width):
                    if x < margin or x >= width - margin or y < margin or y >= height - margin:
                        edge_total += 1
                        if pixels[x, y] < 235:
                            edge_dark += 1
            edge_ratio = edge_dark / max(1, edge_total)
            rows.append(f"slide {index}: variance={variance:.1f}, edge_content={edge_ratio:.3f}")
            if variance < 8:
                findings.append(f"slide {index}: probable blank/near-uniform render")
            # Full-bleed theme backgrounds and title bands are intentional in
            # presentation design. Keep this as a warning rather than a hard
            # failure; geometric clipping is already checked by ppt_verify.
            if edge_ratio > 0.30:
                warnings.append(f"slide {index}: full-bleed/edge content warning ({edge_ratio:.3f}); review if not intentional")
    if findings:
        h.state.unresolved_checks.add("ppt_visual")
        h.state.last_verification_failed = True
        h.state.last_verification_epoch = h.state.mutation_epoch
        if getattr(h, "recorder", None):
            h.recorder.check("ppt_visual", False, "\n".join(findings))
        return "Rendered visual audit findings:\n" + "\n".join(findings) + "\nMetrics:\n" + "\n".join(rows)
    h.state.record_evidence("ppt_visual", f"rendered visual audit passed: {len(images)} slides")
    h.state.unresolved_checks.discard("ppt_visual")
    h.state.last_verification_failed = bool(h.state.unresolved_checks)
    h.state.last_verification_epoch = h.state.mutation_epoch
    if getattr(h, "recorder", None):
        h.recorder.check("ppt_visual", True, "\n".join(rows + warnings))
    warning_text = "\nWarnings:\n" + "\n".join(warnings) if warnings else ""
    return "Rendered visual audit passed.\n" + "\n".join(rows) + warning_text


def _add_box(h, box: dict) -> str:
    s = h.deck.slides[-1]
    tb = s.shapes.add_textbox(
        Inches(box["x"]), Inches(box["y"]), Inches(box["w"]), Inches(box["h"])
    )
    _fit_lines(tb.text_frame, str(box.get("text", "")).split("\n"), box.get("size", 18), box.get("bold", False), _TEXT)
    return "text box added."


def _box_from_kw(kw: dict) -> dict:
    box = dict(kw)
    box["h"] = kw["height"]
    return box


def _normalize_minimal_container(prs: Presentation) -> tuple[Presentation, bool]:
    """Move a stripped text/shape-only deck into a standard Office container.

    Some benchmark templates are valid enough for python-pptx but omit most
    standard layout/theme parts and PowerPoint refuses to open them.  Copying
    plain shape XML is safe because it has no media/chart relationship graph;
    richer decks are deliberately left untouched.
    """
    if len(prs.slide_layouts) > 1:
        return prs, False
    safe_types = {1, 14, 17}  # AUTO_SHAPE, PLACEHOLDER, TEXT_BOX
    if any(int(shape.shape_type) not in safe_types for slide in prs.slides for shape in slide.shapes):
        return prs, False
    normalized = Presentation()
    normalized.slide_width = prs.slide_width
    normalized.slide_height = prs.slide_height
    for source_slide in prs.slides:
        target_slide = normalized.slides.add_slide(normalized.slide_layouts[6])
        for shape in source_slide.shapes:
            target_slide.shapes._spTree.insert_element_before(deepcopy(shape._element), "p:extLst")
        if getattr(source_slide, "has_notes_slide", False):
            notes = source_slide.notes_slide.notes_text_frame.text.strip()
            if notes:
                target_slide.notes_slide.notes_text_frame.text = notes
    return normalized, True


def _save(h, path: str | None) -> str:
    from pathlib import Path
    from .. import config
    root = config.sandbox_root()
    if path:
        p = Path(path)
        # tolerate an explicit "workspace/..." prefix from LLM args
        if not p.is_absolute() and p.parts and p.parts[0] in ("workspace", root.name):
            p = Path(*p.parts[1:])
        target = p if p.is_absolute() else root / p
    else:
        target = root / "deck.pptx"
    required_output = getattr(h.state, "facts", {}).get("required_output_pptx")
    if required_output:
        required_target = (root / required_output).resolve()
        # The task contract owns the final deliverable location.  Models often
        # omit the optional path, use the alias ``output_path``, or choose a
        # generic workspace filename.  Any non-intermediate save therefore
        # resolves to the unique contract output deterministically.
        if not path or "intermediate" not in {part.casefold() for part in target.parts}:
            target = required_target
    target.parent.mkdir(parents=True, exist_ok=True)
    prs = _deck(h)
    prs, normalized = _normalize_minimal_container(prs)
    if normalized:
        h.deck = prs
        h.state.record_fact("ppt_container_normalized", "minimal template migrated to standard PowerPoint container")
    prs.save(str(target))
    try:
        relative_target = str(target.relative_to(root))
    except ValueError:
        relative_target = str(target)
    if normalized:
        # Normalization rewrote the in-memory deck, so this is a real content
        # mutation and must advance the epoch.
        h.state.record_change(relative_target)
    else:
        # A plain save only persists the current content; it must not invalidate
        # fresh structural/render evidence for the current epoch.
        h.state.record_commit(relative_target)
    if getattr(h, "recorder", None):
        source = getattr(h, "deck_source_path", None)
        if source:
            h.recorder.bind_source(source, str(target), "edited presentation source")
        # Multi-source provenance is a harness guarantee.  The model should
        # not spend one call per HTML/XLSX/Markdown input merely to create an
        # audit edge that the runtime already knows deterministically.
        for source_path in sorted(getattr(h.state, "source_paths", set())):
            h.recorder.bind_source(Path(source_path), str(target), "ContentIR source used for presentation")
        h.recorder.artifact(target, "final-pptx")
    return f"saved {len(prs.slides)} slides -> {target.name}"


def _deck_info(h) -> str:
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    if getattr(h, "deck", None) is None:
        return "no deck yet."
    lines = []
    for i, slide in enumerate(h.deck.slides, 1):
        texts = []
        for sh in slide.shapes:
            if sh.has_text_frame and sh.shape_type == MSO_SHAPE_TYPE.TEXT_BOX:
                t = (sh.text_frame.text or "").strip()
                if t:
                    texts.append(t.replace("\n", " | ")[:70])
        lines.append(f"  slide {i}: " + ("; ".join(texts) if texts else "(empty)"))
    return f"{len(h.deck.slides)} slides:\n" + "\n".join(lines)


def _collect_structural_findings(h) -> list[dict[str, Any]]:
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    if getattr(h, "deck", None) is None:
        return []
    findings: list[dict[str, Any]] = []

    def add(slide: int, kind: str, subject: str, severity: float, message: str) -> None:
        findings.append({
            "key": f"slide:{slide}:{kind}:{subject}",
            "slide": slide,
            "kind": kind,
            "severity": round(float(severity), 6),
            "message": message,
        })

    for i, slide in enumerate(h.deck.slides, 1):
        text_shapes = []
        for sh in slide.shapes:
            # skip background / decorative rectangles — only inspect real text boxes
            if sh.has_text_frame and sh.shape_type == MSO_SHAPE_TYPE.TEXT_BOX:
                text_shapes.append(sh)
                text = (sh.text_frame.text or "").strip()
                if not text:
                    add(i, "empty_text", str(sh.shape_id), 1.0, f"slide {i}: empty text box (shape {sh.shape_id})")
                    continue
                observed_sizes = []
                for p in sh.text_frame.paragraphs:
                    for r in p.runs:
                        if r.font.size:
                            observed_sizes.append(r.font.size.pt)
                big = max(observed_sizes) if observed_sizes else 18
                w_in = sh.width / 914400
                h_in = sh.height / 914400
                cpl = max(1, int(w_in * 96 / (big * 0.75)))
                lines = 0
                for ln in text.split("\n"):
                    lines += max(1, math.ceil(len(ln) / cpl))
                needed = lines * big * 0.62 / 72
                if needed > h_in * 0.95:
                    severity = needed / max(0.01, h_in * 0.95)
                    add(
                        i, "text_overflow", str(sh.shape_id), severity,
                        f"slide {i}: shape {sh.shape_id} overflow risk ~{needed:.2f}in in {h_in:.2f}in box",
                    )
            # Inspect every positioned shape, not only text boxes. Pictures,
            # charts, tables, and decorative shapes can also be clipped.
            if sh.left < 0 or sh.top < 0 or sh.left + sh.width > h.deck.slide_width or sh.top + sh.height > h.deck.slide_height:
                overflow = max(
                    max(0, -sh.left) / h.deck.slide_width,
                    max(0, -sh.top) / h.deck.slide_height,
                    max(0, sh.left + sh.width - h.deck.slide_width) / h.deck.slide_width,
                    max(0, sh.top + sh.height - h.deck.slide_height) / h.deck.slide_height,
                )
                add(
                    i, "boundary", str(sh.shape_id), overflow,
                    f"slide {i}: shape {sh.shape_id} crosses slide boundary",
                )
        for left_index, a in enumerate(text_shapes):
            for b in text_shapes[left_index + 1:]:
                overlap_w = min(a.left + a.width, b.left + b.width) - max(a.left, b.left)
                overlap_h = min(a.top + a.height, b.top + b.height) - max(a.top, b.top)
                if overlap_w > 0 and overlap_h > 0:
                    ratio = (overlap_w * overlap_h) / min(a.width * a.height, b.width * b.height)
                    if ratio > 0.15:
                        subject = f"{min(a.shape_id, b.shape_id)}-{max(a.shape_id, b.shape_id)}"
                        add(
                            i, "text_overlap", subject, ratio,
                            f"slide {i}: text shapes {a.shape_id}/{b.shape_id} overlap {ratio:.0%}",
                        )
    return findings


def _verify(h, policy: str = "auto") -> str:
    if getattr(h, "deck", None) is None:
        return "no deck yet to verify."
    findings = _collect_structural_findings(h)
    state = h.state
    scoped = policy == "auto" and state.ppt_existing_deck and state.ppt_baseline_captured
    baseline = state.ppt_baseline_findings if scoped else {}
    affected = state.ppt_affected_slides if scoped else set()
    blocking: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for item in findings:
        prior = baseline.get(item["key"])
        is_new = prior is None
        is_worse = prior is not None and item["severity"] > prior + 1e-6
        # Existing defects on an affected slide are not automatically caused by
        # the current edit. Only new or worsened findings block; unchanged
        # baseline findings remain auditable warnings even inside the scope.
        if not scoped or is_new or is_worse:
            blocking.append(item)
        else:
            warnings.append(item)

    warning_summary = "; ".join(item["message"] for item in warnings)
    state.record_fact("ppt_structural_warnings", warning_summary or "none")
    scope_summary = (
        f"scoped existing-deck check; affected slides={sorted(affected) or 'none'}; "
        f"global warnings={len(warnings)}"
        if scoped else "full-deck check"
    )
    if not blocking:
        summary = f"ppt structural verification passed: {len(h.deck.slides)} slides; {scope_summary}"
        state.record_evidence("ppt_structural", summary)
        h.state.unresolved_checks.discard("ppt_structural")
        h.state.last_verification_failed = bool(h.state.unresolved_checks)
        h.state.last_verification_epoch = h.state.mutation_epoch
        if getattr(h, "recorder", None):
            detail = summary + (f"\nHistorical warnings:\n{warning_summary}" if warnings else "")
            h.recorder.check("ppt_structural", True, detail)
        suffix = f" Historical warnings retained: {len(warnings)}." if warnings else ""
        return f"Verification: no structural issues found; no blocking structural issues.{suffix}"
    h.state.unresolved_checks.add("ppt_structural")
    h.state.last_verification_failed = True
    h.state.last_verification_epoch = h.state.mutation_epoch
    h.state.record_evidence("ppt_structural", f"blocking structural findings at epoch {h.state.mutation_epoch}", passed=False)
    report = "\n".join(item["message"] for item in blocking)
    if getattr(h, "recorder", None):
        detail = report + (f"\nHistorical warnings:\n{warning_summary}" if warnings else "")
        h.recorder.check("ppt_structural", False, detail)
    return "Verification findings:\n" + report


def _quality_check(h) -> str:
    """Run a conservative PPT design lint before the visual gate.

    This is intentionally a quality gate, not an aesthetic oracle: it checks
    relationships that are deterministic from the native slide geometry and
    reports warnings separately from blocking findings.
    """
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    line_types = {MSO_SHAPE_TYPE.LINE}
    connector_type = getattr(MSO_SHAPE_TYPE, "CONNECTOR", None)
    if connector_type is not None:
        line_types.add(connector_type)

    if getattr(h, "deck", None) is None:
        return json.dumps({"schema": "xiaopu.ppt-quality.v1", "passed": False, "error": "no deck"})
    slide_w = h.deck.slide_width
    slide_h = h.deck.slide_height
    errors: list[str] = []
    warnings: list[str] = []
    slide_rows: list[str] = []
    for index, slide in enumerate(h.deck.slides, 1):
        text_shapes = []
        visible_shapes = []
        for shape in slide.shapes:
            if getattr(shape, "width", 0) <= 0 or getattr(shape, "height", 0) <= 0:
                continue
            if shape.left < 0 or shape.top < 0 or shape.left + shape.width > slide_w or shape.top + shape.height > slide_h:
                errors.append(f"slide {index}: shape {shape.shape_id} crosses slide boundary")
            text = (shape.text_frame.text or "").strip() if getattr(shape, "has_text_frame", False) else ""
            if text:
                text_shapes.append(shape)
            elif shape.shape_type not in line_types and shape.width > Inches(0.12) and shape.height > Inches(0.12):
                visible_shapes.append(shape)
        if not text_shapes:
            warnings.append(f"slide {index}: no visible text content")
        if len(visible_shapes) > 18:
            warnings.append(f"slide {index}: high shape density ({len(visible_shapes)} visible shapes)")
        for left_index, first in enumerate(text_shapes):
            for second in visible_shapes:
                if first is second:
                    continue
                overlap_w = min(first.left + first.width, second.left + second.width) - max(first.left, second.left)
                overlap_h = min(first.top + first.height, second.top + second.height) - max(first.top, second.top)
                if overlap_w <= 0 or overlap_h <= 0:
                    continue
                ratio = (overlap_w * overlap_h) / min(first.width * first.height, second.width * second.height)
                full_bleed = second.width >= slide_w * 0.92 and second.height >= slide_h * 0.92
                # A text box that sits entirely inside a non-picture autoshape is
                # the normal "text on card/container" layout, not an overlap
                # defect. Only real content collisions — text over an image, or
                # text poking out of its container — should block verification.
                contained = (
                    first.left >= second.left
                    and first.top >= second.top
                    and first.left + first.width <= second.left + second.width
                    and first.top + first.height <= second.top + second.height
                )
                text_in_container = contained and second.shape_type != MSO_SHAPE_TYPE.PICTURE
                if ratio > 0.30 and not full_bleed and not text_in_container:
                    errors.append(f"slide {index}: text shape {first.shape_id} overlaps shape {second.shape_id} ({ratio:.0%})")
        font_sizes = []
        for shape in text_shapes:
            for paragraph in shape.text_frame.paragraphs:
                for run in paragraph.runs:
                    if run.font.size:
                        font_sizes.append(run.font.size.pt)
        if font_sizes and min(font_sizes) < 10:
            warnings.append(f"slide {index}: very small text ({min(font_sizes):.1f}pt)")
        slide_rows.append(f"slide {index}: text={len(text_shapes)}, visible={len(visible_shapes)}")
    passed = not errors
    payload = {
        "schema": "xiaopu.ppt-quality.v1",
        "passed": passed,
        "profile": getattr(h.state, "task_profile", ""),
        "design_policy": getattr(h.state, "design_policy", ""),
        "slides": len(h.deck.slides),
        "errors": errors,
        "warnings": warnings,
        "rows": slide_rows,
    }
    summary = json.dumps(payload, ensure_ascii=False, indent=2)
    if passed:
        h.state.record_evidence("ppt_quality", f"ppt quality lint passed: {len(h.deck.slides)} slides")
        h.state.unresolved_checks.discard("ppt_quality")
        if getattr(h, "recorder", None):
            h.recorder.check("ppt_quality", True, summary)
        return summary
    h.state.unresolved_checks.add("ppt_quality")
    h.state.last_verification_failed = True
    h.state.last_verification_epoch = h.state.mutation_epoch
    h.state.record_evidence("ppt_quality", f"ppt quality lint found blocking issues at epoch {h.state.mutation_epoch}", passed=False)
    if getattr(h, "recorder", None):
        h.recorder.check("ppt_quality", False, summary)
    return summary


def _make(name: str, description: str, params: dict[str, dict], required: list[str], fn: Callable):
    return (_schema(name, description, params, required), fn)


ppt_tools = [
    _make(
        "ppt_open",
        "Open an existing PPTX as an editable working copy while preserving the original.",
        {"path": {"type": "string"}}, ["path"],
        lambda h, **kw: _open_deck(h, kw["path"]),
    ),
    _make(
        "ppt_inspect",
        "Inspect the active deck once. Use summary for slide contents or shapes for stable ids and geometry.",
        {"detail": {"type": "string", "enum": ["summary", "shapes"]}, "slide_number": {"type": "integer"}}, [],
        lambda h, **kw: _ppt_inspect(h, kw.get("detail", "summary"), kw.get("slide_number")),
    ),
    _make(
        "ppt_edit_text",
        "Edit presentation text: one exact replacement, one inherited bullet, or an atomic multi-slide batch. For a single change use operation='replace' with slide_number, old, and new and omit the `updates` field; use `updates` (batch) only for 2+ independent edits. A `replace` replaces every matching occurrence; omit slide_number (and shape_id) to replace across the whole deck (all_matches is optional and redundant for replace).",
        {
            "operation": {"type": "string", "enum": ["replace", "append_bullet", "batch_updates"]},
            "slide_number": {"type": "integer"}, "shape_id": {"type": "integer"},
            "text_contains": {"type": "string"}, "old": {"type": "string"}, "new": {"type": "string"},
            "text": {"type": "string"}, "match_case": {"type": "boolean"}, "all_matches": {"type": "boolean"},
            "updates": {
                "type": "array", "minItems": 1, "maxItems": 100,
                "items": {
                    "type": "object",
                    "properties": {
                        "operation": {"type": "string", "enum": ["replace", "style"]},
                        "slide_number": {"type": "integer"}, "shape_id": {"type": "integer"},
                        "text_contains": {"type": "string"}, "old": {"type": "string"},
                        "new": {"type": "string"}, "match_case": {"type": "boolean"},
                        "target": {"type": "string", "enum": ["text", "fill"]},
                        "size": {"type": "integer"}, "color": {"type": "string"},
                        "bold": {"type": "boolean"}, "all_matches": {"type": "boolean"},
                    },
                    "required": ["operation"], "additionalProperties": False,
                },
            },
        }, ["operation"],
        lambda h, **kw: _ppt_edit_text(h, **kw),
    ),
    _make(
        "ppt_style",
        "Style a selected text shape or shape fill. Select by shape id or distinctive contained text.",
        {
            "slide_number": {"type": "integer"}, "target": {"type": "string", "enum": ["text", "fill"]},
            "shape_id": {"type": "integer"}, "text_contains": {"type": "string"},
            "size": {"type": "integer"}, "color": {"type": "string"}, "bold": {"type": "boolean"},
            "all_matches": {"type": "boolean"},
        }, ["slide_number", "target"],
        lambda h, **kw: _ppt_style(h, **kw),
    ),
    _make(
        "ppt_compose",
        "Create one semantic presentation unit. Only provide fields needed by the selected kind.",
        {
            "kind": {"type": "string", "enum": ["new_deck", "content", "comparison", "from_slides", "from_outline", "table", "quadrant", "flowchart", "textbox"]},
            "slide_number": {"type": "integer"}, "title": {"type": "string"}, "subtitle": {"type": "string"},
            "source_slides": {"type": "array", "minItems": 2, "maxItems": 2, "items": {"type": "integer"}},
            "insert_after": {"type": "integer"},
            "add_table": {"type": "boolean", "description": "Accepted for clarity; from_slides always includes a comparison table."},
            "replace_template": {"type": "boolean"},
            "slides": {
                "type": "array", "minItems": 1, "maxItems": 20,
                "items": {
                    "type": "object",
                    "properties": {
                        "template_slide": {"type": "integer"},
                        "replacements": {
                            "type": "array", "maxItems": 30,
                            "items": {
                                "type": "object",
                                "properties": {
                                    "shape_name": {"type": "string"}, "text": {"type": "string"},
                                },
                                "required": ["shape_name", "text"], "additionalProperties": False,
                            },
                        },
                        "table": {
                            "type": "object",
                            "properties": {
                                "shape_name": {"type": "string"},
                                "rows": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}},
                            },
                            "required": ["shape_name", "rows"], "additionalProperties": False,
                        },
                        "speaker_notes": {"type": "string"},
                    },
                    "required": ["template_slide", "replacements"], "additionalProperties": False,
                },
            },
            "bullets": {"type": "array", "items": {"type": "string"}}, "size": {"type": "integer"},
            "left_title": {"type": "string"}, "left_bullets": {"type": "array", "items": {"type": "string"}},
            "right_title": {"type": "string"}, "right_bullets": {"type": "array", "items": {"type": "string"}},
            "columns": {"type": "array", "items": {"type": "string"}}, "rows": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}},
            "quadrants": {
                "type": "array", "minItems": 4, "maxItems": 4,
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"}, "metric": {"type": "string"},
                        "detail": {"type": "string"},
                        "bullets": {"type": "array", "maxItems": 3, "items": {"type": "string"}},
                        "source": {"type": "string"},
                    },
                    "required": ["title", "metric", "detail", "bullets", "source"],
                    "additionalProperties": False,
                },
            },
            "nodes": {"type": "array", "minItems": 3, "maxItems": 5, "items": {"type": "string"}},
            "x": {"type": "number"}, "y": {"type": "number"}, "w": {"type": "number"}, "width": {"type": "number"}, "height": {"type": "number"}, "h": {"type": "number"},
            "text": {"type": "string"}, "bold": {"type": "boolean"},
        }, ["kind"],
        lambda h, **kw: _ppt_compose(h, **kw),
    ),
    _make(
        "ppt_arrange",
        "Targeted layout operations on any shape (including pictures): geometry moves/resizes a shape via x/y/w/height, delete_shape/delete_slide/move_slide, or reflow_two_columns to split an existing checklist. Use geometry to resize an image that overlaps newly added content. Inspect first.",
        {
            "operation": {"type": "string", "enum": ["geometry", "delete_shape", "delete_slide", "move_slide", "reflow_two_columns"]},
            "slide_number": {"type": "integer"}, "shape_id": {"type": "integer"},
            "x": {"type": "number"}, "y": {"type": "number"}, "w": {"type": "number"}, "width": {"type": "number"}, "height": {"type": "number"}, "h": {"type": "number"},
            "new_position": {"type": "integer"},
            "text_contains": {"type": "string", "description": "Optional selector when shape_id is omitted."},
            "split_after": {"type": "integer", "description": "Optional left-column item count; defaults to a balanced split."},
            "gutter": {"type": "number", "description": "Column gap in inches (0.15-1.5, default 0.35)."},
        }, ["operation", "slide_number"],
        lambda h, **kw: _ppt_arrange(h, **kw),
    ),
    _make(
        "ppt_save",
        "Commit the active deck to the task-required output path. Omit path when intake already found that path.",
        {"path": {"type": "string"}}, [],
        lambda h, **kw: _save(h, kw.get("path")),
    ),
    _make(
        "ppt_check",
        "Check the current deck revision. Auto runs structural checks; full also runs deterministic quality lint. Finish owns evaluator/render/visual gates.",
        {"policy": {"type": "string", "enum": ["auto", "full"]}}, [],
        lambda h, **kw: _ppt_check(h, kw.get("policy", "auto")),
    ),
    _make(
        "open_deck",
        "Load an existing .pptx from the workspace for inspection or modification.",
        {"path": {"type": "string"}},
        ["path"],
        lambda h, **kw: _open_deck(h, kw["path"]),
    ),
    _make(
        "new_deck",
        "Create a new empty 16:9 PowerPoint deck with ONE cover slide. To build a multi-page deck, call new_deck once for the cover, then call ppt_compose with kind='content'/'comparison'/'table'/'quadrant' etc. once per additional slide; never open a non-existent file first.",
        {"title": {"type": "string"}, "subtitle": {"type": "string"}},
        ["title"],
        lambda h, **kw: _new_deck(h, kw.get("title", "Untitled"), kw.get("subtitle", "")),
    ),
    _make(
        "add_slide",
        "Add a content slide with title and optional bullet list.",
        {
            "title": {"type": "string"},
            "bullets": {"type": "array", "items": {"type": "string"}},
            "size": {"type": "integer", "description": "bullet font size"},
        },
        ["title"],
        lambda h, **kw: _content_slide(h, kw.get("title", ""), kw.get("bullets") or [], kw.get("size", 18)),
    ),
    _make(
        "add_two_column_slide",
        "Add a comparison or paired-argument slide with two balanced cards.",
        {"title": {"type": "string"}, "left_title": {"type": "string"}, "left_bullets": {"type": "array", "items": {"type": "string"}}, "right_title": {"type": "string"}, "right_bullets": {"type": "array", "items": {"type": "string"}}},
        ["title", "left_title", "left_bullets", "right_title", "right_bullets"],
        lambda h, **kw: _two_column(h, kw["title"], kw["left_title"], kw["left_bullets"], kw["right_title"], kw["right_bullets"]),
    ),
    _make(
        "compose_quadrant_slide",
        "Compose a complete executive 2x2 quadrant page in one call. The harness owns layout, typography, source chips, and speaker-note provenance. Use slide_number to replace a template slide; omit it to append.",
        {
            "title": {"type": "string"},
            "subtitle": {"type": "string"},
            "slide_number": {"type": "integer"},
            "quadrants": {
                "type": "array", "minItems": 4, "maxItems": 4,
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "metric": {"type": "string"},
                        "detail": {"type": "string"},
                        "bullets": {"type": "array", "maxItems": 3, "items": {"type": "string"}},
                        "source": {"type": "string", "description": "source anchors and chart ids"},
                    },
                    "required": ["title", "metric", "detail", "bullets", "source"],
                },
            },
        },
        ["title", "quadrants"],
        lambda h, **kw: _quadrant_slide(h, kw["title"], kw.get("subtitle", ""), kw["quadrants"], kw.get("slide_number")),
    ),
    _make(
        "add_metric_slide",
        "Add a visual KPI slide with 1-4 metric cards and an optional takeaway.",
        {"title": {"type": "string"}, "metrics": {"type": "array", "minItems": 1, "maxItems": 4, "items": {"type": "object", "properties": {"value": {"type": "string"}, "label": {"type": "string"}, "detail": {"type": "string"}}, "required": ["value", "label"]}}, "takeaway": {"type": "string"}},
        ["title", "metrics"],
        lambda h, **kw: _metric_slide(h, kw["title"], kw["metrics"], kw.get("takeaway", "")),
    ),
    _make(
        "add_table_slide",
        "Add a styled table slide. Prefer for exact comparisons; keep at most 6 columns and 10 rows.",
        {"title": {"type": "string"}, "columns": {"type": "array", "items": {"type": "string"}}, "rows": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}}},
        ["title", "columns", "rows"],
        lambda h, **kw: _table_slide(h, kw["title"], kw["columns"], kw["rows"]),
    ),
    _make(
        "add_process_slide",
        "Add a 3-5 step process, method, roadmap, or closing action slide.",
        {"title": {"type": "string"}, "steps": {"type": "array", "minItems": 3, "maxItems": 5, "items": {"type": "object", "properties": {"title": {"type": "string"}, "detail": {"type": "string"}}, "required": ["title", "detail"]}}, "takeaway": {"type": "string"}},
        ["title", "steps"],
        lambda h, **kw: _process_slide(h, kw["title"], kw["steps"], kw.get("takeaway", "")),
    ),
    _make(
        "add_image_slide",
        "Add a full-width image slide using an image already in the workspace.",
        {"title": {"type": "string"}, "image_path": {"type": "string"}, "caption": {"type": "string"}},
        ["title", "image_path"],
        lambda h, **kw: _image_slide(h, kw["title"], kw["image_path"], kw.get("caption", "")),
    ),
    _make(
        "add_textbox",
        "Add a free text box to the last slide.",
        {
            "x": {"type": "number"}, "y": {"type": "number"},
            "w": {"type": "number"}, "height": {"type": "number"},
            "text": {"type": "string"}, "size": {"type": "integer"},
            "bold": {"type": "boolean"},
        },
        ["x", "y", "w", "height", "text", "size"],
        lambda h, **kw: _add_box(h, _box_from_kw(kw)),
    ),
    _make(
        "save_deck",
        "Save current deck to a .pptx file (default workspace/deck.pptx).",
        {"path": {"type": "string"}, "output_path": {"type": "string", "description": "Alias for path."}},
        [],
        lambda h, **kw: _save(h, kw.get("path") or kw.get("output_path")),
    ),
    _make(
        "deck_info",
        "List slides and their contents in the current deck.",
        {},
        [],
        lambda h, **kw: _deck_info(h),
    ),
    _make(
        "shape_inventory",
        "Inspect editable shapes with stable slide number, shape id, geometry, and text. Call before modifying an existing deck.",
        {"slide_number": {"type": "integer"}},
        [],
        lambda h, **kw: _shape_inventory(h, kw.get("slide_number")),
    ),
    _make(
        "replace_shape_text",
        "Replace text in one shape identified by shape_inventory while preserving its primary font styling.",
        {"slide_number": {"type": "integer"}, "shape_id": {"type": "integer"}, "text": {"type": "string"}},
        ["slide_number", "shape_id", "text"],
        lambda h, **kw: _replace_text(h, kw["slide_number"], kw["shape_id"], kw["text"]),
    ),
    _make(
        "replace_text",
        "Replace exact text across one slide or the whole deck, including matches split across multiple runs. Preserves the paragraph's dominant style.",
        {"old": {"type": "string"}, "new": {"type": "string"}, "slide_number": {"type": "integer"}, "match_case": {"type": "boolean"}},
        ["old", "new"],
        lambda h, **kw: _replace_text_semantic(h, kw["old"], kw["new"], kw.get("slide_number"), kw.get("match_case", True)),
    ),
    _make(
        "append_bullet",
        "Append a peer bullet to a body/list shape while inheriting paragraph and run styling. Target by shape id or distinctive text.",
        {"slide_number": {"type": "integer"}, "text": {"type": "string"}, "shape_id": {"type": "integer"}, "text_contains": {"type": "string"}},
        ["slide_number", "text"],
        lambda h, **kw: _append_bullet(h, kw["slide_number"], kw["text"], kw.get("shape_id"), kw.get("text_contains", "")),
    ),
    _make(
        "set_text_style",
        "Set font size, color, or bold for a text shape selected by shape id or contained text.",
        {"slide_number": {"type": "integer"}, "shape_id": {"type": "integer"}, "text_contains": {"type": "string"}, "size": {"type": "integer"}, "color": {"type": "string", "description": "RGB hex, e.g. 1F3864"}, "bold": {"type": "boolean"}},
        ["slide_number"],
        lambda h, **kw: _set_text_style(h, kw["slide_number"], kw.get("shape_id"), kw.get("text_contains", ""), kw.get("size"), kw.get("color"), kw.get("bold")),
    ),
    _make(
        "set_shape_fill",
        "Set the solid fill color of a shape selected by shape id or contained text.",
        {"slide_number": {"type": "integer"}, "color": {"type": "string", "description": "RGB hex"}, "shape_id": {"type": "integer"}, "text_contains": {"type": "string"}},
        ["slide_number", "color"],
        lambda h, **kw: _set_shape_fill(h, kw["slide_number"], kw["color"], kw.get("shape_id"), kw.get("text_contains", "")),
    ),
    _make(
        "add_textbox_to_slide",
        "Add a text box to a specified existing slide, using slide-inch coordinates.",
        {"slide_number": {"type": "integer"}, "x": {"type": "number"}, "y": {"type": "number"}, "w": {"type": "number"}, "height": {"type": "number"}, "text": {"type": "string"}, "size": {"type": "integer"}, "bold": {"type": "boolean"}},
        ["slide_number", "x", "y", "w", "height", "text", "size"],
        lambda h, **kw: _add_textbox_to_slide(h, kw["slide_number"], _box_from_kw(kw)),
    ),
    _make(
        "add_flowchart",
        "Add a compact 3-5 node horizontal flowchart to a specified existing slide.",
        {"slide_number": {"type": "integer"}, "nodes": {"type": "array", "minItems": 3, "maxItems": 5, "items": {"type": "string"}}, "title": {"type": "string"}},
        ["slide_number", "nodes"],
        lambda h, **kw: _add_flowchart(h, kw["slide_number"], kw["nodes"], kw.get("title", "")),
    ),
    _make(
        "set_shape_geometry",
        "Move and resize an existing shape using slide-inch coordinates. Inspect with shape_inventory first.",
        {"slide_number": {"type": "integer"}, "shape_id": {"type": "integer"}, "x": {"type": "number"}, "y": {"type": "number"}, "w": {"type": "number"}, "height": {"type": "number"}},
        ["slide_number", "shape_id", "x", "y", "w", "height"],
        lambda h, **kw: _set_shape_geometry(h, kw["slide_number"], kw["shape_id"], kw["x"], kw["y"], kw["w"], kw["height"]),
    ),
    _make(
        "delete_shape",
        "Delete one shape identified by shape_inventory.",
        {"slide_number": {"type": "integer"}, "shape_id": {"type": "integer"}},
        ["slide_number", "shape_id"],
        lambda h, **kw: _delete_shape(h, kw["slide_number"], kw["shape_id"]),
    ),
    _make(
        "delete_slide",
        "Delete a slide by its current one-based position.",
        {"slide_number": {"type": "integer"}},
        ["slide_number"],
        lambda h, **kw: _delete_slide(h, kw["slide_number"]),
    ),
    _make(
        "move_slide",
        "Move a slide from its current one-based position to another position.",
        {"slide_number": {"type": "integer"}, "new_position": {"type": "integer"}},
        ["slide_number", "new_position"],
        lambda h, **kw: _move_slide(h, kw["slide_number"], kw["new_position"]),
    ),
    _make(
        "set_speaker_notes",
        "Replace speaker notes on one slide. For sourced evaluation decks, include a [Sources] block without exposing planning notes on the slide.",
        {"slide_number": {"type": "integer"}, "text": {"type": "string"}},
        ["slide_number", "text"],
        lambda h, **kw: _set_speaker_notes(h, kw["slide_number"], kw["text"]),
    ),
    _make(
        "ppt_verify",
        "Run structural verification on the deck: empty text boxes, overflow proxy. Returns a report.",
        {},
        [],
        lambda h, **kw: _verify(h),
    ),
    _make(
        "ppt_quality_check",
        "Run a deterministic PPT quality lint for boundaries, text overlap, density, and text size. Returns JSON evidence.",
        {},
        [],
        lambda h, **kw: _quality_check(h),
    ),
    _make(
        "render_deck",
        "Render a saved .pptx to PNG slides for visual inspection. On Windows uses installed PowerPoint; Linux benchmark images should provide LibreOffice.",
        {"path": {"type": "string"}, "output_dir": {"type": "string"}},
        ["path"],
        lambda h, **kw: _render(h, kw["path"], kw.get("output_dir", "rendered")),
    ),
    _make(
        "inspect_rendered_deck",
        "Inspect rendered PNG slides for blank output and edge-clipping risk. This is a deterministic gate, not a substitute for semantic visual review.",
        {"output_dir": {"type": "string"}},
        [],
        lambda h, **kw: _inspect_rendered(h, kw.get("output_dir", "rendered")),
    ),
]
