import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest

from agent.action_transaction import CancellationToken, ScopeViolation, TransactionCancelled
from agent.file_transaction_adapter import FileTransactionAdapter
from agent.state import RunState
from agent.tools.fs_tools import _apply_edits, _edit, _run_checks, _verify_files, _write
from agent.tools.registry import dispatch


class HarnessStub:
    def __init__(self):
        self.state = RunState()
        self.recorder = None
        self.deck = None
        self._done = None


def test_single_write_and_edit_use_one_transaction_epoch_each():
    with TemporaryDirectory() as tmp, patch("agent.tools.fs_tools._root", return_value=Path(tmp)):
        root = Path(tmp)
        harness = HarnessStub()

        assert _write(harness, "nested/note.txt", "alpha") == "wrote 5 chars -> nested/note.txt"
        assert (root / "nested/note.txt").read_text(encoding="utf-8") == "alpha"
        assert harness.state.mutation_epoch == 1

        assert _edit(harness, "nested/note.txt", "alpha", "beta") == "edited nested/note.txt: 1 replacement(s)"
        assert (root / "nested/note.txt").read_text(encoding="utf-8") == "beta"
        assert harness.state.mutation_epoch == 2


def test_single_write_rolls_back_new_file_when_postcondition_fails(monkeypatch):
    with TemporaryDirectory() as tmp, patch("agent.tools.fs_tools._root", return_value=Path(tmp)):
        root = Path(tmp)
        harness = HarnessStub()
        real_read = Path.read_text

        def corrupt_read(path, *args, **kwargs):
            if path.name == "new.txt" and path.exists():
                return "corrupt"
            return real_read(path, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", corrupt_read)
        with pytest.raises(Exception, match="postcondition"):
            _write(harness, "new.txt", "expected")

        assert not (root / "new.txt").exists()
        assert harness.state.mutation_epoch == 0


def test_file_transaction_success_commits_once_and_preserves_public_result():
    with TemporaryDirectory() as tmp, patch("agent.tools.fs_tools._root", return_value=Path(tmp)):
        root = Path(tmp)
        (root / "a.txt").write_text("alpha", encoding="utf-8")
        (root / "b.txt").write_text("beta", encoding="utf-8")
        harness = HarnessStub()

        output = _apply_edits(
            harness,
            [
                {"path": "a.txt", "old": "alpha", "new": "A"},
                {"path": "b.txt", "old": "beta", "new": "B"},
            ],
        )

        assert output == "atomic edits applied:\na.txt: 1 replacement(s)\nb.txt: 1 replacement(s)"
        assert (root / "a.txt").read_text(encoding="utf-8") == "A"
        assert (root / "b.txt").read_text(encoding="utf-8") == "B"
        assert harness.state.mutation_epoch == 1


def test_file_transaction_rejects_out_of_workspace_before_checkpoint_or_execute():
    with TemporaryDirectory() as tmp:
        root = Path(tmp) / "workspace"
        root.mkdir()
        outside = Path(tmp) / "outside.txt"
        outside.write_text("secret", encoding="utf-8")
        calls = []
        adapter = FileTransactionAdapter(
            workspace=root,
            paths=[outside],
            execute=lambda paths, token: calls.append("execute"),
            postcondition=lambda value, paths: True,
        )
        with patch.object(Path, "read_bytes", side_effect=AssertionError("checkpoint must not read")):
            with pytest.raises(ScopeViolation):
                adapter.run()

        assert calls == []
        assert outside.read_text(encoding="utf-8") == "secret"


def test_apply_edits_rolls_back_every_file_when_second_write_fails():
    with TemporaryDirectory() as tmp, patch("agent.tools.fs_tools._root", return_value=Path(tmp)):
        root = Path(tmp)
        first = root / "a.txt"
        second = root / "b.txt"
        first.write_text("alpha", encoding="utf-8")
        second.write_text("beta", encoding="utf-8")
        original_write = Path.write_text
        writes = 0

        def fail_second_write(path, content, *args, **kwargs):
            nonlocal writes
            writes += 1
            if writes == 2:
                raise OSError("simulated disk failure")
            return original_write(path, content, *args, **kwargs)

        harness = HarnessStub()
        with patch.object(Path, "write_text", fail_second_write):
            with pytest.raises(OSError, match="simulated disk failure"):
                _apply_edits(
                    harness,
                    [
                        {"path": "a.txt", "old": "alpha", "new": "A"},
                        {"path": "b.txt", "old": "beta", "new": "B"},
                    ],
                )

        assert first.read_text(encoding="utf-8") == "alpha"
        assert second.read_text(encoding="utf-8") == "beta"
        assert harness.state.mutation_epoch == 0


def test_file_transaction_cancellation_rolls_back_created_and_existing_paths():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        existing = root / "existing.txt"
        created = root / "created.txt"
        existing.write_text("before", encoding="utf-8")
        token = CancellationToken()

        def execute(paths, cancellation):
            paths[0].write_text("after", encoding="utf-8")
            paths[1].write_text("new", encoding="utf-8")
            cancellation.cancel()
            cancellation.raise_if_cancelled("between file writes and commit")

        adapter = FileTransactionAdapter(
            workspace=root,
            paths=[existing, created],
            execute=execute,
            postcondition=lambda value, paths: True,
            cancellation=token,
        )
        with pytest.raises(TransactionCancelled):
            adapter.run()

        assert existing.read_text(encoding="utf-8") == "before"
        assert not created.exists()


def test_broken_event_sink_does_not_change_file_commit():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        target = root / "a.txt"
        target.write_text("before", encoding="utf-8")

        def broken_sink(_event):
            raise OSError("telemetry unavailable")

        adapter = FileTransactionAdapter(
            workspace=root,
            paths=[target],
            execute=lambda paths, token: paths[0].write_text("after", encoding="utf-8"),
            postcondition=lambda value, paths: paths[0].read_text(encoding="utf-8") == "after",
            event_sink=broken_sink,
        )
        result = adapter.run()

        assert result.status == "committed"
        assert target.read_text(encoding="utf-8") == "after"


def test_verify_files_closes_safe_file_edit_and_finish_loop():
    with TemporaryDirectory() as tmp, patch("agent.tools.fs_tools._root", return_value=Path(tmp)):
        root = Path(tmp)
        harness = HarnessStub()
        _write(harness, "result.txt", "hello xiaopu")

        output = _verify_files(
            harness,
            ["result.txt"],
            {"result.txt": ["hello", "xiaopu"]},
        )

        assert "verified 1 file(s)" in output
        assert "2 content assertion(s) passed" in output
        assert harness.state.fresh_evidence()[0].kind == "file_verification"
        assert "file_verification" not in harness.state.unresolved_checks
        dispatch("finish", json.dumps({"summary": "verified output"}), harness)
        assert harness._done == "verified output"


def test_verify_files_failure_is_unresolved_and_not_fresh_evidence():
    with TemporaryDirectory() as tmp, patch("agent.tools.fs_tools._root", return_value=Path(tmp)):
        root = Path(tmp)
        (root / "result.txt").write_text("actual", encoding="utf-8")
        harness = HarnessStub()

        with pytest.raises(ValueError, match="missing required text"):
            _verify_files(harness, ["result.txt"], {"result.txt": ["expected"]})

        assert "file_verification" in harness.state.unresolved_checks
        assert harness.state.last_verification_failed
        assert harness.state.fresh_evidence() == []


def test_verify_files_rejects_non_utf8_and_unlisted_assertion_path():
    with TemporaryDirectory() as tmp, patch("agent.tools.fs_tools._root", return_value=Path(tmp)):
        root = Path(tmp)
        (root / "binary.dat").write_bytes(b"\xff\xfe")

        harness = HarnessStub()
        with pytest.raises(ValueError, match="strict UTF-8"):
            _verify_files(harness, ["binary.dat"])

        harness = HarnessStub()
        with pytest.raises(ValueError, match="must also appear in paths"):
            _verify_files(harness, ["binary.dat"], {"other.txt": ["x"]})
        assert "file_verification" in harness.state.unresolved_checks


def test_run_checks_compileall_produces_fresh_code_certificate():
    with TemporaryDirectory() as tmp, patch("agent.tools.fs_tools._root", return_value=Path(tmp)):
        root = Path(tmp)
        (root / "ok.py").write_text("value = 42\n", encoding="utf-8")
        harness = HarnessStub()
        harness.state.record_change("ok.py")

        output = _run_checks(harness, "compileall", ["ok.py"])

        assert "exit_code=0" in output
        certificate = harness.state.fresh_evidence()[0]
        assert certificate.kind == "code_check"
        assert certificate.backend == "compileall"


def test_run_checks_rejects_escape_and_failed_compile_is_unresolved():
    with TemporaryDirectory() as tmp, patch("agent.tools.fs_tools._root", return_value=Path(tmp)):
        root = Path(tmp)
        harness = HarnessStub()
        with pytest.raises(PermissionError):
            _run_checks(harness, "compileall", ["../outside.py"])
        (root / "bad.py").write_text("def broken(:\n", encoding="utf-8")
        with pytest.raises(ValueError, match="exit_code=1"):
            _run_checks(harness, "compileall", ["bad.py"])
        assert "code_check" in harness.state.unresolved_checks
