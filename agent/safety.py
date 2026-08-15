"""Provider- and benchmark-independent command safety predicates."""
from __future__ import annotations

import re


def sensitive_output(command: str) -> bool:
    """Return true when a command likely prints sensitive file contents."""
    lower = command.casefold()
    readers = r"\b(cat|head|tail|less|more|strings|xxd|od|base64|sed|awk|grep)\b"
    sensitive = r"(solution|secret|password|token|api[_-]?key|credential|\.env)"
    return bool(re.search(readers, lower) and re.search(sensitive, lower))
