"""Filesystem tools, sandboxed to WORKSPACE."""
import os
import re
import json
from pathlib import Path
from typing import Any

from .. import config
from ..permissions import Decision, evaluate_shell, path_within

Schema = dict[str, Any]


def _root():
    return config.sandbox_root()


def _safe_environment() -> dict[str, str]:
    env = os.environ.copy()
    for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY"):
        env.pop(name, None)
    return env


def _resolve(rel: str) -> Path:
    root = _root()
    p = (root / rel).resolve()
    if not path_within(root, p):
        raise PermissionError(f"path escapes workspace sandbox: {rel}")
    return p


def _make(name: str, description: str, params: dict[str, dict], required: list[str], fn):
    return (
        {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {"type": "object", "properties": params, "required": required},
            },
        },
        fn,
    )


def _read(h, path: str, max_chars: int = 12000, start_line: int = 1, end_line: int | None = None):
    p = _resolve(path)
    if not p.exists():
        return f"not found: {path}"
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    if not lines:
        return "(empty file)"
    if start_line < 1:
        raise ValueError("start_line must be >= 1")
    if start_line > len(lines):
        raise ValueError(f"start_line {start_line} exceeds file length {len(lines)}")
    stop = min(len(lines), end_line) if end_line is not None else len(lines)
    if stop < start_line:
        raise ValueError("end_line must be >= start_line")
    text = "\n".join(f"{number:6d} | {lines[number - 1]}" for number in range(start_line, stop + 1))
    if len(text) > max_chars:
        head = text[: max_chars * 3 // 4]
        tail = text[-max_chars // 4 :]
        return head + f"\n[truncated {len(text) - len(head) - len(tail)} chars]\n" + tail
    return text


def _read_many(h, paths: list[str], max_chars_per_source: int = 30000):
    if not paths or len(paths) > 32:
        raise ValueError("read_many requires 1-32 paths")
    from ..office_ir import build_content_ir, persist_content_ir
    resolved = [_resolve(path) for path in paths]
    missing = [paths[index] for index, path in enumerate(resolved) if not path.is_file()]
    if missing:
        raise FileNotFoundError(", ".join(missing))
    ir = build_content_ir(resolved, max_chars_per_source=max_chars_per_source)
    ir_path = persist_content_ir(ir, _root())
    if getattr(h, "recorder", None):
        for path in resolved:
            h.recorder.record_input(path, purpose="content-ir-source")
    if getattr(h, "state", None) is not None:
        for source in ir.sources:
            h.state.record_fact(f"source:{source.path}", f"kind={source.kind} sha256={source.sha256} chars={len(source.text)}")
            h.state.source_paths.add(source.path)
        brief = ir.to_model_dict(max_total_chars=12000)
        brief["full_ir_artifact"] = str(ir_path.relative_to(_root()))
        h.state.content_brief = json.dumps(brief, ensure_ascii=False)
    return h.state.content_brief if getattr(h, "state", None) is not None else json.dumps(ir.to_model_dict(), ensure_ascii=False)


def _list_dir(h, path: str = ""):
    p = _resolve(path)
    if not p.exists() or not p.is_dir():
        return f"not a dir: {path}"
    return "\n".join(sorted(x.name for x in p.iterdir()))


def _glob(h, pattern: str = "**/*", limit: int = 500):
    root = _root()
    matches = [str(p.relative_to(root)) for p in root.glob(pattern) if p.is_file()]
    return "\n".join(matches[:limit]) + (f"\n[truncated: {len(matches)} matches]" if len(matches) > limit else "")


def _search(h, query: str, pattern: str = "**/*", limit: int = 200):
    root = _root()
    hits = []
    for p in root.glob(pattern):
        if not p.is_file() or p.stat().st_size > 2_000_000:
            continue
        try:
            for number, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if query.lower() in line.lower():
                    hits.append(f"{p.relative_to(root)}:{number}:{line[:300]}")
                    if len(hits) >= limit:
                        return "\n".join(hits) + "\n[truncated]"
        except OSError:
            continue
    return "\n".join(hits) or "no matches"


def _run_file_transaction(
    h,
    *,
    root: Path,
    paths: list[str | Path],
    execute,
    postcondition,
    changed: list[str],
):
    """Run one ordinary file mutation through the shared safety envelope."""

    from ..action_transaction import ScopeViolation
    from ..file_transaction_adapter import (
        FileTransactionAdapter,
        LinkedCancellationToken,
        recorder_event_sink,
    )
    from ..transaction_journal import DurableTransactionJournal

    control = getattr(h, "_run_control", None)
    cancellation = LinkedCancellationToken(
        lambda: bool(control is not None and control.cancelled.is_set())
    )

    adapter = FileTransactionAdapter(
        workspace=root,
        paths=paths,
        execute=execute,
        postcondition=postcondition,
        commit=lambda _value, _paths: h.state.record_changes(changed),
        cancellation=cancellation,
        event_sink=recorder_event_sink(getattr(h, "recorder", None)),
        journal=DurableTransactionJournal(root),
    )
    try:
        return adapter.run()
    except ScopeViolation as exc:
        denied = next(iter(adapter.denied_paths), None)
        label = str(denied) if denied is not None else str(exc)
        raise PermissionError(f"path escapes workspace sandbox: {label}") from exc


def _edit(h, path: str, old: str, new: str, replace_all: bool = False):
    p = _resolve(path)
    root = _root().resolve()
    holder: dict[str, Any] = {}

    def execute(paths, token):
        token.raise_if_cancelled("single-file edit read")
        target = paths[0]
        text = target.read_text(encoding="utf-8")
        count = text.count(old)
        if count == 0:
            raise ValueError("old text not found")
        if count > 1 and not replace_all:
            raise ValueError(
                f"old text is not unique ({count} matches); provide more context or set replace_all"
            )
        replacements = count if replace_all else 1
        updated = text.replace(old, new) if replace_all else text.replace(old, new, 1)
        token.raise_if_cancelled("single-file edit write")
        target.write_text(updated, encoding="utf-8")
        holder.update(updated=updated, replacements=replacements)
        return replacements

    def postcondition(_value, paths):
        return paths[0].read_text(encoding="utf-8") == holder["updated"]

    _run_file_transaction(
        h,
        root=root,
        paths=[p],
        execute=execute,
        postcondition=postcondition,
        changed=[str(p.relative_to(root))],
    )
    return f"edited {path}: {holder['replacements']} replacement(s)"


def _apply_edits(h, edits: list[dict]):
    if not edits or len(edits) > 50:
        raise ValueError("apply_edits requires 1-50 edits")

    root = _root().resolve()
    staged: dict[Path, str] = {}
    totals: dict[Path, int] = {}

    def execute(paths: tuple[Path, ...], token):
        del paths
        for index, edit in enumerate(edits):
            token.raise_if_cancelled("file edit staging")
            raw_path = edit["path"]
            candidate = Path(raw_path)
            p = (candidate if candidate.is_absolute() else root / candidate).resolve()
            if not p.is_file():
                raise FileNotFoundError(raw_path)
            current = staged.get(p, p.read_text(encoding="utf-8"))
            old, new = edit["old"], edit["new"]
            if not old:
                raise ValueError(f"edit {index}: old text cannot be empty")
            count = current.count(old)
            expected = int(edit.get("expected_replacements", 1))
            if expected < 1:
                raise ValueError(f"edit {index}: expected_replacements must be >= 1")
            if count != expected:
                raise ValueError(
                    f"edit {index} ({raw_path}): expected {expected} matches, "
                    f"found {count}; no files changed"
                )
            staged[p] = current.replace(old, new, expected)
            totals[p] = totals.get(p, 0) + expected
        for p, content in staged.items():
            token.raise_if_cancelled("file edit write")
            p.write_text(content, encoding="utf-8")
        return tuple(staged)

    def postcondition(_value, _paths):
        return all(path.read_text(encoding="utf-8") == content for path, content in staged.items())

    requested_paths = [edit["path"] for edit in edits]
    changed = []
    for raw in requested_paths:
        candidate = Path(raw)
        resolved = (candidate if candidate.is_absolute() else root / candidate).resolve()
        try:
            label = str(resolved.relative_to(root))
        except ValueError:
            label = str(resolved)
        if label not in changed:
            changed.append(label)
    _run_file_transaction(
        h,
        root=root,
        paths=[edit["path"] for edit in edits],
        execute=execute,
        postcondition=postcondition,
        changed=changed,
    )

    return "atomic edits applied:\n" + "\n".join(
        f"{p.relative_to(root)}: {totals[p]} replacement(s)" for p in staged
    )


def _write(h, path: str, content: str):
    p = _resolve(path)
    root = _root().resolve()

    def execute(paths, token):
        target = paths[0]
        token.raise_if_cancelled("single-file write prepare")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return len(content)

    def postcondition(_value, paths):
        return paths[0].is_file() and paths[0].read_text(encoding="utf-8") == content

    _run_file_transaction(
        h,
        root=root,
        paths=[p],
        execute=execute,
        postcondition=postcondition,
        changed=[str(p.relative_to(root))],
    )
    return f"wrote {len(content)} chars -> {path}"


def _record_file_verification(h, passed: bool, summary: str, scope: str) -> None:
    """Publish current-epoch file evidence without making telemetry mandatory."""

    state = h.state
    evidence_summary = f"{summary}; targets={scope[:2000]}"
    state.record_evidence(
        "file_verification",
        evidence_summary,
        passed=passed,
        # ``finish`` consumes workspace-scoped evidence.  The concrete paths
        # remain in the summary/recorder instead of replacing that scope.
        scope="workspace",
    )
    if passed:
        state.unresolved_checks.discard("file_verification")
        if not state.unresolved_checks:
            state.last_verification_failed = False
    else:
        state.unresolved_checks.add("file_verification")
        state.last_verification_failed = True
        state.last_verification_epoch = state.mutation_epoch
    recorder = getattr(h, "recorder", None)
    check = getattr(recorder, "check", None)
    if callable(check):
        try:
            check("file_verification", passed, evidence_summary)
        except Exception:
            # Verification truth lives in RunState; recording is observational.
            pass


def _verify_files(
    h,
    paths: list[str],
    contains: dict[str, list[str]] | None = None,
):
    """Verify regular workspace files and optional per-file UTF-8 substrings."""

    if not paths or len(paths) > 32:
        raise ValueError("verify_files requires 1-32 paths")
    contains = contains or {}
    if not isinstance(contains, dict):
        raise TypeError("contains must be an object mapping paths to string arrays")

    resolved: dict[Path, str] = {}
    assertions: dict[Path, list[str]] = {}
    scope = ", ".join(paths)
    try:
        for raw in paths:
            if not isinstance(raw, str) or not raw.strip():
                raise ValueError("verify_files paths must be non-empty strings")
            resolved.setdefault(_resolve(raw), raw)
        for raw, needles in contains.items():
            if not isinstance(raw, str) or not raw.strip():
                raise ValueError("contains keys must be non-empty paths")
            target = _resolve(raw)
            if target not in resolved:
                raise ValueError(f"contains path must also appear in paths: {raw}")
            if not isinstance(needles, list) or any(
                not isinstance(needle, str) or not needle for needle in needles
            ):
                raise ValueError(f"contains[{raw}] must be an array of non-empty strings")
            assertions[target] = needles
    except Exception as exc:
        summary = f"file verification failed before reading: {type(exc).__name__}: {exc}"
        _record_file_verification(h, False, summary, scope)
        raise

    failures: list[str] = []
    assertion_count = 0
    for target, raw in resolved.items():
        if not target.exists():
            failures.append(f"{raw}: not found")
            continue
        if not target.is_file():
            failures.append(f"{raw}: not a regular file")
            continue
        try:
            text = target.read_text(encoding="utf-8", errors="strict")
        except (OSError, UnicodeError) as exc:
            failures.append(f"{raw}: not readable as strict UTF-8 ({type(exc).__name__})")
            continue
        for needle in assertions.get(target, []):
            assertion_count += 1
            if needle not in text:
                failures.append(f"{raw}: missing required text {needle!r}")

    if failures:
        summary = "file verification failed: " + "; ".join(failures)
        _record_file_verification(h, False, summary, scope)
        raise ValueError(summary)

    summary = (
        f"verified {len(resolved)} file(s): regular files, strict UTF-8 readable; "
        f"{assertion_count} content assertion(s) passed"
    )
    _record_file_verification(h, True, summary, scope)
    return summary


_CHECK_RUNNERS = {
    "pytest": lambda targets: [__import__("sys").executable, "-m", "pytest", *targets],
    "unittest": lambda targets: [__import__("sys").executable, "-m", "unittest", *targets],
    "compileall": lambda targets: [__import__("sys").executable, "-m", "compileall", "-q", *(targets or ["."])],
}


def _run_checks(h, runner: str, targets: list[str] | None = None, timeout: int = 120):
    """Run a fixed, argument-vector verifier without enabling arbitrary shell."""
    import subprocess

    if runner not in _CHECK_RUNNERS:
        raise ValueError(f"unsupported check runner: {runner}")
    targets = targets or []
    if len(targets) > 32:
        raise ValueError("run_checks allows at most 32 targets")
    normalized: list[str] = []
    for target in targets:
        if not isinstance(target, str) or not target.strip():
            raise ValueError("run_checks targets must be non-empty strings")
        candidate = _resolve(target)
        normalized.append(str(candidate.relative_to(_root())))
    command = _CHECK_RUNNERS[runner](normalized)
    timeout = max(1, min(timeout, config.max_command_timeout()))
    try:
        proc = subprocess.run(
            command,
            cwd=str(_root()),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=_safe_environment(),
            timeout=timeout,
            shell=False,
        )
    except subprocess.TimeoutExpired as exc:
        summary = f"{runner} timed out after {timeout}s"
        h.state.record_evidence("code_check", summary, passed=False, backend=runner)
        h.state.unresolved_checks.add("code_check")
        raise TimeoutError(summary) from exc
    output = ((proc.stdout or "") + ("\n[stderr]\n" + proc.stderr if proc.stderr else "")).strip()
    summary = f"{runner} exit_code={proc.returncode}; targets={normalized or ['.']}"
    h.state.record_evidence("code_check", summary, passed=proc.returncode == 0, backend=runner)
    if proc.returncode != 0:
        h.state.unresolved_checks.add("code_check")
        raise ValueError((summary + "\n" + output)[:16000])
    h.state.unresolved_checks.discard("code_check")
    return (summary + "\n" + (output or "(no output)"))[:16000]


def _run(h, command: str, timeout: int = 60):
    """Run a shell command from the workspace. Prefer `python` scripts via run_code."""
    import subprocess
    root = _root()
    permission = evaluate_shell(command, config.command_policy(), config.isolated_benchmark())
    if permission.decision is not Decision.ALLOW:
        return f"PERMISSION {permission.decision.value.upper()}: {permission.reason}"
    timeout = max(1, min(timeout, config.max_command_timeout()))
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=_safe_environment(),
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return f"exit_code=124\nTIMEOUT after {timeout}s\n{stdout}\n[stderr]\n{stderr}"[:16000]
    out = (proc.stdout or "") + "\n[stderr]\n" + (proc.stderr or "")
    result = f"exit_code={proc.returncode}\n{out.strip()}"[:16000]
    verifier = re.search(r"\b(pytest|unittest|tox|nox|cargo\s+test|go\s+test|npm\s+test|pnpm\s+test|bun\s+test|gradle\w*\s+test|mvn\w*\s+test|make\s+(?:test|check)|ruff|mypy|pyright|eslint|tsc|cargo\s+check|compileall)\b", command, re.IGNORECASE)
    if proc.returncode == 0 and verifier:
        h.state.record_evidence("shell_verifier", f"shell passed: {command[:200]}")
    return result


def _run_py(h, code: str, timeout: int = 60, save_as: str = ""):
    """Run a Python snippet in the sandbox; may use python-pptx (import pptx)."""
    import subprocess
    import sys
    root = _root()
    if save_as:
        dst = _resolve(save_as)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(code, encoding="utf-8")
    else:
        dst = root / "_inline.py"
        dst.write_text(code, encoding="utf-8")
    timeout = max(1, min(timeout, config.max_command_timeout()))
    try:
        proc = subprocess.run(
            [sys.executable, str(dst)],
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=_safe_environment(),
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return f"exit_code=124\nTIMEOUT after {timeout}s\n{stdout}\n[stderr]\n{stderr}"[:16000]
    result = f"exit_code={proc.returncode}\n{(proc.stdout or '')}\n[stderr]\n{(proc.stderr or '')}"[:16000]
    if proc.returncode == 0 and re.search(r"\b(assert|unittest|pytest|compile)\b", code):
        h.state.record_evidence("python_verifier", f"python passed: {dst.name}")
    return result


def _git(h, arguments: list[str], max_chars: int = 16000) -> str:
    import subprocess
    proc = subprocess.run(
        ["git", *arguments],
        cwd=str(_root()),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_safe_environment(),
        timeout=30,
    )
    output = ((proc.stdout or "") + ("\n[stderr]\n" + proc.stderr if proc.stderr else "")).strip()
    if len(output) > max_chars:
        output = output[: max_chars * 3 // 4] + "\n[truncated]\n" + output[-max_chars // 4 :]
    return f"exit_code={proc.returncode}\n{output or '(no output)'}"


fs_tools = [
    _make(
        "read_file",
        "Read a line-numbered UTF-8 text range. Use start_line/end_line to avoid flooding context.",
        {"path": {"type": "string"}, "max_chars": {"type": "integer"}, "start_line": {"type": "integer"}, "end_line": {"type": "integer"}},
        ["path"],
        lambda h, **kw: _read(h, kw["path"], kw.get("max_chars", 12000), kw.get("start_line", 1), kw.get("end_line")),
    ),
    _make(
        "read_many",
        "Batch-extract 1-32 supplied text/HTML/CSV/PPTX/DOCX/XLSX sources into a provenance-preserving ContentIR. Prefer this over repeated read/list calls for office tasks.",
        {"paths": {"type": "array", "minItems": 1, "maxItems": 32, "items": {"type": "string"}}, "max_chars_per_source": {"type": "integer", "maximum": 30000}},
        ["paths"],
        lambda h, **kw: _read_many(h, kw["paths"], kw.get("max_chars_per_source", 30000)),
    ),
    _make(
        "write_file",
        "Write text content to a file in the workspace (overwrites).",
        {"path": {"type": "string"}, "content": {"type": "string"}},
        ["path", "content"],
        lambda h, **kw: _write(h, kw["path"], kw["content"]),
    ),
    _make(
        "list_dir",
        "List files/dirs inside a workspace subdirectory.",
        {"path": {"type": "string"}},
        [],
        lambda h, **kw: _list_dir(h, kw.get("path", "")),
    ),
    _make(
        "glob_files",
        "List workspace files matching a glob such as **/*.py. Use before broad reads.",
        {"pattern": {"type": "string"}, "limit": {"type": "integer"}},
        [],
        lambda h, **kw: _glob(h, kw.get("pattern", "**/*"), kw.get("limit", 500)),
    ),
    _make(
        "search_text",
        "Search text case-insensitively across workspace files and return path:line matches.",
        {"query": {"type": "string"}, "pattern": {"type": "string"}, "limit": {"type": "integer"}},
        ["query"],
        lambda h, **kw: _search(h, kw["query"], kw.get("pattern", "**/*"), kw.get("limit", 200)),
    ),
    _make(
        "edit_file",
        "Replace an exact text span in a UTF-8 file. The old text must be unique unless replace_all is true.",
        {"path": {"type": "string"}, "old": {"type": "string"}, "new": {"type": "string"}, "replace_all": {"type": "boolean"}},
        ["path", "old", "new"],
        lambda h, **kw: _edit(h, kw["path"], kw["old"], kw["new"], kw.get("replace_all", False)),
    ),
    _make(
        "apply_edits",
        "Atomically apply 1-50 exact replacements across files. Every match count is checked before any file is written.",
        {"edits": {"type": "array", "minItems": 1, "maxItems": 50, "items": {"type": "object", "properties": {"path": {"type": "string"}, "old": {"type": "string"}, "new": {"type": "string"}, "expected_replacements": {"type": "integer"}}, "required": ["path", "old", "new"]}}},
        ["edits"],
        lambda h, **kw: _apply_edits(h, kw["edits"]),
    ),
    _make(
        "verify_files",
        "Verify 1-32 workspace files exist, are regular files, and decode as strict UTF-8. Optionally require per-file substrings with contains={path: [text, ...]}.",
        {
            "paths": {
                "type": "array",
                "minItems": 1,
                "maxItems": 32,
                "items": {"type": "string"},
            },
            "contains": {
                "type": "object",
                "description": "Optional mapping from a listed path to required UTF-8 substrings.",
            },
        },
        ["paths"],
        lambda h, **kw: _verify_files(h, kw["paths"], kw.get("contains")),
    ),
    _make(
        "run_checks",
        "Run a deterministic workspace verifier without arbitrary shell. Supported runners: pytest, unittest, compileall.",
        {
            "runner": {"type": "string", "enum": ["pytest", "unittest", "compileall"]},
            "targets": {"type": "array", "minItems": 0, "maxItems": 32, "items": {"type": "string"}},
            "timeout": {"type": "integer", "minimum": 1, "maximum": 600},
        },
        ["runner"],
        lambda h, **kw: _run_checks(h, kw["runner"], kw.get("targets"), kw.get("timeout", 120)),
    ),
    _make(
        "run_python",
        "Execute Python code in the sandbox (python-pptx available).",
        {"code": {"type": "string"}, "timeout": {"type": "integer"}},
        ["code"],
        lambda h, **kw: _run_py(h, kw["code"], kw.get("timeout", 60)),
    ),
    _make(
        "run_shell",
        "Run a shell command in the sandbox (use sparingly).",
        {"command": {"type": "string"}, "timeout": {"type": "integer"}},
        ["command"],
        lambda h, **kw: _run(h, kw["command"], kw.get("timeout", 60)),
    ),
    _make(
        "git_status",
        "Read repository status without invoking a shell. Use before and after edits.",
        {},
        [],
        lambda h, **kw: _git(h, ["status", "--short", "--branch"]),
    ),
    _make(
        "git_diff",
        "Read the current Git diff. Optionally restrict to one workspace-relative path.",
        {"path": {"type": "string"}, "staged": {"type": "boolean"}, "max_chars": {"type": "integer"}},
        [],
        lambda h, **kw: _git(h, ["diff", *(["--cached"] if kw.get("staged") else []), "--", *([kw["path"]] if kw.get("path") else [])], kw.get("max_chars", 16000)),
    ),
]
