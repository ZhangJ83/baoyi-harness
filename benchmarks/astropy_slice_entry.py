"""Container entry point for one Astropy test slice."""
from __future__ import annotations
import json, os, subprocess, sys, time
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
out = Path(sys.argv[2] if len(sys.argv) > 2 else "/work/result.json")
expected = sys.argv[3] if len(sys.argv) > 3 else ""
version = root / "astropy" / "version.py"
version.write_text('version = "5.0.4"\ngithash = "unknown"\nversion_info = (5, 0, 4)\n', encoding="utf-8")
build_cmd = [sys.executable, "setup.py", "build_ext", "--inplace"] if os.environ.get("ASTROPY_OFFICIAL_BUILD") else [sys.executable, "/opt/xiaopu/astropy_minimal_build.py"]
build = subprocess.run(build_cmd, cwd=root, text=True, capture_output=True)
start = time.monotonic()
test = subprocess.run([sys.executable, "-m", "pytest", "-q", "astropy/modeling/tests/test_separable.py", "--disable-warnings", "--maxfail=1"], cwd=root, text=True, capture_output=True)
row = {"expected_commit": expected, "build_exit_code": build.returncode, "build_stdout": build.stdout[-12000:], "build_stderr": build.stderr[-12000:], "test_exit_code": test.returncode, "elapsed_seconds": round(time.monotonic()-start, 3), "stdout": test.stdout, "stderr": test.stderr, "score_eligible": False}
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(row, ensure_ascii=False, indent=2))
raise SystemExit(test.returncode if build.returncode == 0 else build.returncode)
