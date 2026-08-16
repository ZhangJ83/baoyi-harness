"""Modern interactive CLI for Xiaopu.

Design choices (based on current agent-CLI practice):
- Rich renders structured status, tools, plans and Markdown replies;
- prompt_toolkit owns the input line, history, completions and key bindings;
- the model runs on a worker thread so Esc / Ctrl+C can interrupt cleanly.

The old full-screen TUI was removed on purpose: this REPL stays scrollable,
selectable and simple, which suits long agent trajectories better.
"""
from __future__ import annotations

import json
import os
import queue
import sys
import threading
import time
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion, PathCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from . import config
from .events import EventKind, RuntimeEvent
from .harness import Harness
from .redact import redact
from .tools.registry import dispatch
from .wordmark import wordmark

console = Console()

COMMANDS: dict[str, str] = {
    "/new": "保存并新建会话，清空当前演示文稿",
    "/sessions": "列出已保存会话",
    "/resume": "恢复已保存会话（id 或序号）",
    "/export": "导出当前会话记录到 markdown 文件",
    "/info": "查看当前演示文稿结构",
    "/status": "查看循环状态：相位、证据纪元、修复预算、用量",
    "/context": "查看 token 用量与上下文预算",
    "/compact": "立即压缩对话历史",
    "/undo": "撤销最近一次 PPT 修改",
    "/verify": "执行演示文稿结构校验",
    "/save": "保存演示文稿（可附目标路径）",
    "/doctor": "检查模型、凭据和本地依赖",
    "/model": "查看或切换当前模型",
    "/thinking": "查看或切换思考模式（on/off）",
    "/effort": "查看或设置推理强度（high/max）",
    "/permissions": "查看或设置 shell 策略（allow/ask/deny）",
    "/plan": "切换计划模式（on/off）",
    "/process": "设置过程显示（quiet/balanced/detail）",
    "/trajectory": "导出本轮完整轨迹：规划/决策/工具/原始思维链",
    "/cot": "显示最近一次模型实际返回的原始思维链",
    "/goal": "启动或查看可恢复的长期目标",
    "/theme": "切换主题（dark/light）",
    "/help": "查看全部命令说明",
    "/exit": "保存会话并退出小朴",
    "/quit": "保存会话并退出小朴",
}

HELP_TEXT = """\
[b]任务[/]       直接输入任务描述，例如：把第 2 页标题改成绿色
[b]命令[/]       以 / 开头，输入 /help 查看全部命令

[cyan]/new[/]     保存并新建会话        [cyan]/sessions[/]  列出已保存会话
[cyan]/resume[/]  恢复会话              [cyan]/export[/]    导出当前会话
[cyan]/status[/]  循环状态              [cyan]/context[/]   上下文用量
[cyan]/verify[/]  结构校验              [cyan]/save[/]      保存演示文稿
[cyan]/model[/]   查看/切换模型         [cyan]/theme[/]     深色/浅色主题
[cyan]/process[/] 过程显示 quiet/balanced/detail
[cyan]/trajectory[/] 本轮完整轨迹（规划/工具/思维链）
[cyan]/cot[/] 查看模型实际返回的原始思维链
[cyan]/doctor[/]  环境诊断（密钥永不显示）
[cyan]/goal[/]    启动/查看长期目标
[cyan]/exit[/]    保存会话并退出
"""


class CommandCompleter(Completer):
    """Slash-command menu with a Chinese description beside every command."""

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if not text.startswith("/") or " " in text:
            return
        for command, description in COMMANDS.items():
            if command.startswith(text):
                yield Completion(
                    command, start_position=-len(text),
                    display=command, display_meta=description,
                )


class HybridCompleter(Completer):
    """Slash commands after '/', filesystem paths everywhere else."""

    def __init__(self) -> None:
        self.commands = CommandCompleter()
        self.paths = PathCompleter(
            only_directories=False,
            expanduser=True,
            get_paths=lambda: [os.getcwd()],
        )

    def get_completions(self, document, complete_event):
        if document.text_before_cursor.startswith("/"):
            yield from self.commands.get_completions(document, complete_event)
            return
        yield from self.paths.get_completions(document, complete_event)


