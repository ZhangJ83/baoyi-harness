"""小朴 terminal UI, inspired by modern agent CLIs."""
from __future__ import annotations

import json
import os
import queue
import shutil
import threading
import time
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.table import Table
from rich.text import Text
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion, PathCompleter, WordCompleter
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.filters import to_filter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.styles import Style

from . import config
from .harness import Harness
from .events import EventKind, RuntimeEvent
from .redact import redact
from .tools.registry import dispatch
from .wordmark import wordmark

console = Console()


def _price(name: str) -> float:
    try:
        return max(0.0, float(os.getenv(name, "0") or "0"))
    except ValueError:
        return 0.0

XIAOPU_HELP = """\
小朴 commands:

  <task>           run the agent on a task
  /new             save current session, then reset memory and deck
  /sessions        list saved sessions
  /resume [id]     resume a saved session (id or list index)
  /export [path]   export current session transcript to a markdown file
  /info            show slide deck structure
  /status          show current loop state (phase / epoch / evidence / budget)
  /context         show token usage and context-window budget
  /compact         compact the conversation history now
  /undo            undo the most recent PPT modification
  /theme [name]    switch theme: dark/light/dracula
  /keys [name]     switch keymap: default/minimal
  /verify          run structural verifier
  /save [path]     save deck to file (default workspace/deck.pptx)
  /doctor          show provider and dependency readiness (secrets are never shown)
  /model [name]    show or switch the active model
  /thinking        show or switch thinking mode: on/off
  /effort          show or set reasoning effort: high/max
  /permissions     show or set shell policy: allow/ask/deny
  /plan            toggle plan mode: on/off (plan first, do not mutate)
  /activity        show / hide the latest auditable work summary
  /process         set process display: hidden/balanced/summary/detail
  /goal [task]     start or inspect a recoverable long-horizon goal
  /mouse           switch mouse input mode: on/off (off keeps output selectable)
  /help            show this help message
  /exit, /quit     save session and exit
"""

COMMANDS = {
    "/new": "保存并新建会话，清空当前演示文稿",
    "/sessions": "列出已保存会话",
    "/resume": "恢复已保存会话（id 或序号）",
    "/export": "导出当前会话记录到 markdown 文件",
    "/info": "查看当前演示文稿结构",
    "/status": "查看循环状态：相位、证据纪元、修复预算、用量",
    "/context": "查看 token 用量与上下文预算",
    "/compact": "立即压缩对话历史",
    "/undo": "撤销最近一次 PPT 修改",
    "/theme": "切换主题（dark/light/dracula）",
    "/keys": "切换快捷键方案（default/minimal）",
    "/verify": "执行演示文稿结构校验",
    "/save": "保存演示文稿（可附目标路径）",
    "/doctor": "检查模型、凭据和本地依赖",
    "/model": "查看或切换当前模型",
    "/thinking": "查看或切换思考模式（on/off）",
    "/effort": "查看或设置推理强度（high/max）",
    "/permissions": "查看或设置 shell 策略（allow/ask/deny）",
    "/plan": "切换计划模式（on/off）",
    "/activity": "展开或收起最新工作摘要",
    "/process": "设置过程显示（hidden/balanced/summary/detail）",
    "/goal": "启动或查看可恢复的长期目标",
    "/mouse": "切换鼠标输入模式（off 时终端文字可选择）",
    "/help": "查看全部命令说明",
    "/exit": "保存会话并退出小朴",
    "/quit": "保存会话并退出小朴",
}


class CommandCompleter(Completer):
    """Slash-command menu with a Chinese description beside every command."""

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if not text.startswith("/") or " " in text:
            return
        for command, description in COMMANDS.items():
            if command.startswith(text):
                yield Completion(command, start_position=-len(text), display=command, display_meta=description)


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


