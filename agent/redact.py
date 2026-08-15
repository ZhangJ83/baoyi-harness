from __future__ import annotations

import os
import re

_KEYLIKE = re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b")


def secrets() -> list[str]:
    names = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY")
    return [value for name in names if len(value := os.getenv(name, "")) >= 8]


def redact(text: str) -> str:
    clean = str(text)
    for value in secrets():
        clean = clean.replace(value, "[REDACTED]")
    return _KEYLIKE.sub("[REDACTED]", clean)