class XiaopuCLI:
    """Scrollable, selectable agent REPL."""

    def __init__(self, model: str | None = None) -> None:
        config.load_dotenv()
        self.h = Harness(model=model, interactive=True)
        self.has_key = bool(config.provider_api_key())
        self.h.attach_printer(self._on_tool)
        self.h.approval_handler = self._approve_command
        self.h.stream_callback = self._on_token
        self.h.reasoning_callback = self._on_reasoning
        subscribe = getattr(self.h, "subscribe", None)
        if callable(subscribe):
            subscribe(self._on_event)
        self._approval_queue: queue.Queue = queue.Queue()
        self._streamed_text = ""
        self._reasoning_text = ""
        self._latest_activity: list[str] = []
        self._trajectory: list[tuple[str, str]] = []
        self._last_tool_error: str | None = None
        self._process_view = "detail"
        self._stream_counts = {"decisions": 0, "tools": 0, "verifications": 0}
        self._theme = config.theme()
        self._is_tty = sys.stdin.isatty() and sys.stdout.isatty()
        self._prompt = self._make_prompt() if self._is_tty else None
        self._interrupted = False

    # ------------------------------------------------------------------ UI
    def _theme_prompt(self) -> str:
        light = self._theme == "light"
        return (
            "bg:#f4f4f5 #1f2937 bold"
            if light
            else "bg:#0f172a #67e8f9 bold"
        )

    def _make_prompt(self) -> PromptSession:
        bindings = KeyBindings()

        @bindings.add("enter")
        def _submit(event) -> None:
            event.current_buffer.validate_and_handle()

        @bindings.add("escape", "enter")
        @bindings.add("c-j")
        def _newline(event) -> None:
            event.current_buffer.insert_text("\n")

        @bindings.add("/")
        def _slash_menu(event) -> None:
            event.current_buffer.insert_text("/")
            event.current_buffer.start_completion(select_first=False)

        @bindings.add("c-l")
        def _clear(event) -> None:
            event.app.renderer.clear()

        @bindings.add("c-c")
        def _cancel(event) -> None:
            if self.h is not None and getattr(self.h, "cancel_requested", None):
                self.h.request_cancel()
            event.app.renderer.clear()

        session = PromptSession(
            completer=HybridCompleter(),
            complete_while_typing=True,
            multiline=True,
            history=FileHistory(str(Path(config.sandbox_root()) / ".xiaopu" / "cli_history.txt")),
            key_bindings=bindings,
            prompt_continuation=lambda width, line_number, is_soft_wrap: Text("  · ", style="dim"),
        )
        session.message = lambda: [
            ("class:prompt", " 小朴 › "),
        ]
        return session

    def print_banner(self) -> None:
        console.print()
        left = Text()
        left.append("Xiaopu\n", style="bold cyan")
        left.append("Provider-neutral coding & PowerPoint agent\n", style="dim")
        left.append_text(wordmark())
        right = Table.grid(padding=(0, 1))
        right.add_column(style="bold", width=14)
        right.add_column(style="white")
        right.add_row("Model", self.h.llm.model)
        right.add_row("Provider", config.provider())
        right.add_row("Workspace", str(config.sandbox_root()))
        right.add_row(
            "Credential",
            "[green]Ready[/]" if self.has_key else "[yellow]Missing[/]",
        )
        right.add_row("Theme", self._theme)
        grid = Table.grid(expand=True, padding=(0, 3))
        grid.add_column(ratio=3)
        grid.add_column(ratio=2)
        grid.add_row(left, right)
        console.print(Panel(grid, title="小朴 · Xiaopu v0.2.0", subtitle="/help 查看命令 · Esc 中止 · Ctrl+L 清屏", border_style="cyan"))
        console.print()

    def _on_token(self, piece: str) -> None:
        self._streamed_text += piece

    def _on_reasoning(self, piece: str) -> None:
        """Provider-returned reasoning stream; never synthesized."""
        self._reasoning_text += piece
        self._trajectory.append(("reasoning", piece))
        if self._process_view == "detail":
            console.print(piece, end="", style="magenta", soft_wrap=True)

    def _on_tool(self, name: str, args: str, out: str) -> None:
        try:
            parsed = json.loads(args)
            pretty_args = json.dumps(parsed, ensure_ascii=False)
        except Exception:
            parsed = {}
            pretty_args = args
        pretty_args = redact(pretty_args[:140] + ("…" if len(pretty_args) > 140 else ""))
        failed = (out or "").lstrip().startswith(("TOOL ERROR", "PERMISSION ASK", "CANCELLED"))
        error_key = f"{name}:{(out or '').strip()}" if failed else None
        if error_key and error_key == self._last_tool_error:
            return
        self._last_tool_error = error_key
        label = name
        summary = redact((out or "").strip().splitlines()[0][:160] if (out or "").strip() else "完成")
        icon = "[red]✕[/]" if failed else "[green]✓[/]"
        body = Text()
        body.append(f"{icon} ", style="bold")
        body.append(label, style="bold cyan")
        if pretty_args:
            body.append(f"  {pretty_args}", style="dim")
        self._latest_activity.append(f"{label} · {pretty_args} · {summary}")
        self._trajectory.append(("tool", f"{label}\nargs={pretty_args}\nresult={redact((out or '').strip())[:1200]}"))
        if self._process_view == "quiet":
            return
        console.print(body)
        if failed or self._process_view == "detail":
            for line in redact(out or "").splitlines()[:6]:
                console.print(f"    [dim]{line[:180]}[/]")
        console.print()

    def _approve_command(self, command: str) -> str:
        decided = threading.Event()
        holder: dict = {"decision": "deny"}
        self._approval_queue.put((command, decided, holder))
        decided.wait(timeout=120)
        return holder["decision"]

    def _drain_approvals(self) -> None:
        while True:
            try:
                command, decided, holder = self._approval_queue.get_nowait()
            except queue.Empty:
                return
            console.print(Panel(
                f"[bold yellow]Shell 命令需要授权[/]\n[dim]{redact(command)}[/]",
                title="权限确认", border_style="yellow", padding=(0, 1),
            ))
            try:
                answer = console.input("[yellow]允许执行？[y/N] [/]").strip().casefold()
            except (EOFError, KeyboardInterrupt):
                answer = "n"
            holder["decision"] = "allow" if answer in {"y", "yes", "是"} else "deny"
            decided.set()

    def _on_event(self, event: RuntimeEvent) -> None:
        kind = event.kind
        payload = event.payload
        if kind == EventKind.TURN_STARTED:
            self._stream_counts = {"decisions": 0, "tools": 0, "verifications": 0}
            self._streamed_text = ""
            self._reasoning_text = ""
            self._trajectory = []
            return
        if kind == EventKind.TASK_PROFILED and self._process_view != "quiet":
            console.print(Panel(
                f"[bold]Capabilities[/]  {', '.join(payload.get('capabilities', []))}\n"
                f"[bold]Verification[/]  {', '.join(payload.get('verification', []))}\n"
                f"[bold]Design policy[/]  {payload.get('design_policy', '')}",
                title=f"Task profile / {payload.get('label', payload.get('profile', 'unknown'))}",
                border_style="cyan", padding=(0, 1),
            ))
            return
        if kind in {EventKind.TASK_PLAN, EventKind.PROGRESS_UPDATED}:
            items = list(payload.get("items", []))
            marks = {"completed": "✓", "in_progress": "→", "pending": "·", "blocked": "!"}
            body = "\n".join(
                f"[{marks.get(str(item.get('status')), '·')}] {item.get('content', '')}"
                for item in items
            ) or "尚无计划"
            self._latest_activity.append("计划与进度：\n" + body)
            if self._process_view != "quiet":
                console.print(Panel(body, title="执行计划", border_style="bright_black", padding=(0, 1)))
            return
        if kind == EventKind.PLANNING_DECISION:
            self._trajectory.append(("planning", f"next={payload.get('next_action')} reason={payload.get('reason')}"))
            if self._process_view == "detail":
                console.print(
                    f"[cyan]规划[/] {payload.get('next_action', '')} "
                    f"[dim]· {payload.get('reason', '')}[/]"
                )
            return
        if kind == EventKind.GOAL_UPDATED and self._process_view != "quiet":
            console.print(
                f"[bold]Goal[/] {payload.get('status', 'active')} · "
                f"{len(payload.get('completed', []))}/{len(payload.get('milestones', []))} · "
                f"{payload.get('goal', '')}"
            )
            return
        if kind == EventKind.CONTROLLER_DECISION:
            self._stream_counts["decisions"] += 1
            self._trajectory.append(("decision", f"action={payload.get('action')} phase={payload.get('phase')} reason={payload.get('reason')}"))
            if self._process_view == "detail":
                console.print(
                    f"[magenta]Decision[/] {payload.get('action', 'continue')}  "
                    f"[dim]{payload.get('reason', '')[:180]}[/]"
                )
            return
        if kind == EventKind.PHASE_CHANGED:
            self._trajectory.append(("phase", f"{payload.get('from_phase')} -> {payload.get('to_phase')}"))
            if self._process_view == "detail":
                console.print(
                    f"[cyan]Phase[/] {payload.get('from_phase', '?')} -> "
                    f"[bold]{payload.get('to_phase', '?')}[/]"
                )
            return
        if kind == EventKind.MODEL_RESPONSE:
            count = payload.get("tool_call_count", 0)
            reasoning = str(payload.get("reasoning_content") or self._reasoning_text or "")
            if reasoning.strip():
                self._trajectory.append(("reasoning_full", reasoning))
                if self._process_view != "quiet":
                    console.print(Panel(
                        Text(reasoning, style="magenta"),
                        title="原始思维链（模型实际返回，未做任何加工）",
                        border_style="magenta", padding=(0, 1),
                    ))
            elif self._process_view != "quiet":
                console.print("[dim]本次模型响应没有返回可显示的原始思维链（provider 未提供）。[/]")
            if self._process_view == "detail":
                console.print(
                    f"[dim]Model turn[/] · {count} tool call(s) · "
                    f"auditable reasoning signal {payload.get('reasoning_chars', 0)} chars"
                )
            return
        if kind == EventKind.TOOL_STARTED:
            self._stream_counts["tools"] += 1
            return
        if kind == EventKind.TOOL_COMPLETED:
            name = str(payload.get("tool", ""))
            if name in {"ppt_check", "ppt_verify", "ppt_quality_check", "render_deck", "inspect_rendered_deck", "run_task_evaluator"}:
                self._stream_counts["verifications"] += 1
            return
        if kind == EventKind.TOOL_FAILED and self._process_view != "quiet":
            console.print(f"[red]Tool failure[/] {payload.get('tool', '?')}: {str(payload.get('error', ''))[:180]}")
            return
        if kind == EventKind.TURN_COMPLETED and self._process_view != "quiet":
            body = (
                f"[bold]Stop[/] {payload.get('stop_reason', '?')}   "
                f"[bold]Phase[/] {payload.get('phase', '?')}\n"
                f"[bold]Events[/] decisions={self._stream_counts['decisions']} · "
                f"tools={self._stream_counts['tools']} · verifications={self._stream_counts['verifications']}\n"
                f"[bold]Artifact[/] {redact(str(payload.get('artifact') or 'none'))}"
            )
            console.print(Panel(body, title="Run summary", border_style="green", padding=(0, 1)))

    # -------------------------------------------------------------- runtime
    def _run_interruptibly(self, task: str) -> str:
        results: queue.Queue[tuple[str, object]] = queue.Queue(maxsize=1)

        def worker() -> None:
            try:
                results.put(("ok", self.h.run(task)))
            except BaseException as exc:
                results.put(("error", exc))

        thread = threading.Thread(target=worker, name="xiaopu-agent-run", daemon=True)
        thread.start()
        announced = False
        while thread.is_alive():
            try:
                self._drain_approvals()
                if os.name == "nt":
                    import msvcrt
                    while msvcrt.kbhit():
                        key = msvcrt.getwch()
                        if key in {"\x1b", "\x03"}:
                            self.h.request_cancel()
                            if not announced:
                                console.print("\n[yellow]⏹ 已收到中止请求，正在停止当前步骤…[/]")
                                announced = True
                        elif key in {"\x00", "\xe0"} and msvcrt.kbhit():
                            msvcrt.getwch()
                thread.join(0.05)
            except KeyboardInterrupt:
                self.h.request_cancel()
                if not announced:
                    console.print("\n[yellow]⏹ 已收到中止请求，正在停止当前步骤…[/]")
                    announced = True
        self._drain_approvals()
        kind, value = results.get()
        if kind == "error":
            raise value
        return str(value)

    def _execute(self, task: str) -> None:
        if not self.has_key:
            console.print("[bold red]CONFIGURATION ERROR:[/] 未配置模型凭据。任务未发送。\n")
            return
        self._latest_activity = [f"目标：{task}"]
        self._last_tool_error = None
        started = time.monotonic()
        try:
            with console.status("[cyan]agent loop[/] · decision / tool / verification", spinner="dots"):
                reply = self._run_interruptibly(task)
            elapsed = max(0, round(time.monotonic() - started))
            console.print()
            if self._streamed_text and reply.strip() == self._streamed_text.strip():
                console.print(self._streamed_text)
            elif reply.startswith(("⚠", "⏹")):
                console.print(Panel(Markdown(reply), title="小朴 · 可恢复暂停", border_style="yellow"))
            else:
                console.print(Markdown(reply))
            state = self.h.state
            signal = f"推理信号 {state.last_reasoning_chars} 字符" if state.last_reasoning_chars else "无推理信号"
            console.print(f"[dim]✓ 完成于 {elapsed} 秒 · {signal}[/]\n")
        except Exception as exc:
            console.print(f"[bold red]RUNTIME ERROR[/] ({type(exc).__name__}): {exc}\n")

    # -------------------------------------------------------------- commands
    def _handle_command(self, cmd: str, parts: list[str]) -> bool:
        """Return True when the REPL should exit."""
        if cmd == "/help":
            console.print(Panel(HELP_TEXT, title="小朴 · 命令", border_style="cyan", padding=(0, 1)))
            return False
        if cmd in {"/exit", "/quit"}:
            try:
                from .session_store import save_session
                record = save_session(self.h, title="interactive session")
                console.print(f"[dim]会话已保存：{record.id}[/]")
            except Exception:
                pass
            console.print("[bold cyan]再见。[/]\n")
            return True
        if cmd == "/new":
            try:
                from .session_store import save_session
                record = save_session(self.h, title="interactive session")
                console.print(f"[dim]会话已保存：{record.id}[/]")
            except Exception:
                pass
            self.h.reset()
            console.print("[bold cyan]已新建会话。[/]\n")
            return False
        if cmd == "/sessions":
            from .session_store import list_sessions
            table = Table(title="已保存会话", border_style="bright_black")
            table.add_column("#", style="dim", width=3)
            table.add_column("id", style="cyan", width=14)
            table.add_column("title", style="white")
            table.add_column("model", style="dim", width=20)
            table.add_column("updated", style="dim", width=22)
            for index, record in enumerate(list_sessions(), 1):
                table.add_row(str(index), record.id[:12], record.title[:60], record.model, record.updated_at)
            console.print(table)
            console.print()
            return False
        if cmd == "/resume":
            from .session_store import load_session, restore_harness
            target = parts[1].strip() if len(parts) > 1 else ""
            if not target:
                console.print("[yellow]用法：/resume <id 或序号>[/]\n")
                return False
            from .session_store import list_sessions
            records = list_sessions()
            record = None
            if target.isdigit() and 1 <= int(target) <= len(records):
                record = records[int(target) - 1]
            else:
                record = next((r for r in records if r.id.startswith(target)), None)
            if record is None:
                console.print("[yellow]未找到会话。[/]\n")
                return False
            payload = load_session(record.id)
            if payload is None:
                console.print("[yellow]会话读取失败。[/]\n")
                return False
            if payload.get("workspace"):
                os.environ["WORKSPACE"] = payload["workspace"]
            console.print(restore_harness(self.h, payload))
            for message in payload.get("messages", []):
                role = message.get("role")
                content = str(message.get("content", "")).strip()
                if role == "user" and content:
                    console.print(Panel(content, title="你", border_style="cyan", padding=(0, 1)))
                elif role == "assistant" and content:
                    console.print(Markdown(content))
            console.print()
            return False
        if cmd == "/export":
            from .session_store import export_session, save_session
            record = save_session(self.h, title="interactive session")
            target = Path(parts[1]) if len(parts) > 1 else Path.cwd() / "xiaopu-session.md"
            console.print(export_session(record.id, target))
            console.print()
            return False
        if cmd == "/info":
            console.print(f"[dim]{dispatch('deck_info', '{}', self.h)}[/]\n")
            return False
        if cmd == "/status":
            state = self.h.state
            table = Table(show_header=False, border_style="bright_black", expand=True)
            table.add_column("项", style="bold", width=20)
            table.add_column("值", style="white")
            for key, value in (
                ("Phase", state.phase.value),
                ("Mutation epoch", str(state.mutation_epoch)),
                ("Fresh evidence", str(len(state.fresh_evidence()))),
                ("Unresolved checks", ", ".join(sorted(state.unresolved_checks)) or "—"),
                ("Repair budget", f"{state.repair_attempts}/{state.max_repairs}"),
                ("Tokens", f"{state.total_tokens} total · {state.generated_output_tokens} generated"),
            ):
                table.add_row(key, value)
            console.print(Panel(table, title="小朴 · 状态", border_style="bright_black"))
            console.print()
            return False
        if cmd == "/context":
            state = self.h.state
            console.print(f"[dim]tokens={state.total_tokens} · input={state.input_tokens} · output={state.generated_output_tokens} · reasoning={state.reasoning_chars} chars[/]\n")
            return False
        if cmd == "/compact":
            self.h._maybe_compact(force=True)
            console.print("[dim]上下文已压缩。[/]\n")
            return False
        if cmd == "/undo":
            console.print(f"[dim]{self.h.undo()}[/]\n")
            return False
        if cmd == "/verify":
            console.print(f"[dim]{dispatch('ppt_check', '{}', self.h)}[/]\n")
            return False
        if cmd == "/save":
            path = parts[1].strip() if len(parts) > 1 else None
            result = dispatch("ppt_save", json.dumps({"path": path}) if path else "{}", self.h)
            console.print(f"[bold cyan]Saved:[/] {result}\n")
            return False
        if cmd == "/doctor":
            from .doctor import report
            payload = report()
            table = Table(show_header=False, border_style="bright_black", expand=True)
            table.add_column("项", style="bold", width=24)
            table.add_column("值", style="white")
            for key, value in payload.items():
                table.add_row(str(key), str(value))
            console.print(Panel(table, title="小朴 · Doctor（密钥永不显示）", border_style="bright_black"))
            console.print()
            return False
        if cmd == "/model":
            value = parts[1].strip() if len(parts) > 1 else None
            if value:
                try:
                    self.h.llm.model = value
                    console.print(f"[dim]模型已切换：{value}[/]\n")
                except Exception as exc:
                    console.print(f"[yellow]切换失败：{exc}[/]\n")
            else:
                console.print(f"[dim]当前模型：{self.h.llm.model} · 可用：{', '.join(config.known_models())}[/]\n")
            return False
        if cmd == "/thinking":
            value = (parts[1].strip() if len(parts) > 1 else None) or ("off" if config.thinking_enabled() else "on")
            config.set_thinking(value == "on")
            console.print(f"[dim]思考模式：{value}[/]\n")
            return False
        if cmd == "/effort":
            value = parts[1].strip() if len(parts) > 1 else None
            if value:
                config.set_reasoning_effort(value)
            console.print(f"[dim]推理强度：{config.reasoning_effort()}[/]\n")
            return False
        if cmd == "/permissions":
            value = parts[1].strip() if len(parts) > 1 else None
            if value and value not in {"allow", "ask", "deny"}:
                console.print("[yellow]用法：/permissions allow|ask|deny[/]\n")
                return False
            if value:
                config.set_command_policy(value)
            console.print(f"[dim]shell 策略：{config.command_policy()}[/]\n")
            return False
        if cmd == "/plan":
            value = parts[1].strip() if len(parts) > 1 else None
            enabled = value == "on" if value in {"on", "off"} else not config.plan_mode()
            config.set_plan_mode(enabled)
            console.print(f"[dim]计划模式：{'on' if enabled else 'off'}[/]\n")
            return False
        if cmd == "/process":
            value = (parts[1].strip() if len(parts) > 1 else None) or "balanced"
            if value not in {"quiet", "balanced", "detail"}:
                console.print("[yellow]用法：/process quiet|balanced|detail[/]\n")
                return False
            self._process_view = value
            console.print(f"[dim]过程显示：{value}[/]\n")
            return False
        if cmd == "/trajectory":
            if not self._trajectory:
                console.print("[dim]本轮暂无轨迹（先执行一个任务）。[/]\n")
                return False
            table = Table(title="本轮详细轨迹", border_style="bright_black", expand=True)
            table.add_column("#", style="dim", width=4)
            table.add_column("阶段", style="bold cyan", width=12)
            table.add_column("内容", style="white")
            for index, (kind, content) in enumerate(self._trajectory, 1):
                table.add_row(str(index), kind, content[:4000])
            console.print(table)
            console.print()
            return False
        if cmd == "/cot":
            text = self.h.state.last_reasoning_text or self._reasoning_text
            if not text.strip():
                console.print("[dim]模型最近一次响应没有返回原始思维链（provider 未提供）。[/]\n")
                return False
            console.print(Panel(Text(text, style="magenta"), title="原始思维链（模型实际返回）", border_style="magenta", padding=(0, 1)))
            return False
        if cmd == "/goal":
            objective = parts[1].strip() if len(parts) > 1 else ""
            console.print(self.h.start_goal(objective) if objective else self.h.goal_summary())
            console.print()
            return False
        if cmd == "/theme":
            value = (parts[1].strip() if len(parts) > 1 else None) or ("light" if self._theme == "dark" else "dark")
            if value not in {"dark", "light"}:
                console.print("[yellow]用法：/theme dark|light[/]\n")
                return False
            config.set_theme(value)
            self._theme = value
            self._prompt = self._make_prompt()
            console.print(f"[dim]主题已切换：{value}[/]\n")
            return False
        if cmd == "/activity":
            if not self._latest_activity:
                console.print("[dim]暂无工作摘要。[/]\n")
            else:
                console.print(Panel("\n\n".join(self._latest_activity), title="小朴 · 工作摘要（可审计）", border_style="cyan"))
            return False
        console.print(f"[yellow]未知命令：{cmd}（输入 /help 查看）[/]\n")
        return False

    def run_interactive(self) -> int:
        self.print_banner()
        while True:
            try:
                if self._is_tty and self._prompt is not None:
                    user_input = self._prompt.prompt().strip()
                else:
                    user_input = console.input("[cyan]小朴 › [/]").strip()
            except (EOFError, KeyboardInterrupt):
                console.print("\n[bold cyan]再见。[/]\n")
                return 0
            if not user_input:
                continue
            if user_input.startswith("/"):
                parts = user_input.split()
                if self._handle_command(parts[0], parts):
                    return 0
                continue
            self._execute(user_input)
        return 0


def run_cli(model: str | None = None) -> int:
    return XiaopuCLI(model=model).run_interactive()
