"""Container-side supervisor for a budgeted competitor CLI invocation."""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream-base", required=True)
    parser.add_argument("--gateway-state", type=Path, required=True)
    parser.add_argument("--stream-log", type=Path, required=True)
    parser.add_argument("--timing", type=Path, required=True)
    parser.add_argument("--output-cap", type=int, required=True)
    parser.add_argument("--wall-seconds", type=float, required=True)
    parser.add_argument(
        "--proxy-script",
        type=Path,
        default=Path(__file__).resolve().with_name("generation_budget_proxy.py"),
    )
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        raise SystemExit("missing child command")
    for path in (args.gateway_state, args.stream_log, args.timing):
        path.parent.mkdir(parents=True, exist_ok=True)
    proxy_command = [
        sys.executable,
        str(args.proxy_script),
        "--host",
        "127.0.0.1",
        "--port",
        "8787",
        "--upstream-base",
        args.upstream_base,
        "--state",
        str(args.gateway_state),
        "--cap",
        str(args.output_cap),
    ]
    proxy_log = args.stream_log.with_name("generation_budget_proxy.log")
    started = time.time()
    timed_out = False
    child_returncode = None
    with proxy_log.open("wb") as proxy_stream:
        proxy = subprocess.Popen(proxy_command, stdout=proxy_stream, stderr=subprocess.STDOUT)
        try:
            time.sleep(0.2)
            if proxy.poll() is not None:
                raise RuntimeError("generation budget proxy exited during startup")
            env = dict(os.environ)
            env["OPENAI_BASE_URL"] = "http://127.0.0.1:8787"
            env["ANTHROPIC_BASE_URL"] = "http://127.0.0.1:8787"
            with args.stream_log.open("wb") as stream:
                child = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT, env=env)
                try:
                    child_returncode = child.wait(timeout=args.wall_seconds)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    if os.name == "nt":
                        child.terminate()
                    else:
                        child.send_signal(signal.SIGTERM)
                    try:
                        child_returncode = child.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child_returncode = child.wait()
        finally:
            proxy.terminate()
            try:
                proxy.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proxy.kill()
                proxy.wait()
    ended = time.time()
    timing = {
        "schema": "budgeted-cli-timing-v1",
        "started_at": started,
        "ended_at": ended,
        "wall_seconds": ended - started,
        "max_agent_wall_seconds": args.wall_seconds,
        "timed_out": timed_out,
        "child_returncode": child_returncode,
        "proxy_returncode": proxy.returncode,
    }
    args.timing.write_text(json.dumps(timing, indent=2) + "\n", encoding="utf-8")
    raise SystemExit(124 if timed_out else int(child_returncode or 0))


if __name__ == "__main__":
    main()
