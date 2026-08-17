from __future__ import annotations

import importlib.util
import json
import os
import platform
import shutil
import sys
from pathlib import Path

from . import config


def report() -> dict:
    config.load_dotenv()
    provider = config.provider()
    key = config.provider_api_key()
    root = config.sandbox_root().resolve()
    powerpoint = Path(r"C:\Program Files\Microsoft Office\root\Office16\POWERPNT.EXE")
    return {
        "provider": provider,
        "model": config.anthropic_model() if provider == "anthropic" else config.model(),
        "base_url": config.anthropic_api_base() if provider == "anthropic" else config.api_base(),
        "api_key_configured": bool(key),
        "api_key_length": len(key) if key else 0,
        "workspace": str(root),
        "workspace_writable": root.is_dir() and os.access(root, os.W_OK),
        "python": platform.python_version(),
        "dependencies": {
            name: importlib.util.find_spec(name) is not None
            for name in ("openai", "anthropic", "pptx", "rich", "pydantic", "PIL")
        },
        "renderers": {
            "powerpoint": powerpoint.is_file(),
            "libreoffice": shutil.which("soffice") is not None,
        },
        "budgets": {
            "max_steps": config.max_steps(),
            "max_tool_calls": config.max_tool_calls(),
            "max_total_tokens": config.max_total_tokens(),
        },
    }


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Baoyi environment & installation doctor")
    parser.add_argument("--check-install", action="store_true", help="Verify dependencies and installation without requiring configured API keys")
    args = parser.parse_args()
    result = report()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    required = result["dependencies"]
    if args.check_install:
        return 0 if all(required.values()) and result["workspace_writable"] else 1
    return 0 if all(required.values()) and result["api_key_configured"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
