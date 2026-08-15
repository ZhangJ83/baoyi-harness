import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent.harness import Harness
from agent.llm import AssistantMessage, LLMReply, ToolCall, ToolFn
from agent.state import RunState
from agent.hooks import ToolEvent


class SequenceLLM:
    model = "fake"

    def __init__(self, replies):
        self.replies = iter(replies)

    def chat(self, messages, tools=None):
        return next(self.replies)


class BudgetCaptureLLM:
    model = "fake"

    def __init__(self, reply):
        self.reply = reply
        self.seen = []

    def chat(self, messages, tools=None):
        self.seen.append(os.environ.get("OPENAI_MAX_TOKENS"))
        return self.reply


class ExecutionModeCaptureLLM:
    model = "fake"

    def __init__(self):
        self.seen = []

    def chat(self, messages, tools=None):
        self.seen.append((os.environ.get("OPENAI_MAX_TOKENS"), os.environ.get("THINKING_ENABLED")))
        if len(self.seen) <= 2:
            return LLMReply.from_message(
                AssistantMessage(content="", reasoning_content="deliberation"),
                total_tokens=200, input_tokens=100, output_tokens=100,
            )
        raise RuntimeError("stop after scheduler observation")


class HarnessTests(unittest.TestCase):
    def make_harness(self, replies):
        harness = Harness.__new__(Harness)
        harness.llm = SequenceLLM(replies)
        harness.max_steps = 5
        harness.messages = []
        harness.deck = None
        harness.on_tool = lambda *args: None
        harness.started = True
        harness.state = RunState()
        harness._done = None
        harness.pre_tool_hooks = []
        harness.post_tool_hooks = []
        harness.loaded_skills = set()
        return harness

    def test_finish_stops_loop_and_tracks_usage(self):
        call = ToolCall("1", ToolFn("finish", json.dumps({"summary": "done"})))
        reply = LLMReply.from_message(AssistantMessage(tool_calls=[call]), total_tokens=17)
        harness = self.make_harness([reply])
        self.assertEqual(harness.run("answer only"), "done")
        self.assertEqual(harness.state.total_tokens, 17)

    def test_workspace_task_question_returns_actual_itemized_directories(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"WORKSPACE": tmp}):
            Path(tmp, "tasks", "Task-B").mkdir(parents=True)
            Path(tmp, "tasks", "Task-A").mkdir(parents=True)
            answer = Harness._workspace_task_listing("当前工作区下有多少个任务")
        self.assertEqual(answer, "当前工作区共有 2 个任务：\n1. Task-A\n2. Task-B")

    def test_non_inventory_task_does_not_trigger_deterministic_listing(self):
        self.assertIsNone(Harness._workspace_task_listing("完成这个任务"))

    def test_progress_question_returns_state_without_waking_model_or_tools(self):
        harness = self.make_harness([])
        harness.state.phase = __import__("agent.state", fromlist=["RuntimePhase"]).RuntimePhase.VERIFY
        harness.state.tool_calls = 12
        harness.state.operational_plan = [
            {"id": "verify", "content": "增量验证并交付", "status": "in_progress"}
        ]
        result = harness.run("对话告诉我现在进展到哪里了")
        self.assertIn("阶段：verify", result)
        self.assertIn("进行中：增量验证并交付", result)
        self.assertEqual(harness.state.tool_calls, 12)

    def test_ppt_plan_progresses_after_mutate_save_and_check(self):
        harness = self.make_harness([])
        harness.deck = object()
        harness._ensure_ppt_plan()
        harness._advance_ppt_plan("ppt_edit_text")
        harness._advance_ppt_plan("ppt_save")
        harness.state.record_evidence("ppt_structural", "passed")
        harness._advance_ppt_plan("ppt_check")
        self.assertTrue(all(item["status"] == "completed" for item in harness.state.operational_plan))

    def test_atomic_skill_coalesces_parallel_inspects_to_targeted_shapes(self):
        harness = self.make_harness([])
        harness.state.record_fact("selected_skill", "ppt.atomic_edit")
        calls = [
            ToolCall("summary", ToolFn("ppt_inspect", json.dumps({"detail": "summary"}))),
            ToolCall("target", ToolFn("ppt_inspect", json.dumps({"slide_number": 2, "detail": "shapes"}))),
            ToolCall("other", ToolFn("ppt_inspect", json.dumps({"slide_number": 2, "detail": "summary"}))),
        ]
        reduced = harness._coalesce_atomic_inspect_batch(calls)
        self.assertEqual([call.id for call in reduced], ["target"])

    def test_task_spec_narrows_atomic_edit_operation_schema(self):
        harness = self.make_harness([])
        harness.task_spec = type("Spec", (), {"operation": "append_bullet"})()
        tools = [{"type": "function", "function": {
            "name": "ppt_edit_text",
            "parameters": {"properties": {"operation": {"type": "string", "enum": ["replace", "append_bullet"]}}},
        }}]
        narrowed = harness._constrain_compiled_tool_schemas(tools)
        self.assertEqual(
            narrowed[0]["function"]["parameters"]["properties"]["operation"]["enum"],
            ["append_bullet"],
        )
        self.assertEqual(tools[0]["function"]["parameters"]["properties"]["operation"]["enum"], ["replace", "append_bullet"])

    def test_unadvertised_registered_tool_is_rejected_before_dispatch(self):
        call = ToolCall("1", ToolFn("run_shell", json.dumps({"command": "echo must-not-run"})))
        again = ToolCall("2", ToolFn("run_shell", json.dumps({"command": "echo still-must-not-run"})))
        harness = self.make_harness([
            LLMReply.from_message(AssistantMessage(tool_calls=[call])),
            LLMReply.from_message(AssistantMessage(tool_calls=[again])),
        ])
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"WORKSPACE": tmp}, clear=False):
            result = harness.run("完成 tasks/missing 的 PPT")
        self.assertIn("未开放的工具", result)
        self.assertEqual(harness.state.tool_calls, 0)
        self.assertTrue(any("Nothing was executed" in str(message.get("content")) for message in harness.messages))

    def test_changed_files_require_evidence(self):
        inspect = ToolCall("1", ToolFn("read_file", json.dumps({"path": "x.py"})))
        finish = ToolCall("2", ToolFn("finish", json.dumps({"summary": "done"})))
        verify = ToolCall("3", ToolFn("verify_files", json.dumps({"paths": ["x.py"]})))
        final = LLMReply.from_message(AssistantMessage(content="verified now"))
        harness = self.make_harness([LLMReply.from_message(AssistantMessage(tool_calls=[inspect])), LLMReply.from_message(AssistantMessage(tool_calls=[finish])), LLMReply.from_message(AssistantMessage(tool_calls=[verify])), final])
        harness.state.record_change("x.py")
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"WORKSPACE": tmp}):
            Path(tmp, "x.py").write_text("x = 1", encoding="utf-8")
            self.assertEqual(harness.run("fix"), "verified now")
            self.assertEqual(harness.state.final_summary, "verified now")

    def test_compaction_keeps_latest_tool_pair_with_user_anchor(self):
        harness = self.make_harness([])
        harness.messages = [
            {"role": "system", "content": "rules"},
            {"role": "user", "content": "x" * 50000},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "7", "type": "function", "function": {"name": "read_file", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "7", "content": "latest"},
        ]
        harness._maybe_compact()
        self.assertEqual([message["role"] for message in harness.messages], ["system", "system", "user", "assistant", "tool"])
        self.assertEqual(harness.messages[-1]["tool_call_id"], "7")

    def test_end_to_end_repository_repair(self):
        def tool(call_id, name, arguments):
            return LLMReply.from_message(AssistantMessage(tool_calls=[ToolCall(call_id, ToolFn(name, json.dumps(arguments)))]), total_tokens=10)

        replies = [
            tool("1", "read_file", {"path": "calculator.py"}),
            tool("2", "edit_file", {"path": "calculator.py", "old": "return a - b", "new": "return a + b"}),
            tool("3", "verify_files", {"paths": ["calculator.py"], "contains": {"calculator.py": ["return a + b"]}}),
            tool("4", "finish", {"summary": "Fixed calculator.add and verified add(2, 3) == 5."}),
        ]
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"WORKSPACE": tmp}):
            path = os.path.join(tmp, "calculator.py")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("def add(a, b):\n    return a - b\n")
            harness = self.make_harness(replies)
            harness.started = False
            harness.max_steps = 10
            answer = harness.run("Fix calculator.add and verify it")
            self.assertIn("verified", answer.lower())
            with open(path, encoding="utf-8") as handle:
                self.assertIn("return a + b", handle.read())
            self.assertEqual(harness.state.tool_calls, 4)
            self.assertEqual(harness.state.total_tokens, 40)

    def test_hooks_can_rewrite_input_and_output(self):
        call = ToolCall("1", ToolFn("finish", json.dumps({"summary": "before"})))
        harness = self.make_harness([LLMReply.from_message(AssistantMessage(tool_calls=[call]))])
        harness.add_pre_tool_hook(lambda event: json.dumps({"summary": "after"}) if event.name == "finish" else event.arguments)
        seen = []
        harness.add_post_tool_hook(lambda event: (seen.append(event), event.output)[1])
        self.assertEqual(harness.run("answer"), "after")
        self.assertEqual(seen[0].name, "finish")

    def test_later_turn_can_load_powerpoint_skill(self):
        first = LLMReply.from_message(AssistantMessage(content="code answer"))
        second = LLMReply.from_message(AssistantMessage(tool_calls=[ToolCall("ppt-finish", ToolFn("finish", json.dumps({"summary": "ppt answer"})))]))
        harness = self.make_harness([first, second])
        self.assertEqual(harness.run("explain this Python function"), "code answer")
        self.assertNotIn("powerpoint", harness.loaded_skills)
        harness.deck = type("Deck", (), {"slides": []})()
        harness.state.record_change("deck:slide:1:shape:1:text")
        harness.state.record_evidence("ppt_structural", "passed")
        harness.state.record_evidence("ppt_render", "passed")
        harness.state.record_evidence("ppt_visual", "passed")
        harness.recorder = type("Recorder", (), {
            "completed": False,
            "event": lambda *a, **k: None,
            "manifest": {"artifacts": [{"role": "final-pptx", "path": "output/final.pptx"}]},
        })()
        self.assertEqual(harness.run("render this PPT slide deck"), "ppt answer")
        self.assertIn("powerpoint", harness.loaded_skills)
        self.assertTrue(any(message["role"] == "system" and "Dynamically loaded" in message["content"] for message in harness.messages))

    def test_repeated_identical_action_has_circuit_breaker(self):
        def repeat(call_id):
            return LLMReply.from_message(
                AssistantMessage(tool_calls=[ToolCall(call_id, ToolFn("search_text", json.dumps({"query": "missing"})))]),
                total_tokens=5,
            )
        harness = self.make_harness([repeat("1"), repeat("2"), repeat("3"), repeat("4")])
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"WORKSPACE": tmp}):
            result = harness.run("find the missing symbol")
        self.assertIn("连续三次执行相同操作", result)
        self.assertEqual(harness.state.total_tokens, 15)

    def test_output_cap_uses_remaining_budget_and_restores_environment(self):
        harness = self.make_harness([LLMReply.from_message(AssistantMessage(content="done"), total_tokens=100)])
        capture = BudgetCaptureLLM(LLMReply.from_message(AssistantMessage(content="done"), total_tokens=100))
        harness.llm = capture
        with patch.dict(os.environ, {"STRICT_RUN_BUDGET": "1", "MAX_TOTAL_TOKENS": "500", "OPENAI_MAX_TOKENS": "700"}, clear=False):
            self.assertEqual(harness.run("answer"), "done")
            self.assertEqual(os.environ["OPENAI_MAX_TOKENS"], "700")
        self.assertEqual(capture.seen, ["500"])

    def test_generated_output_cap_is_separate_and_blocks_overrun_tools(self):
        finish = ToolCall("1", ToolFn("finish", json.dumps({"summary": "must not execute"})))
        reply = LLMReply.from_message(
            AssistantMessage(tool_calls=[finish]), total_tokens=700,
            input_tokens=100, output_tokens=600,
        )
        harness = self.make_harness([reply])
        with patch.dict(os.environ, {"STRICT_RUN_BUDGET": "1", "MAX_TOTAL_TOKENS": "2000", "MAX_GENERATED_OUTPUT_TOKENS": "500"}, clear=False):
            result = harness.run("answer")
        self.assertIn("超过了本轮预算", result)
        self.assertIsNone(harness._done)
        self.assertEqual(harness.state.input_tokens, 100)
        self.assertEqual(harness.state.generated_output_tokens, 600)

    def test_new_user_turn_gets_independent_generated_output_budget(self):
        capture = BudgetCaptureLLM(LLMReply.from_message(
            AssistantMessage(content="done"), total_tokens=100, input_tokens=50, output_tokens=50,
        ))
        harness = self.make_harness([])
        harness.llm = capture
        harness.state.generated_output_tokens = 200
        with patch.dict(os.environ, {"STRICT_RUN_BUDGET": "1", "MAX_TOTAL_TOKENS": "2000", "MAX_GENERATED_OUTPUT_TOKENS": "500", "OPENAI_MAX_TOKENS": "1000"}, clear=False):
            self.assertEqual(harness.run("answer"), "done")
        self.assertEqual(capture.seen, ["500"])

    def test_interactive_mode_does_not_stop_on_cumulative_generation_budget(self):
        capture = BudgetCaptureLLM(LLMReply.from_message(
            AssistantMessage(content="done"), total_tokens=700, input_tokens=100, output_tokens=600,
        ))
        harness = self.make_harness([])
        harness.llm = capture
        with patch.dict(os.environ, {"STRICT_RUN_BUDGET": "0", "MAX_GENERATED_OUTPUT_TOKENS": "500", "OPENAI_MAX_TOKENS": "4096"}, clear=False):
            self.assertEqual(harness.run("answer"), "done")
        self.assertFalse(harness.state.budget_overrun)

    def test_ppt_action_deadline_caps_first_pass_then_disables_thinking_for_retry(self):
        capture = ExecutionModeCaptureLLM()
        harness = self.make_harness([])
        harness.llm = capture
        harness.state.phase = __import__("agent.state", fromlist=["RuntimePhase"]).RuntimePhase.PRODUCE
        harness.state.content_brief = "authoritative brief"
        with patch.dict(os.environ, {
            "STRICT_RUN_BUDGET": "1", "MAX_TOTAL_TOKENS": "10000",
            "MAX_GENERATED_OUTPUT_TOKENS": "5000", "OPENAI_MAX_TOKENS": "4096",
            "FIRST_ACTION_OUTPUT_TOKENS": "1200", "THINKING_ENABLED": "1",
        }, clear=False):
            with self.assertRaisesRegex(RuntimeError, "scheduler observation"):
                harness.run("create and save a PPT")
            self.assertEqual(os.environ["THINKING_ENABLED"], "1")
        self.assertEqual(capture.seen[0], ("1200", "1"))
        self.assertEqual(capture.seen[1], ("1200", "0"))

    def test_reasoning_signal_is_audited_without_rendering_content(self):
        reply = LLMReply.from_message(
            AssistantMessage(content="done", reasoning_content="private reasoning"),
            total_tokens=20, input_tokens=10, output_tokens=10,
        )
        harness = self.make_harness([reply])
        self.assertEqual(harness.run("answer"), "done")
        self.assertTrue(harness.state.reasoning_observed)
        self.assertEqual(harness.state.last_reasoning_chars, len("private reasoning"))
        self.assertNotIn("private reasoning", harness.state.final_summary)

    def test_missing_provider_usage_fails_authoritative_ledger(self):
        harness = self.make_harness([LLMReply.from_message(AssistantMessage(content="done"))])
        self.assertEqual(harness.run("answer"), "done")
        self.assertFalse(harness.state.provider_usage_authoritative)

    def test_action_task_echo_is_retried_instead_of_marked_complete(self):
        echo = LLMReply.from_message(AssistantMessage(content="请修改 PPT 并保存"), total_tokens=10)
        finish = ToolCall("1", ToolFn("finish", json.dumps({"summary": "done"})))
        harness = self.make_harness([echo, LLMReply.from_message(AssistantMessage(tool_calls=[finish]), total_tokens=10)])
        with patch.dict(os.environ, {"STRICT_RUN_BUDGET": "0"}, clear=False):
            result = harness.run("修改 PPT 并保存")
        self.assertIn("运行错误", result)
        self.assertEqual(harness.state.total_tokens, 20)
        self.assertTrue(any("not complete" in str(message.get("content")) for message in harness.messages))
        self.assertTrue(any("cannot finish" in str(message.get("content")) for message in harness.messages))

    def test_action_task_repeated_no_tool_response_is_not_completion(self):
        replies = [LLMReply.from_message(AssistantMessage(content="任务：修改并保存 PPT")) for _ in range(3)]
        harness = self.make_harness(replies)
        result = harness.run("修改并保存 PPT")
        self.assertIn("没有调用工具", result)
        self.assertIsNone(harness.state.final_summary)

    def test_ppt_action_cannot_end_after_inspection_only(self):
        inspect = ToolCall("1", ToolFn("shape_inventory", json.dumps({"slide_number": 2})))
        harness = self.make_harness([
            LLMReply.from_message(AssistantMessage(tool_calls=[inspect])),
            LLMReply.from_message(AssistantMessage(content="done")),
            LLMReply.from_message(AssistantMessage(content="done")),
            LLMReply.from_message(AssistantMessage(content="done")),
        ])
        harness.deck = type("Deck", (), {"slides": [object(), object()]})()
        result = harness.run("修改 PPTX 第2页并保存")
        self.assertIn("任务尚未开始", result)
        self.assertIsNone(harness.state.final_summary)

    def test_ppt_action_can_end_with_final_artifact_and_fresh_structure(self):
        harness = self.make_harness([LLMReply.from_message(AssistantMessage(content="completed"))])
        harness.deck = object()
        harness.state.record_change("deck:slide:2:shape:3:text")
        harness.state.record_evidence("ppt_structural", "passed")
        harness.recorder = type("Recorder", (), {
            "completed": False,
            "manifest": {"artifacts": [{"role": "final-pptx", "path": "output/final.pptx"}]},
        })()
        self.assertEqual(harness.run("修改 PPTX 第2页并保存"), "completed")

    def test_interactive_mode_has_no_visible_step_boundary(self):
        harness = self.make_harness([
            LLMReply.from_message(AssistantMessage(tool_calls=[ToolCall("1", ToolFn("search_text", json.dumps({"query": "x"})))])),
            LLMReply.from_message(AssistantMessage(content="done")),
        ])
        harness.max_steps = 1
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"WORKSPACE": tmp, "STRICT_RUN_BUDGET": "0"}, clear=False):
            self.assertEqual(harness.run("find x"), "done")
        assert any("checkpoint reached" in str(message.get("content")) for message in harness.messages)

    def test_tool_budget_stops_once_without_emitting_tool_errors(self):
        first = ToolCall("1", ToolFn("search_text", json.dumps({"query": "x"})))
        rejected = ToolCall("2", ToolFn("finish", json.dumps({"summary": "must not run"})))
        harness = self.make_harness([
            LLMReply.from_message(AssistantMessage(tool_calls=[first])),
            LLMReply.from_message(AssistantMessage(tool_calls=[rejected])),
        ])
        observed = []
        harness.on_tool = lambda name, args, out: observed.append((name, out))
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"WORKSPACE": tmp, "MAX_TOOL_CALLS": "1", "STRICT_RUN_BUDGET": "1"},
            clear=False,
        ):
            result = harness.run("find x")
        self.assertIn("工具调用额度已用完", result)
        self.assertNotIn("BudgetExceeded", result)
        self.assertEqual([name for name, _ in observed], ["search_text"])
        self.assertFalse(any("TOOL ERROR" in output for _, output in observed))
        self.assertEqual(harness.state.tool_calls, 1)

    def test_interactive_mode_ignores_benchmark_tool_cap(self):
        first = ToolCall("1", ToolFn("search_text", json.dumps({"query": "x"})))
        finish = ToolCall("2", ToolFn("finish", json.dumps({"summary": "done"})))
        harness = self.make_harness([
            LLMReply.from_message(AssistantMessage(tool_calls=[first])),
            LLMReply.from_message(AssistantMessage(tool_calls=[finish])),
        ])
        harness.interactive = True
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"WORKSPACE": tmp, "MAX_TOOL_CALLS": "1", "STRICT_RUN_BUDGET": "1"},
            clear=False,
        ):
            result = harness.run("find x")
        self.assertEqual(result, "done")
        self.assertEqual(harness.state.tool_calls, 2)

    def test_cancel_after_provider_reply_rejects_all_tool_calls(self):
        call = ToolCall("1", ToolFn("finish", json.dumps({"summary": "must not run"})))
        harness = self.make_harness([])

        class CancellingLLM:
            model = "fake"

            def chat(self, messages, tools=None):
                harness.request_cancel()
                return LLMReply.from_message(AssistantMessage(tool_calls=[call]))

        harness.llm = CancellingLLM()
        result = harness.run("answer")
        self.assertIn("已按用户要求中止", result)
        self.assertEqual(harness.state.tool_calls, 0)
        self.assertIsNone(harness._done)

    def test_cancel_closes_provider_request_and_maps_exception_to_interrupt(self):
        harness = self.make_harness([])

        class ClosingLLM:
            model = "fake"
            closed = False

            def cancel_current(self):
                self.closed = True

            def chat(self, messages, tools=None):
                harness.request_cancel()
                raise ConnectionError("request closed")

        harness.llm = ClosingLLM()
        result = harness.run("answer")
        self.assertTrue(harness.llm.closed)
        self.assertIn("已按用户要求中止", result)
        self.assertNotIn("request closed", result)


if __name__ == "__main__":
    unittest.main()
