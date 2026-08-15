from pathlib import Path
from tempfile import TemporaryDirectory

from agent.execution_contract import compile_execution_contract
from agent.goal_runtime import Goal, GoalStore, goal_from_contract
from agent.harness import Harness


def test_goal_roundtrip_and_milestone_progress():
    with TemporaryDirectory() as tmp:
        store = GoalStore(Path(tmp))
        goal = goal_from_contract("修复并验证项目", compile_execution_contract(None, False))
        goal.complete(goal.milestones[0])
        store.save(goal)
        restored = store.load()
        assert restored is not None
        assert restored.objective == "修复并验证项目"
        assert restored.completed_milestones == [goal.milestones[0]]


def test_corrupt_goal_file_fails_closed_without_breaking_session():
    with TemporaryDirectory() as tmp:
        store = GoalStore(Path(tmp))
        store.path.parent.mkdir(parents=True)
        store.path.write_text("not json", encoding="utf-8")
        assert store.load() is None


def test_bare_continue_resumes_active_goal_but_new_task_does_not():
    harness = Harness.__new__(Harness)
    harness.active_goal = Goal(objective="修复项目并运行测试", milestones=["修改", "验证"])
    assert harness._effective_goal_task("继续") == ("修复项目并运行测试", True)
    assert harness._effective_goal_task("继续修改第 4 页") == ("继续修改第 4 页", False)
    assert harness._effective_goal_task("解释当前代码") == ("解释当前代码", False)
