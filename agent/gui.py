"""Modern CustomTkinter GUI for the complete Xiaopu Harness.

Layout: sidebar (sessions / workspace) · chat center · live process/evidence
right · composer bottom.  The harness runs on a worker thread and the UI only
drains thread-safe queues, so streaming, approvals and interruption work
exactly like the CLI.
"""
from __future__ import annotations

import argparse
import json
import os
import queue
import threading
import time
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from . import config
from .events import EventKind
from .tools.registry import dispatch

ACCENT = "#2f9e6e"
ACCENT_HOVER = "#277d58"
SIDEBAR = "#151a22"
CHAT_BG = "#0f141b"
PROCESS_BG = "#0b0f14"
INPUT_BG = "#171e28"


class AgentGUI:
    def __init__(self, root: ctk.CTk, model: str | None = None) -> None:
        from .harness import Harness

        self.root = root
        self.model = model
        self.h = Harness(model=model, interactive=True)
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.approvals: queue.Queue = queue.Queue()
        self.running = False
        self.process_visible = True
        self.status = ctk.StringVar(value="就绪")
        self.live_action = ctk.StringVar(value="等待任务")
        self.live_phase = ctk.StringVar(value="阶段：—")
        self.live_elapsed = ctk.StringVar(value="0 秒")
        self.live_counts = ctk.StringVar(value="工具 0 · 完成 0 · 失败 0")
        self.model_var = ctk.StringVar(value=getattr(self.h.llm, "model", config.model()))
        self.permissions_var = ctk.StringVar(value=config.command_policy())
        self.workspace_var = ctk.StringVar(value=str(config.sandbox_root()))
        self.started_at = None
        self.tool_started_count = self.tool_completed_count = self.tool_failed_count = 0
        self.tool_log_lines: list[str] = []
        self._streaming_started = False
        self._session_records = []
        self._workspace_records = []
        self.h.approval_handler = self._approve_command
        self.h.stream_callback = self._on_stream_token
        self.h.subscribe(self._capture_runtime_event)
        self._build()
        from .workspace_store import register_workspace
        try:
            register_workspace(self.workspace_var.get())
        except Exception:
            pass
        self._refresh_sessions()
        self._refresh_workspaces()
        self.root.after(60, self._drain_events)
        self.root.after(120, self._drain_approvals)
        self.root.after(250, self._tick_elapsed)
        self._refresh_status()

    # ------------------------------------------------------------ layout
    def _build(self) -> None:
        self.root.title("小朴 Agent · Xiaopu")
        self.root.geometry("1280x800")
        self.root.minsize(900, 620)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.root.configure(fg_color=SIDEBAR)

        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(1, weight=1)

        self._build_sidebar()
        self._build_main()

    def _build_sidebar(self) -> None:
        sidebar = ctk.CTkFrame(self.root, width=250, corner_radius=0, fg_color=SIDEBAR)
        sidebar.grid(row=0, column=0, rowspan=2, sticky="nsew")
        sidebar.grid_propagate(False)
        sidebar.grid_columnconfigure(0, weight=1)

        title = ctk.CTkFrame(sidebar, fg_color="transparent")
        title.grid(row=0, column=0, padx=18, pady=(22, 14), sticky="ew")
        ctk.CTkLabel(title, text="小朴", font=ctk.CTkFont("Microsoft YaHei UI", 26, "bold"),
                     text_color="#eaf2ee").pack(anchor="w")
        ctk.CTkLabel(title, text="Xiaopu Agent · PowerPoint 强化",
                     font=ctk.CTkFont("Microsoft YaHei UI", 11),
                     text_color="#7e8b98").pack(anchor="w")

        info = ctk.CTkFrame(sidebar, corner_radius=14, fg_color="#1c242e")
        info.grid(row=1, column=0, padx=16, pady=(0, 14), sticky="ew")
        info.grid_columnconfigure(0, weight=1)
        self._info_label(info, "模型", self.model_var)
        model = ctk.CTkComboBox(info, variable=self.model_var, values=config.known_models(),
                                state="readonly", command=self._switch_model,
                                corner_radius=10, height=32)
        model.grid(row=1, column=0, padx=12, pady=(0, 10), sticky="ew")
        self._info_label(info, "Shell 权限", self.permissions_var)
        perms = ctk.CTkComboBox(info, variable=self.permissions_var, values=("allow", "ask", "deny"),
                                state="readonly", command=self._switch_permissions,
                                corner_radius=10, height=32)
        perms.grid(row=3, column=0, padx=12, pady=(0, 12), sticky="ew")

        self.session_frame = ctk.CTkScrollableFrame(sidebar, label_text="会话", corner_radius=14,
                                                    fg_color="#1c242e", label_fg_color=ACCENT)
        self.session_frame.grid(row=2, column=0, padx=16, pady=(0, 10), sticky="nsew")
        self.session_frame.grid_columnconfigure(0, weight=1)
        self.workspace_frame = ctk.CTkScrollableFrame(sidebar, label_text="工作区", corner_radius=14,
                                                      fg_color="#1c242e", label_fg_color=ACCENT)
        self.workspace_frame.grid(row=3, column=0, padx=16, pady=(0, 12), sticky="nsew")
        self.workspace_frame.grid_columnconfigure(0, weight=1)
        sidebar.grid_rowconfigure(2, weight=3)
        sidebar.grid_rowconfigure(3, weight=2)

        footer = ctk.CTkFrame(sidebar, fg_color="transparent")
        footer.grid(row=4, column=0, padx=16, pady=(0, 16), sticky="ew")
        ctk.CTkLabel(footer, text=f"{config.provider()} · v0.2.0",
                     font=ctk.CTkFont("Microsoft YaHei UI", 10),
                     text_color="#5e6c78").pack(anchor="w")

    @staticmethod
    def _info_label(parent, text: str, variable) -> None:
        label = ctk.CTkLabel(parent, text=text, anchor="w",
                             font=ctk.CTkFont("Microsoft YaHei UI", 11, "bold"),
                             text_color="#aebac6")
        label.grid(row=len(parent.winfo_children()), column=0, padx=12, pady=(10, 2), sticky="ew")

    def _build_main(self) -> None:
        main = ctk.CTkFrame(self.root, corner_radius=0, fg_color="#0e141c")
        main.grid(row=0, column=1, rowspan=2, sticky="nsew")
        main.grid_columnconfigure(1, weight=1)
        main.grid_rowconfigure(1, weight=1)

        topbar = ctk.CTkFrame(main, fg_color="transparent")
        topbar.grid(row=0, column=0, columnspan=2, padx=18, pady=(14, 8), sticky="ew")
        topbar.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(topbar, text="＋ 新会话", width=86, height=32, corner_radius=10,
                      fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      command=self._new_session).grid(row=0, column=1, padx=(0, 6))
        ctk.CTkButton(topbar, text="验证", width=64, height=32, corner_radius=10,
                      command=self._verify).grid(row=0, column=2, padx=6)
        ctk.CTkButton(topbar, text="保存 PPT", width=80, height=32, corner_radius=10,
                      command=self._save_ppt).grid(row=0, column=3, padx=6)
        ctk.CTkButton(topbar, text="导出", width=64, height=32, corner_radius=10,
                      command=self._export_session).grid(row=0, column=4, padx=6)
        ctk.CTkButton(topbar, text="撤销", width=64, height=32, corner_radius=10,
                      command=self._undo).grid(row=0, column=5, padx=(6, 0))

        livebar = ctk.CTkFrame(main, corner_radius=14, fg_color="#171e28")
        livebar.grid(row=0, column=0, padx=18, pady=(70, 8), sticky="ew")
        ctk.CTkLabel(livebar, text="●", text_color="#52c98c", font=ctk.CTkFont("Microsoft YaHei UI", 16)).pack(side="left", padx=(14, 6))
        ctk.CTkLabel(livebar, textvariable=self.live_action, font=ctk.CTkFont("Microsoft YaHei UI", 12, "bold")).pack(side="left", padx=(0, 14))
        ctk.CTkLabel(livebar, textvariable=self.live_phase, text_color="#9aa7b2").pack(side="left")
        ctk.CTkLabel(livebar, textvariable=self.live_counts, text_color="#7e8b98").pack(side="right", padx=(0, 12))
        ctk.CTkLabel(livebar, textvariable=self.live_elapsed, text_color="#9aa7b2").pack(side="right", padx=(0, 10))

        center = ctk.CTkFrame(main, fg_color="transparent")
        center.grid(row=1, column=1, sticky="nsew", padx=(0, 10), pady=(0, 10))
        center.grid_columnconfigure(0, weight=1)
        center.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(center, text="对话", anchor="w", font=ctk.CTkFont("Microsoft YaHei UI", 13, "bold")).grid(row=0, column=0, pady=(0, 4), sticky="w")
        self.chat = ctk.CTkTextbox(center, wrap="word", corner_radius=16, fg_color=CHAT_BG,
                                   border_width=1, border_color="#242d39",
                                   font=ctk.CTkFont("Microsoft YaHei UI", 13))
        self.chat.grid(row=1, column=0, sticky="nsew")
        self._make_readonly_selectable(self.chat)
        self.chat.tag_config("user", foreground="#ffffff", spacing1=6, spacing3=6)
        self.chat.tag_config("assistant", foreground="#d6e1dc", spacing1=6, spacing3=6)
        self.chat.tag_config("error", foreground="#ff9b8e", spacing1=6, spacing3=6)

        self.process = ctk.CTkTabview(main, corner_radius=16, fg_color="#0f141b",
                                      border_width=1, border_color="#242d39")
        self.process.grid(row=1, column=2, sticky="nsew", padx=(0, 18), pady=(0, 10))
        self.process.add("计划")
        self.process.add("工具")
        self.process.add("推理信号")
        self.plan_box = self._process_box("计划")
        self.tool_box = self._process_box("工具")
        self.signal_box = self._process_box("推理信号")
        self._append(self.signal_box, "这里显示模型实际返回的推理信号状态和可审计摘要。\n不会伪造或展示模型未提供的私有思维链。")

        goal = ctk.CTkFrame(main, fg_color="transparent")
        goal.grid(row=2, column=0, columnspan=3, padx=18, pady=(0, 6), sticky="ew")
        goal.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(goal, text="长期目标", font=ctk.CTkFont("Microsoft YaHei UI", 12, "bold")).grid(row=0, column=0, padx=(0, 8))
        self.goal_entry = ctk.CTkEntry(goal, placeholder_text="可留空；输入目标后点击启动",
                                       corner_radius=10, height=34, fg_color=INPUT_BG)
        self.goal_entry.grid(row=0, column=1, sticky="ew")
        ctk.CTkButton(goal, text="启动", width=70, height=34, corner_radius=10,
                      command=self._start_goal).grid(row=0, column=2, padx=8)
        ctk.CTkButton(goal, text="查看", width=70, height=34, corner_radius=10,
                      command=self._show_goal).grid(row=0, column=3)

        composer = ctk.CTkFrame(main, fg_color="transparent")
        composer.grid(row=3, column=0, columnspan=3, padx=18, pady=(0, 16), sticky="ew")
        composer.grid_columnconfigure(0, weight=1)
        self.input = ctk.CTkTextbox(composer, height=84, wrap="word", corner_radius=14,
                                    fg_color=INPUT_BG, border_width=1, border_color="#2c3745",
                                    font=ctk.CTkFont("Microsoft YaHei UI", 13))
        self.input.grid(row=0, column=0, sticky="ew")
        self.input.bind("<Control-Return>", lambda _e: self._send() or "break")
        button_col = ctk.CTkFrame(composer, fg_color="transparent")
        button_col.grid(row=0, column=1, padx=(10, 0))
        self.send = ctk.CTkButton(button_col, text="发送", width=92, height=38,
                                  corner_radius=12, fg_color=ACCENT, hover_color=ACCENT_HOVER,
                                  command=self._send)
        self.send.pack()
        self.stop = ctk.CTkButton(button_col, text="中断", width=92, height=38, corner_radius=12,
                                  fg_color="#a13c3c", hover_color="#7d2f2f",
                                  command=self._cancel, state="disabled")
        self.stop.pack(pady=(8, 0))

        statusbar = ctk.CTkFrame(main, corner_radius=0, fg_color="#10161f", height=30)
        statusbar.grid(row=4, column=0, columnspan=3, sticky="ew")
        ctk.CTkLabel(statusbar, textvariable=self.status, text_color="#9aa7b2",
                     font=ctk.CTkFont("Microsoft YaHei UI", 10)).pack(side="left", padx=16)
        ctk.CTkLabel(statusbar, text="Ctrl+Enter 发送 · 可多行输入", text_color="#5e6c78",
                     font=ctk.CTkFont("Microsoft YaHei UI", 10)).pack(side="right", padx=16)

        main.grid_columnconfigure(1, weight=3)
        main.grid_columnconfigure(2, weight=2)
        main.grid_rowconfigure(0, weight=0)
        self._append_chat("小朴", "已就绪。输入一句任务，或先启动长期 Goal。", "assistant")

    def _process_box(self, tab: str) -> ctk.CTkTextbox:
        box = ctk.CTkTextbox(self.process.tab(tab), wrap="word", corner_radius=0,
                             fg_color=PROCESS_BG, border_width=0,
                             font=ctk.CTkFont("Consolas", 11))
        box.pack(fill="both", expand=True, padx=8, pady=8)
        self._make_readonly_selectable(box)
        return box

    # ------------------------------------------------------------ helpers
    def _append(self, widget: ctk.CTkTextbox, text: str, tag: str | None = None) -> None:
        widget.configure(state="normal")
        widget.insert("end", text + "\n", tag)
        widget.see("end")
        widget.configure(state="disabled")

    @staticmethod
    def _make_readonly_selectable(widget) -> None:
        """Keep output selectable/copyable while rejecting all mutations."""
        widget._xiaopu_readonly = True

        def on_key(event):
            control = bool(event.state & 0x4)
            key = event.keysym.lower()
            if control and key == "a":
                widget.tag_add("sel", "1.0", "end-1c")
                return "break"
            if control and key in {"c", "insert"}:
                return None
            if key in {"left", "right", "up", "down", "home", "end", "prior", "next"}:
                return None
            return "break"

        widget.bind("<KeyPress>", on_key)
        widget.bind("<<Paste>>", lambda _event: "break")
        widget.bind("<<Cut>>", lambda _event: "break")

    def _append_chat(self, role: str, text: str, tag: str) -> None:
        self._append(self.chat, f"{role}\n{text}\n", tag)

    def _switch_model(self, _event=None) -> None:
        value = self.model_var.get().strip()
        if not value:
            return
        if config.provider() == "anthropic":
            os.environ["ANTHROPIC_MODEL"] = value
        else:
            os.environ["OPENAI_MODEL"] = value
        self.h.llm.model = value
        self._refresh_status()

    def _switch_permissions(self, _event=None) -> None:
        os.environ["COMMAND_POLICY"] = self.permissions_var.get()
        self.status.set(f"Shell 策略：{self.permissions_var.get()}")

    # ------------------------------------------------------------ sessions
    def _refresh_sessions(self) -> None:
        from .session_store import list_sessions

        for child in self.session_frame.winfo_children():
            child.destroy()
        self._session_records = list_sessions()
        if not self._session_records:
            ctk.CTkLabel(self.session_frame, text="暂无保存的会话",
                         text_color="#5e6c78").grid(row=0, column=0, pady=10)
            return
        for index, record in enumerate(self._session_records):
            ctk.CTkButton(
                self.session_frame, text=f"{record.id[:8]} · {record.title[:26]}",
                anchor="w", height=34, corner_radius=10, fg_color="#222c38",
                hover_color="#2b3847", command=lambda i=index: self._resume_session(i),
            ).grid(row=index, column=0, padx=6, pady=3, sticky="ew")
        ctk.CTkButton(self.session_frame, text="删除选中", height=30, corner_radius=10,
                      fg_color="transparent", border_width=1, border_color="#3a4552",
                      command=self._delete_session_selected).grid(
            row=len(self._session_records), column=0, padx=6, pady=(8, 4), sticky="ew")

    def _resume_session(self, index: int) -> None:
        from .session_store import load_session, restore_harness

        record = self._session_records[index]
        payload = load_session(record.id)
        if payload is None:
            messagebox.showerror("恢复失败", "会话文件不可用。")
            return
        report = restore_harness(self.h, payload)
        self._append_chat("系统", report, "assistant")
        self._refresh_status()

    def _delete_session_selected(self) -> None:
        # CTk has no multi-select list; expose the newest session for deletion.
        if not self._session_records:
            return
        from .session_store import delete_session

        record = self._session_records[0]
        if messagebox.askyesno("删除会话", f"删除会话 {record.id[:8]}？此操作不可撤销。"):
            delete_session(record.id)
            self._refresh_sessions()

    # ------------------------------------------------------------ workspaces
    def _refresh_workspaces(self) -> None:
        from .workspace_store import list_workspaces

        for child in self.workspace_frame.winfo_children():
            child.destroy()
        self._workspace_records = list(list_workspaces())
        for index, workspace in enumerate(self._workspace_records):
            ctk.CTkButton(
                self.workspace_frame, text=str(workspace)[:40], anchor="w", height=32,
                corner_radius=10, fg_color="#222c38", hover_color="#2b3847",
                command=lambda i=index: self._switch_workspace(i),
            ).grid(row=index, column=0, padx=6, pady=3, sticky="ew")
        ctk.CTkButton(self.workspace_frame, text="选择其他目录", height=30, corner_radius=10,
                      fg_color="transparent", border_width=1, border_color="#3a4552",
                      command=self._choose_workspace).grid(
            row=max(len(self._workspace_records), 1), column=0, padx=6, pady=(8, 4), sticky="ew")

    def _switch_workspace(self, index: int) -> None:
        workspace = str(self._workspace_records[index])
        os.environ["WORKSPACE"] = workspace
        self.workspace_var.set(workspace)
        self.status.set(f"工作区已切换：{workspace}")

    def _choose_workspace(self) -> None:
        path = filedialog.askdirectory(title="选择工作区")
        if not path:
            return
        os.environ["WORKSPACE"] = path
        self.workspace_var.set(path)
        from .workspace_store import register_workspace
        try:
            register_workspace(path)
        except Exception:
            pass
        self._refresh_workspaces()

    # ------------------------------------------------------------ agent run
    def _on_stream_token(self, piece: str) -> None:
        self.events.put(("stream", piece))

    def _approve_command(self, command: str) -> str:
        decided = threading.Event()
        holder: dict = {"decision": "deny"}
        self.approvals.put((command, decided, holder))
        decided.wait(timeout=120)
        return holder["decision"]

    def _drain_approvals(self) -> None:
        try:
            while True:
                command, decided, holder = self.approvals.get_nowait()
                ok = messagebox.askyesno("权限确认", f"允许执行这条 Shell 命令？\n\n{command}")
                holder["decision"] = "allow" if ok else "deny"
                decided.set()
        except queue.Empty:
            pass
        self.root.after(120, self._drain_approvals)

    def _capture_runtime_event(self, event) -> None:
        self.events.put(("runtime", event))

    def _drain_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "result":
                    if self._streaming_started:
                        self._streaming_started = False
                        self._append(self.chat, str(payload) + "\n", "assistant")
                    else:
                        self._append_chat("小朴", str(payload), "assistant")
                    self._set_running(False)
                    self._refresh_status()
                elif kind == "error":
                    self._append_chat("错误", str(payload), "error")
                    self._set_running(False)
                    self._refresh_status()
                elif kind == "stream":
                    if not self._streaming_started:
                        self._append(self.chat, "小朴\n", "assistant")
                        self._streaming_started = True
                    self.chat.configure(state="normal")
                    self.chat.insert("end", str(payload), "assistant")
                    self.chat.see("end")
                    self.chat.configure(state="disabled")
                elif kind == "runtime":
                    self._show_event(payload)
        except queue.Empty:
            pass
        self.root.after(60, self._drain_events)

    def _show_event(self, event) -> None:
        if not self.process_visible:
            return
        p = event.payload
        if event.kind == EventKind.TURN_STARTED:
            self.live_action.set("正在分析任务并选择执行路线…")
            self.live_phase.set("阶段：intake")
            self._streaming_started = False
            self._refresh_status()
            return
        if event.kind == EventKind.CONTROLLER_DECISION:
            self.live_action.set(f"控制器决策：{p.get('action', 'planning')}")
            self.live_phase.set(f"阶段：{p.get('phase', '—')}")
            return
        if event.kind == EventKind.PLANNING_DECISION:
            line = f"计划 · {p.get('next_action', '')}\n依据 · {p.get('reason', '')}"
            self.live_action.set(str(p.get("next_action", "正在规划…")))
            self.live_phase.set(f"阶段：{p.get('stage', '—')}")
        elif event.kind == EventKind.GOAL_UPDATED:
            line = f"Goal · {p.get('status')} · {len(p.get('completed', []))}/{len(p.get('milestones', []))}"
        elif event.kind == EventKind.TOOL_STARTED:
            self.tool_started_count += 1
            self._refresh_counts()
            self.live_action.set(f"正在调用 {p.get('tool', '未知工具')}…")
            self.tool_log_lines.append(f"▸ {p.get('tool', '?')}  {p.get('arguments', '')[:120]}")
            self._append(self.tool_box, self.tool_log_lines[-1])
            return
        elif event.kind == EventKind.TOOL_COMPLETED:
            self.tool_completed_count += 1
            self._refresh_counts()
            self.live_action.set(f"{p.get('tool', '工具')} 已完成，正在处理结果…")
            self._append(self.tool_box, f"✓ {p.get('tool', '?')}")
            return
        elif event.kind == EventKind.TOOL_FAILED:
            self.tool_failed_count += 1
            self._refresh_counts()
            self.live_action.set(f"{p.get('tool', '工具')} 失败，正在调整路线…")
            self._append(self.tool_box, f"✕ {p.get('tool', '?')}: {str(p.get('error', ''))[:160]}")
            return
        elif event.kind == EventKind.MODEL_RESPONSE:
            chars = int(p.get("reasoning_chars", 0) or 0)
            self.live_action.set("模型已返回，正在执行工具…" if p.get("tool_call_count") else "正在检查完成条件…")
            self._append(self.signal_box, f"模型响应 · 推理信号 {chars} 字符 · 工具请求 {p.get('tool_call_count', 0)} 个")
            return
        elif event.kind == EventKind.PHASE_CHANGED:
            line = f"阶段 · {p.get('from_phase')} → {p.get('to_phase')}"
            self.live_phase.set(f"阶段：{p.get('to_phase', '—')}")
        else:
            return
        self._append(self.plan_box, line)

    def _set_running(self, value: bool) -> None:
        self.running = value
        self.send.configure(state="disabled" if value else "normal")
        self.stop.configure(state="normal" if value else "disabled")
        self.status.set("正在执行…" if value else "就绪")
        if value:
            self.started_at = time.monotonic()
            self.tool_started_count = self.tool_completed_count = self.tool_failed_count = 0
            self.live_action.set("正在提交任务给模型…")
            self.live_phase.set("阶段：intake")
            self._refresh_counts()
        else:
            self.started_at = None
            self.live_action.set("任务已结束，等待下一条指令")
        self._refresh_status()

    def _refresh_counts(self) -> None:
        self.live_counts.set(f"工具 {self.tool_started_count} · 完成 {self.tool_completed_count} · 失败 {self.tool_failed_count}")

    def _refresh_status(self) -> None:
        state = self.h.state
        fresh = len(state.fresh_evidence())
        self.status.set(
            f"{state.phase.value} · epoch {state.mutation_epoch} · 证据 {fresh} · "
            f"tokens {state.total_tokens} · repair {state.repair_attempts}/{state.max_repairs}"
        )

    def _tick_elapsed(self) -> None:
        if self.started_at is not None:
            elapsed = max(0, int(time.monotonic() - self.started_at))
            minutes, seconds = divmod(elapsed, 60)
            self.live_elapsed.set(f"{minutes}:{seconds:02d}" if minutes else f"{seconds} 秒")
        self.root.after(250, self._tick_elapsed)

    def _send(self) -> None:
        if self.running:
            return
        task = self.input.get("1.0", "end").strip()
        if not task:
            return
        self.input.delete("1.0", "end")
        self._append_chat("你", task, "user")
        self._set_running(True)

        def worker() -> None:
            try:
                self.events.put(("result", self.h.run(task)))
            except Exception as exc:
                self.events.put(("error", f"{type(exc).__name__}: {exc}"))
        threading.Thread(target=worker, daemon=True).start()

    def _cancel(self) -> None:
        self.h.request_cancel()
        self.status.set("正在安全中断…")

    def _start_goal(self) -> None:
        objective = self.goal_entry.get().strip()
        if objective:
            try:
                self._append_chat("Goal", self.h.start_goal(objective), "assistant")
            except Exception as exc:
                messagebox.showerror("Goal 启动失败", str(exc))

    def _show_goal(self) -> None:
        messagebox.showinfo("长期目标", self.h.goal_summary())

    def _new_session(self) -> None:
        if self.running:
            return
        from .session_store import save_session
        save_session(self.h)
        self.h.reset()
        self._append_chat("系统", "已保存当前会话并创建新会话。", "assistant")
        self._refresh_sessions()
        self._refresh_status()

    def _verify(self) -> None:
        try:
            result = dispatch("ppt_check", json.dumps({"policy": "auto"}), self.h)
            self._append_chat("验证", result, "assistant")
        except Exception as exc:
            messagebox.showerror("验证失败", str(exc))

    def _save_ppt(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".pptx", filetypes=[("PowerPoint", "*.pptx")])
        if path:
            try:
                result = dispatch("ppt_save", json.dumps({"path": path}), self.h)
                self._append_chat("保存", result, "assistant")
            except Exception as exc:
                messagebox.showerror("保存失败", str(exc))

    def _export_session(self) -> None:
        from .session_store import export_session, save_session

        record = save_session(self.h)
        path = filedialog.asksaveasfilename(defaultextension=".md", filetypes=[("Markdown", "*.md")])
        if not path:
            return
        try:
            exported = export_session(record.id, Path(path))
            self._append_chat("导出", f"会话已导出：{exported}", "assistant")
        except Exception as exc:
            messagebox.showerror("导出失败", str(exc))

    def _undo(self) -> None:
        self._append_chat("撤销", self.h.undo(), "assistant")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-gui", description="Launch the modern Xiaopu GUI")
    parser.add_argument("--workspace", type=str, default=None, help="working directory")
    parser.add_argument("--model", type=str, default=None, help="model override")
    return parser


def main() -> int:
    config.load_dotenv()
    args = build_parser().parse_args()
    if args.workspace:
        path = Path(args.workspace).expanduser().resolve()
        if not path.is_dir():
            print(f"WORKSPACE ERROR: directory does not exist: {path}")
            return 2
        os.environ["WORKSPACE"] = str(path)
    root = ctk.CTk()
    AgentGUI(root, model=args.model)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
