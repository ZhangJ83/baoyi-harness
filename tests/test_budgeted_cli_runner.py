import json
import subprocess
import sys
from pathlib import Path


def test_runner_enforces_wall_timeout_and_writes_timing(tmp_path):
    timing = tmp_path / "timing.json"
    command = [
        sys.executable,
        "-m",
        "agent.budgeted_cli_runner",
        "--upstream-base",
        "http://127.0.0.1:9",
        "--gateway-state",
        str(tmp_path / "gateway.json"),
        "--stream-log",
        str(tmp_path / "stream.log"),
        "--timing",
        str(timing),
        "--output-cap",
        "10",
        "--wall-seconds",
        "0.1",
        "--",
        sys.executable,
        "-c",
        "import time; time.sleep(2)",
    ]
    result = subprocess.run(command, cwd=Path(__file__).resolve().parents[1], timeout=10)
    assert result.returncode == 124
    payload = json.loads(timing.read_text(encoding="utf-8"))
    assert payload["timed_out"] is True
    assert payload["wall_seconds"] < 2
