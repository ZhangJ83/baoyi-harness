from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from . import config


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    body: str
    path: Path
    allowed_tools: tuple[str, ...] = ()
    when_to_use: str = ""


def _parse(path: Path) -> Skill | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    name = path.parent.name
    description = ""
    allowed_tools: tuple[str, ...] = ()
    when_to_use = ""
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            header = text[3:end]
            for line in header.splitlines():
                key, sep, value = line.partition(":")
                if sep and key.strip() == "name":
                    name = value.strip().strip("\"'")
                if sep and key.strip() == "description":
                    description = value.strip().strip("\"'")
                if sep and key.strip() in {"allowed_tools", "allowed-tools"}:
                    allowed_tools = _parse_tool_list(value)
                if sep and key.strip() in {"when_to_use", "when-to-use"}:
                    when_to_use = value.strip().strip("\"'")
    return Skill(name=name, description=description, body=text, path=path, allowed_tools=allowed_tools, when_to_use=when_to_use)


def _parse_tool_list(value: str) -> tuple[str, ...]:
    """Parse both plain and YAML inline-list tool declarations."""
    value = value.strip()
    if not value:
        return ()
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1]
    else:
        inner = value
    items = [item.strip().strip("\"'") for item in inner.split(",")]
    return tuple(item for item in items if item)


def discover() -> list[Skill]:
    package_root = Path(__file__).resolve().parent / "builtin_skills"
    project_root = config.sandbox_root() / ".xiaopu" / "skills"
    found = []
    for root in (package_root, project_root):
        if not root.is_dir():
            continue
        for path in sorted(root.glob("*/SKILL.md")):
            skill = _parse(path)
            if skill and all(existing.name != skill.name for existing in found):
                found.append(skill)
    return found


def catalog(skills: list[Skill]) -> str:
    if not skills:
        return "(no skills available)"
    return "\n".join(f"- {skill.name}: {skill.description}" + (f"; when={skill.when_to_use}" if skill.when_to_use else "") + (f"; allowed_tools={','.join(skill.allowed_tools)}" if skill.allowed_tools else "") for skill in skills)


def match(task: str, skills: list[Skill], max_chars: int = 12000) -> list[Skill]:
    lowered = task.lower()
    selected = []
    stopwords = {"create", "modify", "verify", "and", "with", "from", "using", "tool", "tools"}
    for skill in skills:
        if skill.name.lower() == "powerpoint" and any(
            marker in lowered for marker in ("ppt", "pptx", "powerpoint", "slide", "deck", "演示", "幻灯片", "排版")
        ):
            selected.append(skill)
            continue
        terms = {term for term in re.findall(r"[a-zA-Z]{4,}|[\u4e00-\u9fff]{2,}", skill.description.lower()) if term not in stopwords}
        hits = sum(term in lowered for term in terms)
        if skill.name.lower() in lowered or hits >= 2:
            selected.append(skill)
    total = 0
    bounded = []
    for skill in selected:
        if total + len(skill.body) > max_chars:
            break
        bounded.append(skill)
        total += len(skill.body)
    return bounded
