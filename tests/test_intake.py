from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json

from agent.intake import bind_manifest_task, prepare_task_brief, task_root_from_prompt
from agent.state import RunState


def test_preflight_builds_office_brief_without_contract_or_output():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        task = root / "tasks" / "demo"
        (task / "input").mkdir(parents=True)
        (task / "output").mkdir()
        (task / "instruction.md").write_text("Create output/final.pptx", encoding="utf-8")
        (task / "TRAJECTORY_CAPTURE_CONTRACT.md").write_text("long logging contract", encoding="utf-8")
        (task / "input" / "facts.md").write_text("# Actual\n42%", encoding="utf-8")
        (task / "output" / "old.md").write_text("ignore", encoding="utf-8")
        state = RunState()

        with patch("agent.intake.config.sandbox_root", return_value=root):
            assert task_root_from_prompt("完成 tasks/demo 的 PPT") == task
            brief = prepare_task_brief("完成 tasks/demo 的 PPT", state)

        assert "Create output/final.pptx" in brief
        assert "42%" in brief
        assert "long logging contract" not in brief
        assert "ignore" not in brief
        assert len(state.source_paths) == 2
        assert (root / ".xiaopu" / "content_ir").is_dir()
        assert state.facts["required_output_pptx"] == "tasks/demo/output/final.pptx"


def test_bare_task_directory_name_resolves_without_tasks_prefix():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        task = root / "tasks" / "4._Pre-Colonial_Filipino_Culture-001"
        task.mkdir(parents=True)
        with patch("agent.intake.config.sandbox_root", return_value=root):
            assert task_root_from_prompt("4._Pre-Colonial_Filipino_Culture-001完成这个任务") == task


def test_preflight_discovers_task_local_official_evaluator():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        task = root / "tasks" / "demo"
        evaluator = task / "tests" / "grading" / "test_verify.py"
        evaluator.parent.mkdir(parents=True)
        (task / "instruction.md").write_text("Create output/final.pptx", encoding="utf-8")
        evaluator.write_text("def test_ok(): assert True", encoding="utf-8")
        state = RunState()
        with patch("agent.intake.config.sandbox_root", return_value=root):
            brief = prepare_task_brief("tasks/demo", state)
        assert "official_evaluator" in brief
        assert state.facts["official_evaluator_present"] == "true"


def test_preflight_is_idempotent_for_same_task():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        task = root / "tasks" / "demo"
        task.mkdir(parents=True)
        (task / "instruction.md").write_text("Create PPT", encoding="utf-8")
        state = RunState()
        with patch("agent.intake.config.sandbox_root", return_value=root):
            first = prepare_task_brief("tasks/demo", state)
            before = state.progress_epoch
            second = prepare_task_brief("tasks/demo", state)
        assert first == second
        assert state.progress_epoch == before


def test_preflight_binds_one_exact_pptx_instead_of_guessing_its_name():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        task = root / "tasks" / "3-002"
        task.mkdir(parents=True)
        (task / "instruction.md").write_text("Change the title", encoding="utf-8")
        (task / "3.pptx").write_bytes(b"opaque deck name")
        state = RunState()
        with patch("agent.intake.config.sandbox_root", return_value=root), patch(
            "agent.intake.build_content_ir"
        ) as build_ir, patch("agent.intake.persist_content_ir") as persist_ir:
            build_ir.return_value = type("IR", (), {
                "sources": [],
                "to_model_dict": lambda self, max_total_chars=12000: {"schema": "test"},
            })()
            artifact = root / ".xiaopu" / "content_ir" / "test.json"
            artifact.parent.mkdir(parents=True)
            artifact.write_text("{}", encoding="utf-8")
            persist_ir.return_value = artifact
            brief = prepare_task_brief("tasks/3-002", state)
        assert state.facts["ppt_input_deck"] == str(Path("tasks/3-002/3.pptx"))
        assert state.facts["required_output_pptx"] == "tasks/3-002/output/final.pptx"
        assert json.loads(brief)["input_pptx"] == str(Path("tasks/3-002/3.pptx"))


def test_preflight_does_not_guess_between_multiple_pptx_inputs():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        task = root / "tasks" / "demo"
        task.mkdir(parents=True)
        (task / "a.pptx").write_bytes(b"a")
        (task / "b.pptx").write_bytes(b"b")
        state = RunState()
        with patch("agent.intake.config.sandbox_root", return_value=root), patch(
            "agent.intake.build_content_ir"
        ) as build_ir, patch("agent.intake.persist_content_ir") as persist_ir:
            build_ir.return_value = type("IR", (), {
                "sources": [],
                "to_model_dict": lambda self, max_total_chars=12000: {"schema": "test"},
            })()
            artifact = root / ".xiaopu" / "content_ir" / "test.json"
            artifact.parent.mkdir(parents=True)
            artifact.write_text("{}", encoding="utf-8")
            persist_ir.return_value = artifact
            prepare_task_brief("tasks/demo", state)
        assert "ppt_input_deck" not in state.facts
        assert json.loads(state.facts["ppt_input_candidates"]) == [
            str(Path("tasks/demo/a.pptx")), str(Path("tasks/demo/b.pptx"))
        ]


def test_task_root_handles_windows_path_followed_by_unspaced_or_mojibake_prose():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        task = root / "tasks" / "html-report-quadrant-ppt"
        task.mkdir(parents=True)
        with patch("agent.intake.config.sandbox_root", return_value=root):
            assert task_root_from_prompt(
                r"完成 tasks\html-report-quadrant-ppt，严格按照 instruction.md"
            ) == task
            assert task_root_from_prompt(
                r"完成 tasks\html-report-quadrant-ppt锛屼弗鏍兼寜鐓 instruction.md"
            ) == task


def test_manifest_placeholder_binds_first_unfinished_task_deterministically():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "tasks" / "3-002").mkdir(parents=True)
        (root / "tasks" / "3-003").mkdir(parents=True)
        (root / "workspace_manifest.csv").write_text(
            '"task_id","task_dir","status"\n'
            '"3-002","tasks/3-002","prepared"\n'
            '"3-003","tasks/3-003","prepared"\n',
            encoding="utf-8",
        )
        bound, task_id = bind_manifest_task(
            r"read workspace_manifest.csv then complete tasks\<task_id>", root
        )
        assert task_id == "3-002"
        assert "tasks/3-002" in bound


def test_bound_instruction_is_preserved_as_a_routing_fact():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        task = root / "tasks" / "3-002"
        task.mkdir(parents=True)
        instruction = "Change Lecture 3 to Lecture 1 in the presentation title."
        (task / "instruction.md").write_text(instruction, encoding="utf-8")
        state = RunState()
        with patch("agent.intake.config.sandbox_root", return_value=root):
            prepare_task_brief("tasks/3-002", state)
        assert state.facts["task_instruction"] == instruction
