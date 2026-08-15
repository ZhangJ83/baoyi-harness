from __future__ import annotations

import os
import platform
from pathlib import Path

from . import config


def workspace_context(max_entries: int = 120, max_instruction_chars: int = 16000) -> str:
    root = config.sandbox_root().resolve()
    try:
        entries = sorted(root.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))
    except OSError as exc:
        return f"Workspace: {root}\nWorkspace inspection failed: {exc}"
    listing = "\n".join(
        f"{'dir ' if item.is_dir() else 'file'} {item.name}" for item in entries[:max_entries]
    )
    if len(entries) > max_entries:
        listing += f"\n... {len(entries) - max_entries} more entries"

    instruction_parts = []
    # ``CLAUDE.md`` is a foreign product's instruction convention.  Loading it
    # into 小朴's context can import an incompatible identity or command contract.
    for name in ("AGENTS.md", "XIAOPU.md"):
        path = root / name
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace")
            instruction_parts.append(f"--- {name} ---\n{text[:max_instruction_chars]}")
    instructions = "\n".join(instruction_parts) or "(no root AGENTS.md or XIAOPU.md)"
    return (
        f"OS: {platform.system()} {platform.release()}\n"
        f"Workspace: {root}\n"
        f"Python: {platform.python_version()}\n"
        f"Top-level entries:\n{listing or '(empty)'}\n"
        f"Project instructions:\n{instructions}\n"
        "Nested instruction files may override rules for files below them; discover and read them before editing nested code."
    )
