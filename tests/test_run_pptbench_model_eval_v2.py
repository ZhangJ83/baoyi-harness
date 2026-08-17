import json
import subprocess
import sys
from pathlib import Path

from benchmarks.run_pptbench_model_eval_v2 import build_prompt, command_for


ROOT = Path(__file__).resolve().parents[1]


def protocol():
    return json.loads((ROOT / "benchmarks/pptbench_model_eval_v2.json").read_text(encoding="utf-8-sig"))


def test_prompt_exposes_the_full_artifact_contract_without_identity():
    task = protocol()["tasks"][0]
    prompt = build_prompt(task, has_input=False)
    assert "deck.pptx" in prompt
    assert "[Sources]" in prompt
    assert "50 pt" in prompt and "35 pt" in prompt and "16 pt" in prompt
    assert all(value in prompt for value in task["required_text"])
    assert "Xiaopu" not in prompt and "Claude" not in prompt and "Codex" not in prompt


def test_xiaopu_command_carries_frozen_hard_caps(tmp_path):
    command, extra_env = command_for("xiaopu", tmp_path, protocol(), "prompt")
    assert extra_env == {}
    assert command[command.index("--max-tool-calls") + 1] == "60"
    assert command[command.index("--max-generated-output-tokens") + 1] == "4500"
    assert command[command.index("--model") + 1] == "deepseek-v4-flash"


def test_full_dry_run_freezes_36_unique_cells_without_credential(tmp_path):
    run_root = tmp_path / "run"
    result = subprocess.run(
        [sys.executable, "-m", "benchmarks.run_pptbench_model_eval_v2",
         "--run-root", str(run_root), "--dry-run"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    manifest = json.loads((run_root / "run_manifest.json").read_text(encoding="utf-8"))
    cells = {(row["system"], row["task_id"]) for row in manifest["cells"]}
    assert len(manifest["cells"]) == len(cells) == 36
    assert not (run_root / "raw").exists()
