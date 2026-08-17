"""Baoyi — provider-neutral coding + PowerPoint agent harness

Usage:
  baoyi                    interactive UI in the current directory
  baoyi --workspace PATH   use an explicit local project/task directory
  baoyi "task..."          single-shot task (requires provider credential)
  baoyi --json "task..."   single-shot task with machine-readable JSON output
  baoyi --model M          override model id
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
        "then restart Baoyi. Run `baoyi-doctor` to validate the environment."
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
        "Baoyi did not attempt generic automatic recovery; inspect the "
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
    list_sessions = "--list-sessions" in args
    yes_approve = "--yes" in args
    resume_id: str | None = None
    export_spec: str | None = None
    log_path: str | None = None
    plan_arg: str | None = None
    positional = []
    i = 0
    args = [a for a in args if a not in {"--json", "--list-sessions", "--yes"}]
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
        elif a == "--resume":
            resume_id = args[i + 1]
            i += 2
        elif a.startswith("--resume="):
            resume_id = a.split("=", 1)[1]
            i += 1
        elif a == "--export":
            export_spec = args[i + 1]
            i += 2
        elif a.startswith("--export="):
            export_spec = a.split("=", 1)[1]
            i += 1
        elif a == "--log":
            log_path = args[i + 1]
            i += 2
        elif a.startswith("--log="):
            log_path = a.split("=", 1)[1]
            i += 1
        elif a == "--plan":
            plan_arg = "on" if i + 1 >= len(args) or args[i + 1].startswith("-") else args[i + 1]
            if plan_arg in {"on", "off"}:
                i += 2
            else:
                i += 1
        elif a.startswith("--plan="):
            plan_arg = a.split("=", 1)[1]
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

    if list_sessions:
        from .session_store import list_sessions
        for index, record in enumerate(list_sessions(), 1):
            print(f"{index}\t{record.id[:12]}\t{record.title}\t{record.model}\t{record.updated_at}")
        return 0

    if export_spec:
        from .session_store import export_session
        parts = export_spec.split(maxsplit=1)
        session_id = parts[0]
        target = Path(parts[1]) if len(parts) > 1 else Path.cwd() / f"baoyi-session-{session_id}.md"
        try:
            print(export_session(session_id, target))
            return 0
        except Exception as exc:
            print(f"EXPORT ERROR ({type(exc).__name__}): {exc}", file=sys.stderr)
            return 1

    if plan_arg:
        config.set_plan_mode(plan_arg == "on")
    if config.plan_mode() and task and resume_id is None:
        task = f"计划模式：先只给出执行计划与预期修改，不要调用任何修改工具。\n{task}"

    if task or resume_id:
        # single-shot mode
        try:
            from .harness import Harness
        except Exception as e:
            print(f"[import error] {e}")
            return 1

        h = Harness(model=model)
        if yes_approve:
            h.approval_handler = lambda command: "allow"  # noqa: E731 -- explicit --yes
        if log_path:
            log_file = Path(log_path).expanduser().resolve()
            log_file.parent.mkdir(parents=True, exist_ok=True)

            def _tee_printer(name: str, args: str, out: str) -> None:
                _print_tool(name, args, out)
                with log_file.open("a", encoding="utf-8") as stream:
                    stream.write(f"\n> {name}({args})\n{out}\n")
            h.attach_printer(_tee_printer)
        else:
            h.attach_printer(_print_tool)
        if resume_id:
            from .session_store import load_session, restore_harness
            payload = load_session(resume_id)
            if payload is None:
                print(f"SESSION ERROR: unknown session id: {resume_id}", file=sys.stderr)
                return 2
            if payload.get("workspace"):
                os.environ["WORKSPACE"] = payload["workspace"]
            print(restore_harness(h, payload))
            if not task:
                return 0
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
        # Every single-shot run is a resumable checkpoint. A paused/STUCK run
        # keeps its working deck path in the snapshot, so `--resume <id>` can
        # continue from the last blocker instead of restarting from input.
        session_note = ""
        try:
            from .session_store import save_session
            record = save_session(h, title=task)
            session_note = f"\nSESSION_ID={record.id}"
        except Exception as exc:
            session_note = f"\nSESSION_SAVE_WARNING={type(exc).__name__}: {exc}"
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
            print(reply + session_note)
        if log_path:
            with log_file.open("a", encoding="utf-8") as stream:
                stream.write(f"\n===== RESULT ({elapsed}s) =====\n{reply}\n")
        return 0

    # interactive terminal REPL
    from .cli import run_cli

    return run_cli(model=model)


if __name__ == "__main__":
    _force_utf8_stdio()
    sys.exit(main())
