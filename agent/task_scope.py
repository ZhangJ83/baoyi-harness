"""Conservative task-text inference for PowerPoint mutation scope.

A scope can be:
- global: any slide may change;
- finite slides: only listed slides may change;
- shape targets: only listed shapes on listed slides may change;
- unscoped: no hard gate, the diff is recorded as audit evidence only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re


@dataclass(frozen=True)
class PptScope:
    global_scope: bool = False
    slides: frozenset[int] = frozenset()
    shape_targets: tuple[tuple[int, frozenset[int]], ...] = ()
    restrictive: bool = False
    explicit: bool = False


_GLOBAL_SCOPE = re.compile(
    r"\b(?:all\s+(?:slides?|pages?)|entire\s+(?:presentation|deck)|"
    r"whole\s+(?:presentation|deck)|throughout(?:\s+the)?\s+(?:slides?|presentation|deck)|"
    r"across\s+all\s+slides?)\b|"
    r"(?:所有页面|全部页面|所有幻灯片|全部幻灯片|整个演示文稿|整份演示文稿|全文|通篇|全篇|全篇幻灯片|全文幻灯片)",
    re.IGNORECASE,
)

_ENGLISH_SLIDES = re.compile(
    r"\b(?:slides?|pages?)\s+#?\s*"
    r"(\d+(?:\s*(?:,|and|&)\s*\d+)*)\b",
    re.IGNORECASE,
)

_CHINESE_SLIDES = re.compile(
    r"第\s*(\d+(?:\s*(?:、|,|，|和|及|与)\s*\d+)*)\s*页"
)

_ENGLISH_SHAPE = re.compile(
    r"\bshape\s*#?\s*(\d+)\s+(?:on|in)\s+(?:slide|page)\s*#?\s*(\d+)\b",
    re.IGNORECASE,
)

_CHINESE_SHAPE = re.compile(
    r"第\s*(\d+)\s*页\s*(?:的)?\s*(?:形状|图形|shape)\s*#?\s*(\d+)",
    re.IGNORECASE,
)

_NUMBER = re.compile(r"\d+")

_CONTINUATION_ONLY = re.compile(
    r"^(?:继续|继续吧|请继续|continue|resume)(?:[\s.!?。！？]*)$",
    re.IGNORECASE,
)

_RESTRICTIVE = re.compile(
    r"\b(?:only|just)\b|只改|仅改|只调整|仅调整|只修改|仅修改|只允许|不要改|不能改|"
    r"其他页(?:保持|不要|不能)|其余页(?:保持|不要|不能)|保留其他页面|keep other pages unchanged",
    re.IGNORECASE,
)


def _slide_numbers(task: str) -> frozenset[int]:
    pages: set[int] = set()
    for pattern in (_ENGLISH_SLIDES, _CHINESE_SLIDES):
        for match in pattern.finditer(task):
            pages.update(int(token) for token in _NUMBER.findall(match.group(1)) if int(token) > 0)
    return frozenset(pages)


def _shape_targets(task: str) -> dict[int, set[int]]:
    targets: dict[int, set[int]] = {}
    for match in _ENGLISH_SHAPE.finditer(task):
        shape_id, slide = int(match.group(1)), int(match.group(2))
        targets.setdefault(slide, set()).add(shape_id)
    for match in _CHINESE_SHAPE.finditer(task):
        slide, shape_id = int(match.group(1)), int(match.group(2))
        targets.setdefault(slide, set()).add(shape_id)
    return targets


def infer_ppt_mutation_scope(task: str) -> PptScope:
    """Return the scope explicitly expressed by *task*, or an unscoped default."""
    if _GLOBAL_SCOPE.search(task):
        return PptScope(global_scope=True, restrictive=bool(_RESTRICTIVE.search(task)), explicit=True)
    slides = _slide_numbers(task)
    targets = _shape_targets(task)
    slides = slides | frozenset(targets.keys())
    restrictive = bool(_RESTRICTIVE.search(task))
    explicit = bool(slides or targets)
    return PptScope(
        global_scope=False,
        slides=slides,
        shape_targets=tuple((slide, frozenset(shapes)) for slide, shapes in sorted(targets.items())),
        restrictive=restrictive,
        explicit=explicit,
    )


def ppt_scope_is_explicit(task: str) -> bool:
    """Whether *task* explicitly declares a global or finite scope."""
    return infer_ppt_mutation_scope(task).explicit


def is_scope_continuation(task: str) -> bool:
    """Return true only for a standalone request to resume the prior turn."""
    return bool(_CONTINUATION_ONLY.fullmatch(task.strip()))