class XiaopuTerminalUI:
    def __init__(self, model: str | None = None) -> None:
        config.load_dotenv()
        # Interactive mode follows Claude Code/Codex: no benchmark aggregate
        # tool/token hard cap, while retaining interruption and stall guards.
        self.h = Harness(model=model, interactive=True)
        self.has_key = bool(config.provider_api_key())
        self.h.attach_printer(self._on_tool)
        # Product extension points installed once and preserved across reset().
        self.h.approval_handler = self._approve_command
        self.h.stream_callback = self._on_token
        self._approval_queue: queue.Queue = queue.Queue()
        self._streamed_text = ""
        self._theme = config.theme()
        subscribe = getattr(self.h, "subscribe", None)
        if callable(subscribe):
            subscribe(self._on_event)
        self._activity_expanded = False
        self._reasoning_view = "balanced"
        self._latest_activity: list[str] = []
        self._last_tool_error: str | None = None
        self._task_profile: dict = {}
        self._stream_counts = {"decisions": 0, "tools": 0, "verifications": 0, "repairs": 0}
        self._mouse_input = False
        self._prompt = self._make_prompt()

    def _theme_styles(self) -> dict:
        themes = {
            "dark": {"prompt": "bg:#303030 #f5f5f5 bold", "input": "bg:#303030 #f5f5f5", "": "bg:#303030 #f5f5f5"},
            "light": {"prompt": "bg:#eeeeee #111111 bold", "input": "bg:#eeeeee #111111", "": "bg:#eeeeee #111111"},
            "dracula": {"prompt": "bg:#282a36 #f8f8f2 bold", "input": "bg:#282a36 #f8f8f2", "": "bg:#282a36 #f8f8f2"},
        }
        return themes.get(getattr(self, "_theme", config.theme()), themes["dark"])

    def _make_prompt(self) -> PromptSession:
        # Mouse reporting is terminal-global and blocks native selection in
        # scrollback. Keep it off by default; /mouse on enables input clicks.
        bindings = KeyBindings()
        input_height = {"value": 1}

        def refresh_input_height(event) -> None:
            # Grow only after an explicit newline; keep the composer compact.
            # Keep the composer as tall as the actual document.  There is no
            # artificial six-line ceiling; prompt_toolkit will clip/scroll
            # naturally when the document exceeds the terminal height.
            line_count = max(1, event.current_buffer.document.line_count)
            input_height["value"] = line_count
            window = event.app.layout.current_window
            window.dont_extend_height = to_filter(True)
            window.height = Dimension.exact(line_count)
            event.app.invalidate()

        @bindings.add("enter")
        def _submit(event) -> None:
            event.current_buffer.validate_and_handle()

        @bindings.add("escape", "enter")
        def _newline(event) -> None:
            event.current_buffer.insert_text("\n")
            refresh_input_height(event)

        @bindings.add("c-j")
        def _newline_ctrl_j(event) -> None:
            event.current_buffer.insert_text("\n")
            refresh_input_height(event)

        @bindings.add("/")
        def _slash_completion(event) -> None:
            # Explicitly trigger the slash menu; some Windows terminals do
            # not emit a completion refresh for the first typed character.
            event.current_buffer.insert_text("/")
            event.current_buffer.start_completion(select_first=False)

        @bindings.add("c-o")
        def _cycle_reasoning(event) -> None:
            if config.keymap() != "minimal":
                self._cycle_reasoning_view()
                event.app.invalidate()

        @bindings.add("c-l")
        def _clear_screen(event) -> None:
            event.app.renderer.clear()

        session = PromptSession(
            completer=HybridCompleter(),
            complete_while_typing=True,
            multiline=True,
            mouse_support=self._mouse_input,
            key_bindings=bindings,
            history=FileHistory(str(config.state_home() / "history.txt")),
            enable_history_search=True,
            prompt_continuation=lambda width, line_number, is_soft_wrap: " " * width,
            style=Style.from_dict(self._theme_styles()),
            bottom_toolbar=self._live_input_status,
            # Do not reserve completion-menu rows in the idle composer.  A
            # fixed reservation makes a one-line prompt render as a large
            # empty block.  The menu is allowed to appear only while `/` is
            # being completed, so the input grows one row at a time.
            reserve_space_for_menu=0,
        )
        # Style the actual input Window, including cells after the cursor.
        # Styling fragments/rprompt only paints occupied cells and leaves the
        # middle of the row black.
        session.layout.current_window.style = "class:input"
        session.layout.current_window.char = " "
        # Claude-like compact composer: one row at rest, growing by one row for
        # every explicit newline.
        # Let the buffer content determine the preferred height (one row when
        # empty, two after a newline, etc.), while preventing the window from
        # stretching into the rest of the terminal.
        session.layout.current_window.dont_extend_height = to_filter(True)
        session.layout.current_window.height = Dimension(min=1)
        return session

    def _live_input_status(self):
        tail = "鼠标定位开" if self._mouse_input else "Esc 中断"
        return HTML(
            f"<style fg='#888888'>交互模式  ·  Enter 提交  ·  Alt+Enter/Ctrl+J 换行  ·  Ctrl+O 过程:{self._reasoning_view}  ·  {tail}</style>"
        )

    def _cycle_reasoning_view(self) -> None:
        levels = ("hidden", "balanced", "summary", "detail")
        self._reasoning_view = levels[(levels.index(self._reasoning_view) + 1) % len(levels)]

    def _set_reasoning_view(self, value: str | None) -> None:
        if value is None:
            console.print(f"[dim]过程显示：{self._reasoning_view}（Ctrl+O 循环切换）[/]\n")
            return
        normalized = value.lower()
        if normalized not in {"hidden", "balanced", "summary", "detail"}:
            console.print("[yellow]用法：/process hidden、balanced、summary 或 detail[/]\n")
            return
        self._reasoning_view = normalized
        self._set_reasoning_view(None)

    def _on_token(self, piece: str) -> None:
        """Token-level streaming display for the final text answer only."""
        self._streamed_text += piece
        console.print(piece, end="", soft_wrap=True)

    def _approve_command(self, command: str) -> str:
        """Background-thread approval request; the UI main loop answers it."""
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
            console.print()
            console.print(Panel(
                f"[bold yellow]Shell 命令需要授权[/]\n[dim]{command}[/]",
                title="权限确认", border_style="yellow", padding=(0, 1),
            ))
            try:
                answer = console.input("[yellow]允许执行？[y/N] [/]").strip().casefold()
            except (EOFError, KeyboardInterrupt):
                answer = "n"
            holder["decision"] = "allow" if answer in {"y", "yes", "是"} else "deny"
            decided.set()

    def _on_event(self, event: RuntimeEvent) -> None:
        """Render auditable summaries, never private chain-of-thought."""
        kind = event.kind
        payload = event.payload
        if kind == EventKind.TURN_STARTED:
            self._stream_counts = {"decisions": 0, "tools": 0, "verifications": 0, "repairs": 0}
            self._streamed_text = ""
            return
        if kind == EventKind.TASK_PROFILED:
            self._task_profile = payload
            self._latest_activity.append(
                "Task profile: " + str(payload.get("label", payload.get("profile", "unknown")))
                + "\nCapabilities: " + ", ".join(payload.get("capabilities", []))
                + "\nVerification: " + ", ".join(payload.get("verification", []))
            )
            if self._reasoning_view != "hidden":
                title = f"Task profile / {payload.get('label', payload.get('profile', 'unknown'))}"
                body = (
                    f"[bold]Capabilities[/]  {', '.join(payload.get('capabilities', []))}\n"
                    f"[bold]Verification[/]  {', '.join(payload.get('verification', []))}\n"
                    f"[bold]Design policy[/]  {payload.get('design_policy', '')}"
                )
                console.print(Panel(body, title=title, border_style="cyan", padding=(0, 1)))
            return
        if kind in {EventKind.TASK_PLAN, EventKind.PROGRESS_UPDATED}:
            items = list(payload.get("items", []))
            marks = {"completed": "✓", "in_progress": "→", "pending": "·", "blocked": "!"}
            body = "\n".join(
                f"[{marks.get(str(item.get('status')), '·')}] {item.get('content', '')}"
                for item in items
            ) or "尚无计划"
            self._latest_activity.append("计划与进度：\n" + body)
            # The plan is operational product state, not private chain of
            # thought. Keep it visible even when /process hidden is selected.
            title = "执行计划" if kind == EventKind.TASK_PLAN else "进度更新"
            console.print(Panel(body, title=title, border_style="bright_black", padding=(0, 1)))
            note = str(payload.get("note", "")).strip()
            if note:
                console.print(f"[yellow]计划调整[/] {note}")
            return
        if kind == EventKind.GOAL_UPDATED:
            if self._reasoning_view != "hidden":
                console.print(
                    f"[bold]Goal[/] {payload.get('status', 'active')} · "
                    f"{len(payload.get('completed', []))}/{len(payload.get('milestones', []))} · "
                    f"{payload.get('goal', '')}"
                )
            return
        if kind == EventKind.PLANNING_DECISION:
            if self._reasoning_view in {"balanced", "detail"}:
                prefix = "计划调整" if payload.get("revised") else "下一步"
                console.print(
                    f"[cyan]{prefix}[/] {payload.get('next_action', '')} "
                    f"[dim]· {payload.get('reason', '')}[/]"
                )
            return
        if kind == EventKind.PHASE_CHANGED:
            if self._reasoning_view != "hidden":
                console.print(
                    f"[cyan]Phase[/] {payload.get('from_phase', '?')} -> "
                    f"[bold]{payload.get('to_phase', '?')}[/]"
                    + (f"  [dim]{payload.get('reason', '')[:150]}[/]" if payload.get("reason") else "")
                )
            return
        if kind == EventKind.CONTROLLER_DECISION:
            self._stream_counts["decisions"] += 1
            if self._reasoning_view != "hidden":
                console.print(
                    f"[magenta]Decision[/] {payload.get('action', 'continue')}  "
                    f"[dim]phase={payload.get('phase', '?')} · {payload.get('reason', '')[:180]}[/]"
                )
            return
        if kind == EventKind.MODEL_RESPONSE:
            if self._reasoning_view in {"balanced", "detail"}:
                count = payload.get("tool_call_count", 0)
                if count:
                    console.print(
                        f"[dim]Model turn[/] · {count} tool call(s) requested · "
                        f"auditable reasoning signal {payload.get('reasoning_chars', 0)} chars"
                    )
                else:
                    console.print(
                        "[yellow]Model turn[/] · no tool call · controller will check evidence before completion"
                    )
            return
        if kind == EventKind.TOOL_STARTED:
            self._stream_counts["tools"] += 1
            return
        if kind == EventKind.TOOL_COMPLETED:
            name = str(payload.get("tool", ""))
            if name in {"ppt_check", "ppt_verify", "ppt_quality_check", "render_deck", "inspect_rendered_deck"}:
                self._stream_counts["verifications"] += 1
            return
        if kind == EventKind.TOOL_FAILED:
            if self._reasoning_view != "hidden":
                console.print(f"[red]Tool failure[/] {payload.get('tool', '?')}: {str(payload.get('error', ''))[:180]}")
            return
        if kind == EventKind.TURN_COMPLETED and self._reasoning_view != "hidden":
            artifact = payload.get("artifact") or "none"
            body = (
                f"[bold]Stop[/] {payload.get('stop_reason', '?')}   [bold]Phase[/] {payload.get('phase', '?')}\n"
                f"[bold]Events[/] decisions={self._stream_counts['decisions']} · tools={self._stream_counts['tools']} · "
                f"verifications={self._stream_counts['verifications']}\n"
                f"[bold]Artifact[/] {redact(str(artifact))}"
            )
            console.print(Panel(body, title="Run summary", border_style="green", padding=(0, 1)))

    def _set_mouse_input(self, value: str | None) -> None:
        if value is None:
            state = "开启" if self._mouse_input else "关闭"
            console.print(f"[dim]鼠标输入定位：{state}。关闭时可以拖选复制终端输出。[/]\n")
            return
        normalized = value.lower()
        if normalized not in {"on", "off"}:
            console.print("[yellow]用法：/mouse on 或 /mouse off[/]\n")
            return
        self._mouse_input = normalized == "on"
        self._prompt = self._make_prompt()
        self._set_mouse_input(None)

    @staticmethod
    def _input_width() -> int:
        return max(24, shutil.get_terminal_size(fallback=(100, 30)).columns - 2)

    def _print_input_top_bar(self) -> None:
        console.print("─" * self._input_width(), style="bright_black", soft_wrap=True)

    def print_welcome(self) -> None:
        status = "Ready" if self.has_key else "Configuration required"
        left = Text()
        left.append("Welcome back!\n\n", style="bold white")
        # This is a LiSu raster projected into true-colour terminal pixels.
        # It remains exactly the two requested characters, with no frame or
        # romanised wordmark competing for attention.
        left.append("\n")
        left.append_text(wordmark())
        left.append("\n")
        right = Text()
        right.append("Tips for getting started\n", style="bold white")
        right.append("Describe a PPT task, or type /help for commands.\n\n", style="dim")
        right.append("Runtime\n", style="bold white")
        right.append(f"{self.h.llm.model} · {config.provider()}\n", style="white")
        right.append(f"Workspace: {config.sandbox_root()}\n", style="dim")
        right.append(f"Status: {status}", style="white" if self.has_key else "yellow")
        if not self.has_key:
            right.append(f"\nSet {config.provider_credential_name()}, then restart.", style="yellow")
        grid = Table.grid(expand=True, padding=(0, 3))
        grid.add_column(ratio=3)
        grid.add_column(ratio=2)
        grid.add_row(left, right)
        console.print()
        console.print(Panel(grid, border_style="bright_black", title="小朴 · Xiaopu v0.2.0", subtitle="Type /help for help · /exit to quit"))
        console.print()

    def _on_tool(self, name: str, args: str, out: str) -> None:
        try:
            parsed = json.loads(args)
            pretty_args = json.dumps(parsed, ensure_ascii=False)
        except Exception:
            parsed = {}
            pretty_args = args
        pretty_args = redact(pretty_args[:120] + ("..." if len(pretty_args) > 120 else ""))
        labels = {
            "read_file": "读取", "write_file": "写入", "edit_file": "编辑",
            "list_dir": "列出目录", "glob_files": "查找文件", "search_text": "搜索内容",
            "discover_workspace": "发现工作区", "bind_provenance": "记录文件来源",
            "update_tasks": "更新任务", "git_status": "检查工作区改动", "git_diff": "查看改动",
            "open_deck": "打开演示文稿", "shape_inventory": "检查页面对象",
            "replace_shape_text": "修改文字", "set_shape_geometry": "调整排版",
            "save_deck": "保存演示文稿", "ppt_verify": "结构检查",
            "render_deck": "渲染演示文稿", "inspect_rendered_deck": "视觉检查",
            "run_python": "运行脚本", "run_shell": "运行命令", "finish": "完成任务",
        }
        target = next((parsed.get(key) for key in ("path", "output_dir", "image_path", "command") if parsed.get(key)), "")
        target_text = f"([underline]{redact(str(target))[:90]}[/])" if target else ""
        failed = (out or "").lstrip().startswith(("TOOL ERROR", "PERMISSION ASK", "CANCELLED"))
        error_key = f"{name}:{(out or '').strip()}" if failed else None
        if error_key and error_key == self._last_tool_error:
            return
        self._last_tool_error = error_key
        label = labels.get(name, name)
        self._latest_activity.append(
            f"动作：{label}\n目标：{pretty_args or '当前任务'}\n结果：{redact((out or '').strip())[:500]}"
        )
        if self._reasoning_view == "hidden":
            return
        dot = "[red]●[/]" if failed else "[white]●[/]"
        console.print(f"{dot} [bold]{label}[/]{target_text}")
        lines = [redact(line) for line in (out or "").splitlines() if line.strip()]
        if self._reasoning_view in {"balanced", "summary"}:
            if failed:
                message = lines[0] if lines else "未知错误"
                message = message.replace("TOOL ERROR ", "").replace("PERMISSION ASK", "需要授权")
                lines = [f"失败 · {message}"]
            elif name in {"read_file", "list_dir", "glob_files", "search_text"}:
                line_count = len(lines)
                char_count = len(out or "")
                lines = [f"完成 · 获得 {line_count} 行 / {char_count} 字符"]
            elif name in {"run_python", "run_shell"}:
                exit_line = next((line for line in lines if "exit_code" in line), "执行完成")
                lines = [f"完成 · {exit_line}"]
            elif name == "finish":
                lines = ["已提交最终结果"]
            else:
                lines = [f"完成 · {lines[0][:120]}" if lines else "完成"]
        for index, line in enumerate(lines[:6]):
            branch = "└─" if index == min(len(lines), 6) - 1 else "├─"
            console.print(f"  [dim]{branch} {line[:180]}[/]")
        if len(lines) > 6:
            console.print(f"  [dim]└─ … 另有 {len(lines) - 6} 行（/activity 查看摘要）[/]")
        console.print()

    def _show_activity(self) -> None:
        if not self._latest_activity:
            console.print("[dim]暂无可展开的工作摘要。[/]\n")
            return
        console.print(Panel("\n\n".join(self._latest_activity), title="小朴 · 工作摘要（可审计，不含隐藏推理）", border_style="cyan"))

    def _toggle_activity(self) -> None:
        self._activity_expanded = not self._activity_expanded
        if self._activity_expanded:
            self._show_activity()
        else:
            console.print("[dim]工作摘要已收起。输入 /activity 再次展开。[/]\n")

    def _thinking_status(self) -> None:
        enabled = config.thinking_enabled()
        state = self.h.state
        observed = (
            f"已观测到服务端推理信号（本轮 {state.last_reasoning_chars} 字符，累计 {state.reasoning_chars} 字符）"
            if state.reasoning_observed else "尚未观测到服务端 reasoning 字段"
        )
        console.print(
            f"思考模式：{'开启' if enabled else '关闭'}；推理强度：{config.reasoning_effort()}。"
            f"{observed}。原始隐藏思维链不会显示；使用 /activity 展开可审计工作摘要。\n"
        )

    def _set_thinking(self, value: str | None) -> None:
        if value is None:
            self._thinking_status()
            return
        normalized = value.lower()
        if normalized not in {"on", "off"}:
            console.print("[yellow]用法：/thinking on 或 /thinking off[/]\n")
            return
        os.environ["THINKING_ENABLED"] = "1" if normalized == "on" else "0"
        self._thinking_status()

    def _set_effort(self, value: str | None) -> None:
        if value is None:
            self._thinking_status()
            return
        normalized = value.lower()
        if normalized not in {"high", "max"}:
            console.print("[yellow]用法：/effort high 或 /effort max[/]\n")
            return
        os.environ["REASONING_EFFORT"] = normalized
        self._thinking_status()

    def _status(self) -> None:
        state = self.h.state
        contract = getattr(state, "execution_contract", None)
        fresh_kinds = sorted({record.kind for record in state.fresh_evidence()})
        body = (
            f"[bold]Phase[/] {state.phase.value}   [bold]Mutation epoch[/] {state.mutation_epoch}\n"
            f"[bold]Fresh evidence[/] {', '.join(fresh_kinds) or '无'}\n"
            f"[bold]Repair[/] {state.repair_attempts}/{state.max_repairs}   "
            f"[bold]Unresolved[/] {', '.join(sorted(state.unresolved_checks)) or '无'}\n"
            f"[bold]Budget[/] tokens {state.total_tokens} · generated {state.generated_output_tokens} · "
            f"tool calls {state.tool_calls}\n"
            f"[bold]Contract[/] {getattr(contract, 'capability', '?')} · "
            f"certs {sorted(getattr(contract, 'finish_certificates', ()) or ()) or '无'}"
        )
        console.print(Panel(body, title="小朴 · Loop 状态（可审计，不含隐藏推理）", border_style="bright_black", padding=(0, 1)))

    def _show_sessions(self) -> None:
        from .session_store import list_sessions

        records = list_sessions()
        if not records:
            console.print("[dim]暂无已保存会话。运行任务后退出或使用 /new 会自动保存。[/]\n")
            return
        table = Table(title="小朴 · 会话", border_style="bright_black", expand=True)
        table.add_column("#", justify="right", width=4)
        table.add_column("id", width=14)
        table.add_column("标题", ratio=3)
        table.add_column("模型", width=18)
        table.add_column("轮次", justify="right", width=6)
        table.add_column("更新时间", width=22)
        for index, record in enumerate(records, 1):
            table.add_row(str(index), record.id[:12], record.title, record.model,
                          str(record.turn_count), record.updated_at)
        console.print(table)
        console.print("[dim]使用 /resume <序号|id> 恢复会话。[/]\n")

    def _resume(self, token: str | None) -> None:
        from .session_store import list_sessions, restore_harness

        if not token:
            self._show_sessions()
            return
        records = list_sessions()
        session_id = token
        if token.isdigit() and 1 <= int(token) <= len(records):
            session_id = records[int(token) - 1].id
        payload = None
        for record in records:
            if record.id == session_id or record.id.startswith(session_id):
                from .session_store import load_session

                payload = load_session(record.id)
                break
        if payload is None:
            console.print(f"[yellow]未找到会话：{token}[/]\n")
            return
        report = restore_harness(self.h, payload)
        console.print(f"[dim white]{report}[/]\n")

    def _show_context(self) -> None:
        state = self.h.state
        limit = config.max_total_tokens()
        used = min(state.total_tokens, limit)
        bar = ProgressBar(total=limit, completed=used, width=50)
        input_tokens = max(0, state.total_tokens - state.generated_output_tokens)
        price_in = _price("XIAOPU_PRICE_INPUT_PER_M")
        price_out = _price("XIAOPU_PRICE_OUTPUT_PER_M")
        cost_line = (
            f"费用估算：${input_tokens / 1_000_000 * price_in + state.generated_output_tokens / 1_000_000 * price_out:.6f}"
            if price_in > 0 or price_out > 0
            else "费用估算：未配置单价（设置 XIAOPU_PRICE_INPUT_PER_M / XIAOPU_PRICE_OUTPUT_PER_M，单位 USD/1M tokens）"
        )
        console.print(
            f"上下文预算：{used:,} / {limit:,} tokens（模型输入累计；达到上限前自动压缩）\n"
            f"[dim]{bar}[/]\n"
            f"生成输出：{state.generated_output_tokens:,} tokens · 工具调用 {state.tool_calls} 次\n"
            f"思考信号：累计 {state.reasoning_chars:,} 字符（原始思维链永不显示）\n"
            f"{cost_line}\n"
        )

    def _show_model(self) -> None:
        from . import config as cfg

        current = getattr(self.h.llm, "model", config.model())
        console.print(
            f"当前模型：{current}（provider={config.provider()}）\n"
            "可用模型：" + ", ".join(cfg.known_models()) + "\n"
            "用法：/model <名称> 切换（仅限 OpenAI-compatible 模型，重启后仍可覆盖）。\n"
        )

    def _set_model(self, value: str | None) -> None:
        if value is None:
            self._show_model()
            return
        known = config.known_models()
        if value not in known:
            console.print(f"[yellow]未知模型：{value}。可用：{', '.join(known)}[/]\n")
            return
        if config.provider() == "anthropic":
            os.environ["ANTHROPIC_MODEL"] = value
        else:
            os.environ["OPENAI_MODEL"] = value
        self.h.llm.model = value
        self._show_model()

    def _permissions(self, value: str | None) -> None:
        current = config.command_policy()
        if value is None:
            console.print(f"Shell 策略：{current}（allow=全部放行 / ask=外部写、网络与危险命令需授权 / deny=全部拒绝）\n")
            return
        normalized = value.lower()
        if normalized not in {"allow", "ask", "deny"}:
            console.print("[yellow]用法：/permissions allow、ask 或 deny[/]\n")
            return
        os.environ["COMMAND_POLICY"] = normalized
        console.print(f"[dim white]Shell 策略已切换为：{normalized}[/]\n")

    def _plan(self, value: str | None) -> None:
        current = config.plan_mode()
        if value is None:
            value = "off" if current else "on"
        normalized = value.lower()
        if normalized not in {"on", "off"}:
            console.print("[yellow]用法：/plan on 或 /plan off[/]\n")
            return
        config.set_plan_mode(normalized == "on")
        console.print(f"[dim white]计划模式：{'开启（先给计划，不修改文件）' if normalized == 'on' else '关闭'}[/]\n")

    def _export(self, path: str | None) -> None:
        from .session_store import export_session, save_session

        record = save_session(self.h)
        target = Path(path) if path else Path.cwd() / f"xiaopu-session-{record.id}.md"
        exported = export_session(record.id, target)
        console.print(f"[dim white]会话已导出：{exported}[/]\n")

    def run_interactive(self) -> int:
        self.print_welcome()
        while True:
            try:
                self._print_input_top_bar()
                user_input = self._prompt.prompt(
                    [("class:prompt", "❯ ")],
                ).strip()
            except (EOFError, KeyboardInterrupt):
                console.print("\n[dim white]Exiting.[/]")
                break
            if not user_input:
                continue
            parts = user_input.split(None, 1)
            cmd = parts[0].lower()
            if cmd in ("/quit", "/exit", "/q"):
                from .session_store import save_session
                save_session(self.h)
                break
            if cmd in ("/help", "/h"):
                console.print(XIAOPU_HELP)
                continue
            if cmd == "/new":
                from .session_store import save_session
                record = save_session(self.h)
                self.h.reset()
                console.print(f"[dim white]会话已保存（{record.id[:12]}）并重置，记忆与演示文稿已清空。[/]\n")
                continue
            if cmd == "/sessions":
                self._show_sessions()
                continue
            if cmd == "/resume":
                self._resume(parts[1].strip() if len(parts) > 1 else None)
                continue
            if cmd == "/export":
                self._export(parts[1].strip() if len(parts) > 1 else None)
                continue
            if cmd == "/context":
                self._show_context()
                continue
            if cmd == "/compact":
                self.h._maybe_compact(force=True)
                console.print("[dim white]上下文已压缩，完整状态保留在运行账本中。[/]\n")
                continue
            if cmd == "/model":
                self._set_model(parts[1].strip() if len(parts) > 1 else None)
                continue
            if cmd == "/permissions":
                self._permissions(parts[1].strip() if len(parts) > 1 else None)
                continue
            if cmd == "/plan":
                self._plan(parts[1].strip() if len(parts) > 1 else None)
                continue
            if cmd == "/info":
                console.print(f"[dim white]{dispatch('deck_info', '{}', self.h)}[/]\n")
                continue
            if cmd == "/status":
                self._status()
                continue
            if cmd == "/undo":
                console.print(f"[dim white]{self.h.undo()}[/]\n")
                continue
            if cmd == "/theme":
                value = (parts[1].strip() if len(parts) > 1 else None) or "dark"
                if value not in config.THEMES:
                    console.print(f"[yellow]可用主题：{', '.join(config.THEMES)}[/]\n")
                    continue
                config.set_theme(value)
                self._theme = value
                self._prompt = self._make_prompt()
                console.print(f"[dim white]主题已切换：{value}[/]\n")
                continue
            if cmd == "/keys":
                value = (parts[1].strip() if len(parts) > 1 else None) or ("minimal" if config.keymap() == "default" else "default")
                if value not in {"default", "minimal"}:
                    console.print("[yellow]用法：/keys default 或 /keys minimal[/]\n")
                    continue
                config.set_keymap(value)
                self._prompt = self._make_prompt()
                console.print(f"[dim white]快捷键方案：{value}（Ctrl+O {'启用' if value == 'default' else '禁用'}）[/]\n")
                continue
            if cmd == "/verify":
                console.print(f"[dim white]{dispatch('ppt_verify', '{}', self.h)}[/]\n")
                continue
            if cmd == "/save":
                path = parts[1].strip() if len(parts) > 1 else None
                result = dispatch("save_deck", json.dumps({"path": path}) if path else "{}", self.h)
                console.print(f"[bold white]Saved:[/] {result}\n")
                continue
            if cmd == "/doctor":
                from .doctor import report
                payload = report()
                rows = [(str(key), str(value)) for key, value in payload.items()]
                table = Table(show_header=False, border_style="bright_black", expand=True)
                table.add_column("项", style="bold", width=24)
                table.add_column("值")
                for key, value in rows:
                    table.add_row(key, value)
                console.print(Panel(table, title="小朴 · Doctor（密钥永不显示）", border_style="bright_black", padding=(0, 1)))
                continue
            if cmd == "/activity":
                self._toggle_activity()
                continue
            if cmd == "/goal":
                objective = parts[1].strip() if len(parts) > 1 else ""
                console.print(self.h.start_goal(objective) if objective else self.h.goal_summary())
                continue
            if cmd in {"/process", "/reasoning"}:
                self._set_reasoning_view(parts[1].strip() if len(parts) > 1 else None)
                continue
            if cmd == "/mouse":
                self._set_mouse_input(parts[1].strip() if len(parts) > 1 else None)
                continue
            if cmd == "/thinking":
                self._set_thinking(parts[1].strip() if len(parts) > 1 else None)
                continue
            if cmd == "/effort":
                self._set_effort(parts[1].strip() if len(parts) > 1 else None)
                continue
            self._execute(user_input)
        return 0

    def _execute(self, task: str) -> None:
        if not self.has_key:
            console.print(
                "[bold red]CONFIGURATION ERROR:[/] "
                f"{config.provider_credential_name()} is required for PROVIDER={config.provider()!r}. "
                "No task was sent and no offline fallback is available. "
                "Configure the credential, restart 小朴, then try again.\n"
            )
            return
        self._latest_activity = [f"目标：{task}"]
        self._last_tool_error = None
        started = time.monotonic()
        effort = config.reasoning_effort()
        with console.status(f"[dim]agent loop · decision / tool / verification · effort={effort}[/]", spinner="dots"):
            try:
                reply = self._run_interruptibly(task)
                elapsed = max(0, round(time.monotonic() - started))
                console.print()
                if self._streamed_text and reply.strip() == self._streamed_text.strip():
                    reply_rendered = False
                else:
                    reply_rendered = True
                    if reply.startswith(("⚠", "⏹")):
                        console.print(Panel(Markdown(reply), title="小朴 · 可恢复暂停", border_style="yellow"))
                    else:
                        console.print(Markdown(reply))
                state = self.h.state
                signal = f"已收到推理信号 · {state.last_reasoning_chars} 字符" if state.last_reasoning_chars else "未收到推理信号"
                if reply.startswith(("⚠", "⏹")):
                    console.print(f"[dim]Ⅱ 已暂停于 {elapsed} 秒 · {effort} 推理 · {signal}[/]")
                else:
                    console.print(f"[dim]✣ 完成于 {elapsed} 秒 · {effort} 推理 · {signal}[/]")
                if not reply_rendered:
                    console.print()
                console.print()
                if self._activity_expanded:
                    self._show_activity()
            except Exception as exc:
                console.print(f"[bold red]RUNTIME ERROR[/] ({type(exc).__name__}): {exc}\n")

    def _run_interruptibly(self, task: str) -> str:
        """Run the harness while keeping Esc responsive on Windows."""
        results: queue.Queue[tuple[str, object]] = queue.Queue(maxsize=1)

        def worker() -> None:
            try:
                results.put(("ok", self.h.run(task)))
            except BaseException as exc:  # propagate on the UI thread
                results.put(("error", exc))

        thread = threading.Thread(target=worker, name="xiaopu-agent-run", daemon=True)
        thread.start()
        interrupt_announced = False
        while thread.is_alive():
            try:
                self._drain_approvals()
                if os.name == "nt":
                    import msvcrt

                    while msvcrt.kbhit():
                        key = msvcrt.getwch()
                        if key in {"\x1b", "\x03"}:  # Esc and Ctrl+C both interrupt
                            self.h.request_cancel()
                            if not interrupt_announced:
                                console.print("\n[yellow]⏹ 已收到中止请求，正在停止当前步骤…[/]")
                                interrupt_announced = True
                        elif key in {"\x00", "\xe0"} and msvcrt.kbhit():
                            msvcrt.getwch()  # consume the extended-key suffix
                thread.join(0.05)
            except KeyboardInterrupt:
                self.h.request_cancel()
                if not interrupt_announced:
                    console.print("\n[yellow]⏹ 已收到中止请求，正在停止当前步骤…[/]")
                    interrupt_announced = True
        self._drain_approvals()
        kind, value = results.get()
        if kind == "error":
            raise value
        return str(value)


def run_tui(model: str | None = None) -> int:
    return XiaopuTerminalUI(model=model).run_interactive()
