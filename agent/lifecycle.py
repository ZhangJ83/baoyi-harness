"""Traceable workspace and artifact lifecycle for 小朴 runs."""
from __future__ import annotations

import hashlib
import json
import shutil
import uuid
import os
import re
import threading
from enum import Enum
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Protocol

from . import config

INPUT_SUFFIXES = {".pptx", ".ppt", ".xlsx", ".xls", ".csv", ".html", ".htm", ".pdf", ".docx", ".txt", ".md", ".png", ".jpg", ".jpeg", ".svg"}
INSTRUCTION_NAMES = {"AGENTS.md", "AGENTS.override.md", "XIAOPU.md", "README.md"}


class RecordMode(str, Enum):
    """Persistence depth; never a controller or verification policy."""

    MINIMAL = "minimal"
    AUDIT = "audit"
    RESEARCH = "research"

    @classmethod
    def parse(cls, value: str | "RecordMode" | None) -> "RecordMode":
        if isinstance(value, cls):
            return value
        normalized = str(value or config.record_mode()).strip().lower()
        try:
            return cls(normalized)
        except ValueError:
            return cls.AUDIT


class EventSink(Protocol):
    """Side-effect-only destination for operational journal rows."""

    def emit(self, row: dict[str, Any]) -> None: ...


class NullEventSink:
    """No-op sink used after recording becomes unavailable."""

    def emit(self, row: dict[str, Any]) -> None:
        return None


class JsonlEventSink:
    def __init__(self, path: Path):
        self.path = path

    def emit(self, row: dict[str, Any]) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


class BestEffortEventSink:
    """Circuit-break a failed observer so it cannot fail or stall the run."""

    def __init__(
        self,
        sink: EventSink,
        on_error: Callable[[str, Exception], None] | None = None,
    ):
        self._sink: EventSink = sink
        self._on_error = on_error
        self.disabled = False

    def emit(self, row: dict[str, Any]) -> None:
        if self.disabled:
            return
        try:
            self._sink.emit(row)
        except Exception as exc:  # recording is an observer, never a task gate
            self.disabled = True
            self._sink = NullEventSink()
            if self._on_error is not None:
                self._on_error("event_sink", exc)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def discover_workspace(root: Path | None = None, limit: int = 240) -> dict[str, Any]:
    root = (root or config.sandbox_root()).resolve()
    ignored = {".git", ".xiaopu", "__pycache__", "node_modules"}
    files: list[Path] = []
    for current, dirs, names in os.walk(root):
        dirs[:] = [name for name in dirs if name not in ignored and not name.startswith(".pytest")]
        for name in names:
            files.append(Path(current) / name)
            if len(files) >= limit:
                break
        if len(files) >= limit:
            break
    instructions, task_files, inputs = [], [], []
    for path in files:
        rel = str(path.relative_to(root))
        lowered = path.name.lower()
        if path.name in INSTRUCTION_NAMES or path.name.endswith("SKILL.md"):
            instructions.append(rel)
        if any(token in lowered for token in ("task", "brief", "request", "manifest", "rubric")):
            task_files.append(rel)
        if path.suffix.lower() in INPUT_SUFFIXES and ".xiaopu" not in path.parts:
            inputs.append({"path": rel, "suffix": path.suffix.lower(), "bytes": path.stat().st_size})
    expected = [item["path"] for item in inputs if item["suffix"] == ".pptx" and any(token in Path(item["path"]).stem.lower() for token in ("final", "output", "deliverable"))]
    return {
        "workspace": str(root),
        "instructions": instructions,
        "task_files": task_files,
        "inputs": inputs,
        "expected_outputs": expected,
        "available_routes": {
            "ppt_edit": "native ppt tools / python-pptx",
            "render": "PowerPoint COM on Windows; LibreOffice fallback elsewhere",
            "inspect": "structural geometry + rendered pixel audit",
        },
        "truncated": len(files) >= limit,
    }


