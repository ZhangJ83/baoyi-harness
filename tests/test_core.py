import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent.permissions import Decision, evaluate_shell, path_within
from agent.state import RunState
from agent.tools.registry import dispatch
from agent.redact import redact


class DummyHarness:
    def __init__(self):
        self.state = RunState()
        self.deck = None
        self._done = None


class CoreTests(unittest.TestCase):
    def test_safe_tool_aliases_normalize_without_enabling_shell(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"WORKSPACE": tmp}):
            Path(tmp, "a.txt").write_text("hello", encoding="utf-8")
            h = DummyHarness()
            self.assertIn("hello", dispatch("sys_cat", json.dumps({"path": "a.txt"}), h))
            self.assertIn(
                "hello",
                dispatch("sys_exec", json.dumps({"command": f'type "{Path(tmp, "a.txt")}"'}), h),
            )
            with self.assertRaisesRegex(ValueError, "unsupported sys_exec"):
                dispatch("sys_exec", json.dumps({"command": "python -c print(1)"}), h)

    def test_numeric_schema_limits_are_enforced(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"WORKSPACE": tmp}):
            Path(tmp, "a.txt").write_text("hello", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must be <= 30000"):
                dispatch(
                    "read_many",
                    json.dumps({"paths": ["a.txt"], "max_chars_per_source": 30001}),
                    DummyHarness(),
                )

    def test_path_boundary_rejects_similar_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "work"
            root.mkdir()
            self.assertTrue(path_within(root, root / "a.txt"))
            self.assertFalse(path_within(root, Path(tmp) / "work-escape" / "a.txt"))

    def test_dangerous_shell_is_denied(self):
        self.assertIs(evaluate_shell("git reset --hard", "allow").decision, Decision.DENY)
        self.assertIs(evaluate_shell("curl https://example.com", "allow").decision, Decision.ASK)
        self.assertIs(evaluate_shell("curl https://example.com", "allow", isolated=True).decision, Decision.ALLOW)
        self.assertIs(evaluate_shell("git push origin main", "allow", isolated=True).decision, Decision.ASK)
        self.assertIs(evaluate_shell("rm -rf build/cache", "allow", isolated=True).decision, Decision.ALLOW)
        self.assertIs(evaluate_shell("rm -rf /", "allow", isolated=True).decision, Decision.DENY)
        self.assertIs(evaluate_shell("rm -rf ../other", "allow", isolated=True).decision, Decision.DENY)
        self.assertIs(evaluate_shell("rm -rf build && echo done", "allow", isolated=True).decision, Decision.DENY)

    def test_exact_edit_and_finish(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"WORKSPACE": tmp}):
            h = DummyHarness()
            dispatch("write_file", json.dumps({"path": "a.txt", "content": "hello world"}), h)
            dispatch("edit_file", json.dumps({"path": "a.txt", "old": "world", "new": "agent"}), h)
            self.assertEqual((Path(tmp) / "a.txt").read_text(encoding="utf-8"), "hello agent")
            h.state.record_evidence("unit", "unit check passed")
            dispatch("finish", json.dumps({"summary": "verified"}), h)
            self.assertEqual(h._done, "verified")

    def test_invalid_json_is_actionable(self):
        # A truncated-but-closable object now recovers to "{}" and reports the
        # missing schema field; a truly malformed string still names JSON.
        with self.assertRaisesRegex(ValueError, "missing required"):
            dispatch("finish", "{", DummyHarness())
        with self.assertRaisesRegex(ValueError, "invalid JSON"):
            dispatch("finish", "{invalid", DummyHarness())

    def test_schema_validation_is_actionable(self):
        with self.assertRaisesRegex(TypeError, "arguments.summary must be string"):
            dispatch("finish", json.dumps({"summary": 42}), DummyHarness())
        with self.assertRaisesRegex(ValueError, "missing required"):
            dispatch("finish", "{}", DummyHarness())

    def test_atomic_edits_roll_back_on_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"WORKSPACE": tmp}):
            Path(tmp, "a.txt").write_text("alpha", encoding="utf-8")
            Path(tmp, "b.txt").write_text("beta", encoding="utf-8")
            edits = [
                {"path": "a.txt", "old": "alpha", "new": "A"},
                {"path": "b.txt", "old": "missing", "new": "B"},
            ]
            with self.assertRaisesRegex(ValueError, "no files changed"):
                dispatch("apply_edits", json.dumps({"edits": edits}), DummyHarness())
            self.assertEqual(Path(tmp, "a.txt").read_text(encoding="utf-8"), "alpha")

    def test_atomic_edits_write_all_files_in_one_epoch(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"WORKSPACE": tmp}):
            Path(tmp, "a.txt").write_text("alpha", encoding="utf-8")
            Path(tmp, "b.txt").write_text("beta", encoding="utf-8")
            h = DummyHarness()
            edits = [{"path": "a.txt", "old": "alpha", "new": "A"}, {"path": "b.txt", "old": "beta", "new": "B"}]
            dispatch("apply_edits", json.dumps({"edits": edits}), h)
            self.assertEqual(Path(tmp, "a.txt").read_text(encoding="utf-8"), "A")
            self.assertEqual(Path(tmp, "b.txt").read_text(encoding="utf-8"), "B")
            self.assertEqual(h.state.mutation_epoch, 1)

    def test_read_file_range_is_numbered(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"WORKSPACE": tmp}):
            Path(tmp, "a.txt").write_text("one\ntwo\nthree", encoding="utf-8")
            output = dispatch("read_file", json.dumps({"path": "a.txt", "start_line": 2, "end_line": 3}), DummyHarness())
            self.assertIn("2 | two", output)
            self.assertNotIn("one", output)

    def test_subprocess_environment_drops_api_keys(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"WORKSPACE": tmp, "OPENAI_API_KEY": "sk-should-not-leak", "COMMAND_POLICY": "allow"}):
            output = dispatch("run_python", json.dumps({"code": "import os\nprint(os.getenv('OPENAI_API_KEY', 'missing'))"}), DummyHarness())
            self.assertIn("missing", output)
            self.assertNotIn("sk-should-not-leak", output)

    def test_python_timeout_is_structured(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"WORKSPACE": tmp}):
            output = dispatch("run_python", json.dumps({"code": "import time\ntime.sleep(2)", "timeout": 1}), DummyHarness())
            self.assertIn("exit_code=124", output)
            self.assertIn("TIMEOUT after 1s", output)

    def test_stale_evidence_cannot_finish_after_new_mutation(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"WORKSPACE": tmp}):
            h = DummyHarness()
            dispatch("write_file", json.dumps({"path": "a.py", "content": "x = 1"}), h)
            h.state.record_evidence("test", "passed at epoch one")
            dispatch("edit_file", json.dumps({"path": "a.py", "old": "1", "new": "2"}), h)
            self.assertEqual(h.state.mutation_epoch, 2)
            self.assertEqual(h.state.fresh_evidence(), [])
            with self.assertRaisesRegex(ValueError, "current mutation epoch 2"):
                dispatch("finish", json.dumps({"summary": "done"}), h)

    def test_task_invariant(self):
        items = [
            {"id": "1", "content": "a", "status": "in_progress"},
            {"id": "2", "content": "b", "status": "in_progress"},
        ]
        with self.assertRaisesRegex(ValueError, "at most one"):
            dispatch("update_tasks", json.dumps({"items": items}), DummyHarness())

    def test_redacts_keys_but_not_hashes(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-secret-secret-secret"}):
            self.assertEqual(redact("key=sk-secret-secret-secret"), "key=[REDACTED]")
        digest = "1234567890abcdef1234567890abcdef"
        self.assertEqual(redact(digest), digest)


if __name__ == "__main__":
    unittest.main()
