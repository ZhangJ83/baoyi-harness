"""Deterministic repository facts for the generic code capability pack."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(frozen=True)
class CodeTaskSpec:
    language: str = "unknown"
    runner: str = ""
    target_paths: tuple[str, ...] = ()


def compile_code_task(request: str, workspace: Path) -> CodeTaskSpec:
    text = request.replace("\\", "/")
    mentioned = []
    for match in re.finditer(r"(?<![\w.-])([\w./-]+\.(?:py|js|ts|tsx|jsx|rs|go))(?![\w.-])", text, re.I):
        candidate = (workspace / match.group(1)).resolve()
        try:
            mentioned.append(str(candidate.relative_to(workspace.resolve())))
        except ValueError:
            continue
    suffixes = {Path(path).suffix.casefold() for path in mentioned}
    if not suffixes:
        suffixes = {path.suffix.casefold() for path in workspace.iterdir() if path.is_file()}
    language = (
        "python" if ".py" in suffixes or (workspace / "pyproject.toml").exists()
        else "typescript" if suffixes & {".ts", ".tsx"} or (workspace / "tsconfig.json").exists()
        else "javascript" if suffixes & {".js", ".jsx"} or (workspace / "package.json").exists()
        else "rust" if ".rs" in suffixes or (workspace / "Cargo.toml").exists()
        else "go" if ".go" in suffixes or (workspace / "go.mod").exists()
        else "unknown"
    )
    runner = ""
    if language == "python":
        has_test_files = any(
            path.is_file() and (path.name.startswith("test_") or path.name.endswith("_test.py"))
            for path in workspace.iterdir()
        )
        runner = "pytest" if ((workspace / "pytest.ini").exists() or (workspace / "tests").is_dir() or has_test_files) else "compileall"
    return CodeTaskSpec(language=language, runner=runner, target_paths=tuple(dict.fromkeys(mentioned)))

