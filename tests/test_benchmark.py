import unittest
from unittest.mock import patch
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import sys

from agent.benchmark import is_provider_unavailable


class BenchmarkDiagnosticsTests(unittest.TestCase):
    def test_connection_failures_are_infrastructure_diagnostics(self):
        self.assertTrue(is_provider_unavailable("APIConnectionError: Connection error."))
        self.assertTrue(is_provider_unavailable("request timed out"))

    def test_regular_agent_errors_are_not_reclassified(self):
        self.assertFalse(is_provider_unavailable("SchemaValidationError: invalid tool"))

    def test_bundle_path_cannot_escape_workspace(self):
        from agent import benchmark

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            argv = [
                "xiaopu-bench", "--workspace", str(root),
                "--bundle", "../escape", "task",
            ]

            class FakeLLM:
                model = "fake"

            class FakeHarness:
                def __init__(self, *args, **kwargs):
                    from agent.state import RunState
                    self.state = RunState(final_summary="done")
                    self.llm = FakeLLM()
                    self.policy_guard = type("P", (), {"manifest": lambda self: {}})()
                    self.recorder = None
                def attach_printer(self, printer): pass
                def run(self, task): return "done"

            with patch.object(sys, "argv", argv), patch("agent.harness.Harness", FakeHarness):
                self.assertEqual(benchmark.main(), 2)


if __name__ == "__main__":
    unittest.main()
