"""ppt_agent — coding + PowerPoint agent harness
Usage:
  xiaopu                    interactive UI in the current directory
  xiaopu --workspace PATH   use an explicit local project/task directory
  xiaopu "task..."          single-shot task (requires provider credential)
  xiaopu --json "task..."   single-shot task with machine-readable JSON output
  agent --model M           override model id
"""

import json
import os
import sys
import time
from pathlib import Path

from . import config
from .redact import redact


def _force_utf8_stdio() -> None:
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _print_tool(name: str, args: str, out: str) -> None:
    try:
        args_pretty = json.dumps(json.loads(args), ensure_ascii=False)[:160]
    except Exception:
        args_pretty = args[:160]
    args_pretty = redact(args_pretty)
    print(f"  > {name}({args_pretty})")
    for line in (out or "").splitlines()[:12]:
        print(f"    {redact(line)}")


def _print_help() -> None:
    print(__doc__)


def _missing_credential_error() -> str:
    return (
        "CONFIGURATION ERROR: no provider credential is configured. "
        f"Set {config.provider_credential_name()} for PROVIDER={config.provider()!r}, "
        "then restart Xiaopu. Run `xiaopu-doctor` to validate the environment."
    )


def _print_incomplete_transaction_notice(workspace: Path) -> None:
    """Report prior crash candidates without attempting domain recovery."""

    from .transaction_journal import list_incomplete_transactions

    pending = list_incomplete_transactions(workspace)
    if not pending:
        return
    preview = ", ".join(
        f"{entry.transaction_id} ({entry.status})" for entry in pending[:5]
    )
    extra = f" and {len(pending) - 5} more" if len(pending) > 5 else ""
    print(
        "RECOVERY NOTICE: found "
        f"{len(pending)} incomplete transaction(s): {preview}{extra}. "
        "Xiaopu did not attempt generic automatic recovery; inspect the "
        f"domain checkpoint and journal under {pending[0].journal_path.parent}.",
        file=sys.stderr,
    )


def main() -> int:
    _force_utf8_stdio()
    config.load_dotenv()
    args = [a for a in sys.argv[1:] if not a.startswith("--fly--")]

    if any(a in ("-h", "--help") for a in args):
        _print_help()
        return 0

    model = None
    workspace = None
    json_out = "--json" in args
    positional = []
    i = 0
    args = [a for a in args if a != "--json"]
    while i < len(args):
        a = args[i]
        if a == "--model":
            model = args[i + 1]
            i += 2
        elif a.startswith("--model="):
            model = a.split("=", 1)[1]
            i += 1
        elif a == "--workspace":
            workspace = args[i + 1]
            i += 2
        elif a.startswith("--workspace="):
            workspace = a.split("=", 1)[1]
            i += 1
        else:
            positional.append(a)
            i += 1

    task = " ".join(positional).strip()
    # Match project-oriented CLIs: the directory from which Xiaopu is started
    # is the workspace unless the caller explicitly selects another one.
    selected_workspace = Path(workspace).expanduser().resolve() if workspace else Path.cwd().resolve()
    if not selected_workspace.is_dir():
        print(f"WORKSPACE ERROR: directory does not exist: {selected_workspace}", file=sys.stderr)
        return 2
    os.environ["WORKSPACE"] = str(selected_workspace)
    _print_incomplete_transaction_notice(selected_workspace)

    if task:
        # single-shot mode
        try:
            from .harness import Harness
        except Exception as e:
            print(f"[import error] {e}")
            return 1

        h = Harness(model=model)
        h.attach_printer(_print_tool)
        if not config.provider_api_key():
            print(_missing_credential_error(), file=sys.stderr)
            return 2
        started = time.monotonic()
        try:
            reply = h.run(task)
            elapsed = round(time.monotonic() - started, 2)
        except Exception as e:
            if json_out:
                print(json.dumps({"status": "runtime_error", "error_type": type(e).__name__,
                                  "error": str(e), "task": task}, ensure_ascii=False))
            else:
                print(f"RUNTIME ERROR ({type(e).__name__}): {e}", file=sys.stderr)
            return 1
        if json_out:
            print(json.dumps({
                "status": "completed",
                "task": task,
                "workspace": str(selected_workspace),
                "model": h.llm.model if getattr(h, "llm", None) else (model or ""),
                "elapsed_seconds": elapsed,
                "reply": reply,
            }, ensure_ascii=False))
        else:
            print(reply)
        return 0

    # interactive terminal UI
    from .tui import run_tui

    return run_tui(model=model)


if __name__ == "__main__":
    _force_utf8_stdio()
    sys.exit(main())
