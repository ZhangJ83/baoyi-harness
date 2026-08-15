from pathlib import Path
from tempfile import TemporaryDirectory

from agent.code_task_compiler import compile_code_task


def test_python_repo_and_target_compile_to_pytest_contract():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "tests").mkdir()
        (root / "app.py").write_text("x = 1", encoding="utf-8")
        spec = compile_code_task("Fix app.py and run tests", root)
        assert spec.language == "python"
        assert spec.runner == "pytest"
        assert spec.target_paths == ("app.py",)


def test_typescript_repo_is_detected_without_inventing_runner():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "tsconfig.json").write_text("{}", encoding="utf-8")
        spec = compile_code_task("Fix src/main.ts", root)
        assert spec.language == "typescript"
        assert spec.runner == ""