class RunRecorder:
    """Best-effort operational evidence plus artifact/provenance manifests.

    The in-memory manifest remains available to lifecycle policies, while every
    persistence action is observational and failure-isolated.  The working-copy
    operation is intentionally still strict because preserving the source file
    is part of execution correctness, not trajectory collection.
    """

    _MINIMAL_EVENTS = {
        "artifact_written",
        "verification",
        "run_completed",
        "working_copy_created",
    }

    def __init__(
        self,
        goal: str,
        model: str,
        provider: str,
        root: Path | None = None,
        mode: str | RecordMode | None = None,
        event_sink: EventSink | None = None,
    ):
        self.workspace = (root or config.sandbox_root()).resolve()
        self.mode = RecordMode.parse(mode)
        self.run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
        self.root = self.workspace / ".xiaopu" / "runs" / self.run_id
        self.work = self.root / "working"
        self.evidence = self.root / "evidence"
        self.steps_path = self.root / "steps.jsonl"
        self.provenance_path = self.root / "provenance.jsonl"
        self.manifest_path = self.root / "run_manifest.json"
        self._sequence = 0
        self._lock = threading.RLock()
        self._record_failures = 0
        self._last_record_error = ""
        # A journal directory is optional.  If it cannot be created, the run
        # continues with in-memory evidence; execution paths create their own
        # required destinations when they actually need to write an artifact.
        self._best_effort("recorder_init", lambda: self.work.mkdir(parents=True, exist_ok=True))
        self._best_effort("recorder_init", lambda: self.evidence.mkdir(parents=True, exist_ok=True))
        self._recorded_inputs: set[tuple[str, str, str]] = set()
        self._working_by_source: dict[Path, Path] = {}
        self._source_by_working: dict[Path, Path] = {}
        self._event_sink = BestEffortEventSink(
            event_sink or JsonlEventSink(self.steps_path),
            self._record_failure,
        )
        self.manifest: dict[str, Any] = {
            "schema": "xiaopu-run-v1",
            "run_id": self.run_id,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "goal": goal,
            "agent": "小朴 (Xiaopu)",
            "model": model,
            "provider": provider,
            "record_mode": self.mode.value,
            "recording_health": {
                "failures": self._record_failures,
                "last_error": self._last_record_error,
            },
            "workspace": str(self.workspace),
            "status": "running",
            "artifacts": [],
            "checks": [],
            "source_evidence_boundary": "platform mechanisms are source-supported; PPT repair policies are Xiaopu implementation informed by observed trajectories",
        }
        self._write_manifest()

    def _record_failure(self, stage: str, exc: Exception) -> None:
        """Keep recorder health in memory without recursively writing it."""
        with self._lock:
            self._record_failures += 1
            self._last_record_error = f"{stage}: {type(exc).__name__}: {exc}"[:1000]
            manifest = getattr(self, "manifest", None)
            if isinstance(manifest, dict):
                manifest["recording_health"] = {
                    "failures": self._record_failures,
                    "last_error": self._last_record_error,
                }

    def _best_effort(self, stage: str, action: Callable[[], Any], default: Any = None) -> Any:
        try:
            return action()
        except Exception as exc:  # journal/provenance failure must not fail work
            self._record_failure(stage, exc)
            return default

    def _write_manifest(self) -> None:
        with self._lock:
            self._best_effort(
                "manifest",
                lambda: self.manifest_path.write_text(
                    json.dumps(self.manifest, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                ),
            )

    def event(self, kind: str, **payload: Any) -> None:
        from .redact import redact
        if self.mode is RecordMode.MINIMAL and kind not in self._MINIMAL_EVENTS:
            return
        # The append-only trace is evidence, not a secret store. Redact all
        # string leaves before persistence while preserving structured fields.
        max_chars = {
            RecordMode.MINIMAL: 512,
            RecordMode.AUDIT: 2000,
            RecordMode.RESEARCH: 12000,
        }[self.mode]

        def clean(value: Any) -> Any:
            if isinstance(value, str):
                clean_text = redact(value)
                if len(clean_text) > max_chars:
                    head = max_chars * 3 // 4
                    tail = max_chars - head
                    clean_text = clean_text[:head] + f"\n[record payload truncated: {len(clean_text) - max_chars} chars]\n" + clean_text[-tail:]
                return clean_text
            if isinstance(value, dict):
                return {key: clean(item) for key, item in value.items()}
            if isinstance(value, list):
                return [clean(item) for item in value]
            return value
        with self._lock:
            self._sequence += 1
            row = clean({"sequence": self._sequence, "timestamp": datetime.now(timezone.utc).isoformat(), "kind": kind, **payload})
            self._event_sink.emit(row)

    def record_input(self, path: Path, purpose: str = "input") -> None:
        path = path.resolve()
        if not path.is_file():
            return
        digest = self._best_effort("input_hash", lambda: _sha256(path))
        if digest is None:
            return
        identity = (str(path), digest, purpose)
        with self._lock:
            if identity in self._recorded_inputs:
                return
            self._recorded_inputs.add(identity)
        row = {"source": str(path), "sha256": digest, "bytes": path.stat().st_size, "purpose": purpose}
        def append() -> None:
            with self._lock, self.provenance_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")

        self._best_effort("provenance", append)
        self.event("input_read", **row)

    def bind_source(self, source: Path, output: str, usage: str) -> None:
        self.record_input(source, purpose=usage)
        row = {"source": str(source.resolve()), "output": output, "usage": usage, "relation": "source-to-output"}
        def append() -> None:
            with self._lock, self.provenance_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")

        self._best_effort("provenance", append)

    def working_copy(self, source: Path) -> Path:
        source = source.resolve()
        with self._lock:
            if source in self._source_by_working:
                return source
            existing = self._working_by_source.get(source)
            fresh = False
            if existing is not None and existing.is_file():
                try:
                    fresh = (
                        source.stat().st_size == existing.stat().st_size
                        and source.stat().st_mtime_ns <= existing.stat().st_mtime_ns
                    )
                except OSError:
                    fresh = False
            if existing is not None and fresh:
                return existing
        self.record_input(source, "editable-source")
        # Source preservation is execution correctness, not optional
        # trajectory bookkeeping, so failure here must remain visible.
        self.work.mkdir(parents=True, exist_ok=True)
        target = self.work / f"{source.stem}.working{source.suffix}"
        # The persisted deliverable can legitimately change mid-run (save then
        # reopen for repair).  A cached working copy would silently roll the
        # draft back to an older revision, so refresh whenever source changed.
        if existing is not None and existing.is_file() and not fresh:
            try:
                existing.unlink()
            except OSError:
                pass
        shutil.copy2(source, target)
        target = target.resolve()
        with self._lock:
            self._working_by_source[source] = target
            self._source_by_working[target] = source
        self.event("working_copy_created", source=str(source), working_copy=str(target), source_sha256=_sha256(source))
        return target

    def artifact(self, path: Path, role: str = "final") -> None:
        path = path.resolve()
        if not path.is_file():
            return
        digest = self._best_effort("artifact_hash", lambda: _sha256(path))
        size = self._best_effort("artifact_stat", lambda: path.stat().st_size)
        row = {"path": str(path), "role": role, "sha256": digest or "unavailable", "bytes": size if size is not None else -1}
        with self._lock:
            identity = (row["path"], row["role"], row["sha256"])
            existing = {(item.get("path"), item.get("role"), item.get("sha256")) for item in self.manifest["artifacts"]}
            if identity not in existing:
                self.manifest["artifacts"].append(row)
        self.event("artifact_written", **row)
        self._write_manifest()

    def check(self, name: str, passed: bool, evidence: str) -> None:
        row = {"name": name, "passed": passed, "evidence": evidence[:2000]}
        with self._lock:
            self.manifest["checks"].append(row)
        self.event("verification", **row)
        self._write_manifest()

    def finish(self, summary: str, state: Any, stop_reason: str = "end_turn") -> None:
        self.manifest.update({
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "stop_reason": stop_reason,
            "summary": summary,
            "tool_calls": state.tool_calls,
            "tokens": state.total_tokens,
            "mutation_epoch": state.mutation_epoch,
            "repair_attempts": getattr(state, "repair_attempts", 0),
            "changed_files": sorted(state.changed_files),
            "trajectory": str(self.steps_path),
            "provenance": str(self.provenance_path),
        })
        self.event("run_completed", stop_reason=stop_reason, summary=summary)
        self._write_manifest()
        if self.mode is not RecordMode.MINIMAL:
            self._best_effort("trajectory_export", lambda: self._materialize_task_trajectory(state))

    def _task_root(self) -> Path | None:
        """Resolve a single task directory named in the goal, if present."""
        from .intake import task_root_from_prompt
        return task_root_from_prompt(str(self.manifest.get("goal", "")), self.workspace)

    def _materialize_task_trajectory(self, state: Any) -> None:
        """Export truthful harness records into a task's trajectory contract.

        This removes trajectory bookkeeping from model tool calls. The
        contract directory is a harness-owned ``latest run`` view, so its
        generated files are refreshed on every completed run. Immutable,
        per-run originals remain under ``.xiaopu/runs/<run_id>``.
        """
        task_root = self._task_root()
        if task_root is None or not (task_root / "TRAJECTORY_CAPTURE_CONTRACT.md").is_file():
            return
        target = task_root / "trajectory"
        target.mkdir(parents=True, exist_ok=True)
        steps_target = target / "steps.jsonl"
        shutil.copy2(self.steps_path, steps_target)
        metadata = {
            "benchmark": "benchmark_mini_v0.1",
            "protocol": "trajectory-capture",
            "agent": "小朴 (Xiaopu)",
            "model": self.manifest.get("model"),
            "mode": "ppt-harness",
            "task_id": task_root.name,
            "session_id": self.run_id,
            "started_at": self.manifest.get("started_at"),
            "completed_at": self.manifest.get("completed_at"),
            "trajectory_source": "harness-recorded",
            "record_mode": self.mode.value,
        }
        files = {
            "run_metadata.json": json.dumps(metadata, ensure_ascii=False, indent=2),
            "plan.md": f"# Plan\n\nGoal: {self.manifest.get('goal', '')}\n\nRoute: inspect affected slides once → edit → save → verify → finish.\n",
            "reads.md": "# Reads\n\nSee `steps.jsonl` input_read and tool events; provenance is recorded by content hash.\n",
            "checks.md": "# Checks\n\n" + "\n".join(f"- [{'x' if item.get('passed') else ' '}] {item.get('name')}: {item.get('evidence')}" for item in self.manifest.get("checks", [])) + "\n",
            "repairs.md": f"# Repairs\n\nRepair attempts: {getattr(state, 'repair_attempts', 0)}. See `steps.jsonl` for observed defects and targeted repairs.\n",
            "artifacts.md": "# Artifacts\n\n" + "\n".join(f"- `{item.get('path')}` — {item.get('role')}, sha256 `{item.get('sha256')}`" for item in self.manifest.get("artifacts", [])) + "\n",
        }
        for name, content in files.items():
            path = target / name
            path.write_text(content, encoding="utf-8")

    @property
    def completed(self) -> bool:
        return self.manifest.get("status") == "completed"

    @property
    def record_failures(self) -> int:
        return self._record_failures

    @property
    def recording_degraded(self) -> bool:
        return self._record_failures > 0
