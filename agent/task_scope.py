"""Conservative task-text inference for PowerPoint mutation scope.

Only explicit, mechanically reliable slide/page expressions are recognized.
``None`` means that no finite slide set can be inferred: either the task
explicitly opens the whole presentation or it does not state a trustworthy
page number.  Callers use :func:`ppt_scope_is_explicit` to distinguish those
two cases without guessing.
"""

from __future__ import annotations

import re


_GLOBAL_SCOPE = re.compile(
    r"\b(?:all\s+(?:slides?|pages?)|entire\s+(?:presentation|deck)|"
    r"whole\s+(?:presentation|deck)|throughout(?:\s+the)?\s+(?:slides?|presentation|deck)|"
    r"across\s+all\s+slides?)\b|"
    r"(?:所有页面|全部页面|所有幻灯片|全部幻灯片|整个演示文稿|整份演示文稿|全文|通篇|全篇|全篇幻灯片|全文幻灯片)",
    re.IGNORECASE,
)

_ENGLISH_SCOPE = re.compile(
    r"\b(?:slides?|pages?)\s+#?\s*"
    r"(\d+(?:\s*(?:,|and|&)\s*\d+)*)\b",
    re.IGNORECASE,
)

_CHINESE_SCOPE = re.compile(
    r"第\s*(\d+(?:\s*(?:、|,|，|和|及|与)\s*\d+)*)\s*页"
)

_NUMBER = re.compile(r"\d+")

_CONTINUATION_ONLY = re.compile(
    r"^(?:继续|继续吧|请继续|continue|resume)(?:[\s.!?。！？]*)$",
    re.IGNORECASE,
)


def _explicit_pages(task: str) -> frozenset[int]:
    pages: set[int] = set()
    for pattern in (_ENGLISH_SCOPE, _CHINESE_SCOPE):
        for match in pattern.finditer(task):
            pages.update(
                number for token in _NUMBER.findall(match.group(1))
                if (number := int(token)) > 0
            )
    return frozenset(pages)


def infer_ppt_mutation_scope(task: str) -> frozenset[int] | None:
    """Return an explicit finite slide set, or ``None`` when it is not finite.

    Whole-deck phrases deliberately take precedence over page mentions.  Text
    without a supported explicit expression also returns ``None``; it is not
    interpreted as permission to mutate an inferred page.
    """

    if _GLOBAL_SCOPE.search(task):
        return None
    pages = _explicit_pages(task)
    return pages or None


def ppt_scope_is_explicit(task: str) -> bool:
    """Whether *task* explicitly declares a finite or whole-deck scope."""

    return bool(_GLOBAL_SCOPE.search(task) or _explicit_pages(task))


def is_scope_continuation(task: str) -> bool:
    """Return true only for a standalone request to resume the prior turn.

    A sentence such as ``continue editing slide 4`` is intentionally a new
    scoped task (and is parsed as slide 4); only an otherwise content-free
    continuation token inherits the preceding scope.
    """

    return bool(_CONTINUATION_ONLY.fullmatch(task.strip()))
