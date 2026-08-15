"""Modern CustomTkinter GUI for the complete Xiaopu Harness.

Layout follows current agent-app practice (chat-first, activity in a
collapsible right drawer, sessions in a slim left rail):
- left rail: sessions / workspace / footer
- center: message bubbles + sticky composer
- right drawer (default hidden): live timeline + raw provider reasoning

The harness runs on a worker thread and the UI only drains thread-safe
queues, so streaming, approvals and interruption work exactly like the CLI.
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
SIDEBAR = "#131920"
MAIN_BG = "#0c1117"
CARD_BG = "#151d26"
USER_BG = "#1f3d32"
ASSISTANT_BG = "#1a232e"
BORDER = "#242e3a"
TEXT = "#e7edf2"
MUTED = "#7f8c98"


class AgentGUI:
    def __init__(self, root: ctk.CTk, model: str | None = None) -> None:
        from .harness import Harness

        self.root = root
        self.model = model
        self.h = Harness(model=model, interactive=True)
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.approvals: queue.Queue = queue.Queue()
        self.running = False
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
        self._trajectory: list[str] = []
        self._reasoning_text = ""
        self._streaming_started = False
        self._stream_buffer = ""
        self._stream_bubble_label = None
        self._session_records = []
        self._workspace_records = []
        self.activity_visible = False
        self.h.approval_handler = self._approve_command
        self.h.stream_callback = self._on_stream_token
        self.h.reasoning_callback = self._on_reasoning
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

    # ------------------------------------------------------------------ layout
    def _build(self) -> None:
        self.root.title("小朴 Agent · Xiaopu")
        self.root.geometry("1360x860")
        self.root.minsize(980, 640)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.root.configure(fg_color=MAIN_BG)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        self._build_sidebar()
        self._build_main()

    def _build_sidebar(self) -> None:
        rail = ctk.CTkFrame(self.root, width=252, corner_radius=0, fg_color=SIDEBAR)
        rail.grid(row=0, column=0, sticky="nsew")
        rail.grid_propagate(False)
        rail.grid_columnconfigure(0, weight=1)
        rail.grid_rowconfigure(2, weight=1)

        brand = ctk.CTkFrame(rail, fg_color="transparent")
        brand.grid(row=0, column=0, padx=18, pady=(20, 12), sticky="ew")
        ctk.CTkLabel(brand, text="小朴", font=ctk.CTkFont("Microsoft YaHei UI", 25, "bold"),
                     text_color="#f0f7f2").pack(anchor="w")
        ctk.CTkLabel(brand, text="Xiaopu Agent", font=ctk.CTkFont("Microsoft YaHei UI", 11),
                     text_color=MUTED).pack(anchor="w")

        ctk.CTkButton(rail, text="＋ 新会话", height=36, corner_radius=11,
                      fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      command=self._new_session).grid(row=1, column=0, padx=16, pady=(0, 12), sticky="ew")

        self.session_frame = ctk.CTkScrollableFrame(rail, label_text="会话历史", corner_radius=13,
                                                    fg_color=CARD_BG, label_fg_color=MUTED)
        self.session_frame.grid(row=2, column=0, padx=16, pady=(0, 10), sticky="nsew")
        self.session_frame.grid_columnconfigure(0, weight=1)

        ws = ctk.CTkFrame(rail, fg_color="transparent")
        ws.grid(row=3, column=0, padx=16, pady=(0, 16), sticky="ew")
        ctk.CTkLabel(ws, text="工作区", font=ctk.CTkFont("Microsoft YaHei UI", 11, "bold"),
                     text_color=MUTED).pack(anchor="w", pady=(0, 4))
        self.workspace_menu = ctk.CTkOptionMenu(ws, values=[self.workspace_var.get()],
                                                command=self._switch_workspace_value,
                                                corner_radius=10, height=32,
                                                dynamic_resizing=False)
        self.workspace_menu.pack(fill="x")
        ctk.CTkButton(ws, text="选择其他目录…", height=30, corner_radius=9,
                      fg_color="transparent", border_width=1, border_color=BORDER,
                      hover_color=CARD_BG, command=self._choose_workspace).pack(fill="x", pady=(8, 0))

        ctk.CTkLabel(rail, text=f"{config.provider()} · v0.2.0", font=ctk.CTkFont("Microsoft YaHei UI", 10),
                     text_color="#5e6c78").grid(row=4, column=0, pady=(0, 14))

    def _build_main(self) -> None:
        main = ctk.CTkFrame(self.root, corner_radius=0, fg_color=MAIN_BG)
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        self._build_topbar(main)

        self.chat = ctk.CTkScrollableFrame(main, fg_color=MAIN_BG, corner_radius=0)
        self.chat.grid(row=1, column=0, sticky="nsew", padx=(18, 8), pady=(0, 8))
        self.chat.grid_columnconfigure(0, weight=1)

        self.activity = ctk.CTkFrame(main, width=430, corner_radius=16, fg_color="#10171f",
                                     border_width=1, border_color=BORDER)
        self.activity.grid_columnconfigure(0, weight=1)
        self.activity.grid_rowconfigure(1, weight=1)
        header = ctk.CTkFrame(self.activity, fg_color="transparent")
        header.grid(row=0, column=0, padx=14, pady=(12, 6), sticky="ew")
        ctk.CTkLabel(header, text="活动", font=ctk.CTkFont("Microsoft YaHei UI", 14, "bold")).pack(side="left")
        ctk.CTkButton(header, text="✕", width=30, height=26, corner_radius=8,
                      fg_color="transparent", border_width=1, border_color=BORDER,
                      hover_color=CARD_BG, text_color=MUTED,
                      command=self._toggle_activity).pack(side="right")
        self.activity_tabs = ctk.CTkTabview(self.activity, corner_radius=12,
                                            fg_color="#10171f", border_width=0)
        self.activity_tabs.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self.activity_tabs.add("时间线")
        self.activity_tabs.add("思维链")
        self.trajectory_box = self._readonly_box(self.activity_tabs.tab("时间线"))
        self.cot_box = self._readonly_box(self.activity_tabs.tab("思维链"))
        self._append(self.cot_box, "模型实际返回的 reasoning_content 会实时显示在这里。\nprovider 未返回时明确提示，绝不伪造。")

        self._build_composer(main)
        self._build_statusbar(main)

        self._append_chat("system", "已就绪。输入一句任务，或先启动长期 Goal。")

    def _build_topbar(self, main: ctk.CTkFrame) -> None:
        bar = ctk.CTkFrame(main, fg_color="transparent")
        bar.grid(row=0, column=0, padx=18, pady=(14, 8), sticky="ew")
        bar.grid_columnconfigure(0, weight=1)

        left = ctk.CTkFrame(bar, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(left, textvariable=self.live_action, font=ctk.CTkFont("Microsoft YaHei UI", 12, "bold")).pack(side="left")
        ctk.CTkLabel(left, textvariable=self.live_phase, text_color=MUTED).pack(side="left", padx=(10, 0))

        right = ctk.CTkFrame(bar, fg_color="transparent")
        right.grid(row=0, column=1, sticky="e")
        ctk.CTkLabel(right, text="模型").pack(side="left", padx=(0, 6))
        ctk.CTkOptionMenu(right, variable=self.model_var, values=config.known_models(),
                          command=self._switch_model, width=170, corner_radius=9, height=30).pack(side="left")
        ctk.CTkLabel(right, text="权限").pack(side="left", padx=(12, 6))
        ctk.CTkOptionMenu(right, variable=self.permissions_var, values=("allow", "ask", "deny"),
                          command=self._switch_permissions, width=76, corner_radius=9, height=30).pack(side="left")
        self.activity_btn = ctk.CTkButton(right, text="活动", width=58, height=30, corner_radius=9,
                                          fg_color=CARD_BG, border_width=1, border_color=BORDER,
                                          hover_color="#1d2834", command=self._toggle_activity)
        self.activity_btn.pack(side="left", padx=(12, 0))
        ctk.CTkButton(right, text="验证", width=54, height=30, corner_radius=9,
                      command=self._verify).pack(side="left", padx=8)
        ctk.CTkButton(right, text="保存 PPT", width=72, height=30, corner_radius=9,
                      command=self._save_ppt).pack(side="left", padx=(0, 8))
        ctk.CTkButton(right, text="导出", width=54, height=30, corner_radius=9,
                      command=self._export_session).pack(side="left", padx=(0, 8))
        ctk.CTkButton(right, text="撤销", width=54, height=30, corner_radius=9,
                      command=self._undo).pack(side="left")

        live = ctk.CTkFrame(main, corner_radius=12, fg_color="#111822")
        live.grid(row=0, column=0, padx=18, pady=(56, 6), sticky="ew")
        ctk.CTkLabel(live, text="●", text_color="#52c98c", font=ctk.CTkFont("Microsoft YaHei UI", 14)).pack(side="left", padx=(12, 6))
        ctk.CTkLabel(live, textvariable=self.live_counts, text_color=MUTED).pack(side="left")
        ctk.CTkLabel(live, textvariable=self.live_elapsed, text_color=MUTED).pack(side="right", padx=12)

    def _build_composer(self, main: ctk.CTkFrame) -> None:
        goal = ctk.CTkFrame(main, fg_color="transparent")
        goal.grid(row=2, column=0, padx=18, pady=(0, 6), sticky="ew")
        goal.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(goal, text="长期目标", font=ctk.CTkFont("Microsoft YaHei UI", 11, "bold")).grid(row=0, column=0, padx=(0, 8))
        self.goal_entry = ctk.CTkEntry(goal, placeholder_text="可留空；输入目标后点击启动",
                                       corner_radius=10, height=32, fg_color="#111822", border_color=BORDER)
        self.goal_entry.grid(row=0, column=1, sticky="ew")
        ctk.CTkButton(goal, text="启动", width=62, height=32, corner_radius=9,
                      command=self._start_goal).grid(row=0, column=2, padx=8)
        ctk.CTkButton(goal, text="查看", width=62, height=32, corner_radius=9,
                      command=self._show_goal).grid(row=0, column=3)

        composer = ctk.CTkFrame(main, corner_radius=16, fg_color="#111822", border_width=1, border_color=BORDER)
        composer.grid(row=3, column=0, padx=18, pady=(0, 10), sticky="ew")
        composer.grid_columnconfigure(0, weight=1)
        self.input = ctk.CTkTextbox(composer, height=76, wrap="word", corner_radius=12,
                                    fg_color="#0e141b", border_width=0,
                                    font=ctk.CTkFont("Microsoft YaHei UI", 13))
        self.input.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        self.input.bind("<Control-Return>", lambda _e: self._send() or "break")
        buttons = ctk.CTkFrame(composer, fg_color="transparent")
        buttons.grid(row=0, column=1, padx=(0, 10), pady=10)
        self.send = ctk.CTkButton(buttons, text="发送", width=88, height=34, corner_radius=10,
                                  fg_color=ACCENT, hover_color=ACCENT_HOVER, command=self._send)
        self.send.pack()
        self.stop = ctk.CTkButton(buttons, text="中断", width=88, height=34, corner_radius=10,
                                  fg_color="#a13c3c", hover_color="#7d2f2f",
                                  command=self._cancel, state="disabled")
        self.stop.pack(pady=(8, 0))

    def _build_statusbar(self, main: ctk.CTkFrame) -> None:
        bar = ctk.CTkFrame(main, corner_radius=0, fg_color="#0a0f14", height=28)
        bar.grid(row=4, column=0, sticky="ew")
        ctk.CTkLabel(bar, textvariable=self.status, text_color=MUTED,
                     font=ctk.CTkFont("Microsoft YaHei UI", 10)).pack(side="left", padx=16)
        ctk.CTkLabel(bar, text="Ctrl+Enter 发送 · Esc 中断 · 活动面板可收起",
                     text_color="#5e6c78", font=ctk.CTkFont("Microsoft YaHei UI", 10)).pack(side="right", padx=16)

    # ------------------------------------------------------------------ chat
    def _readonly_box(self, parent) -> ctk.CTkTextbox:
        box = ctk.CTkTextbox(parent, wrap="word", corner_radius=0, fg_color="#0d141b",
                             border_width=0, font=ctk.CTkFont("Consolas", 11))
        box.pack(fill="both", expand=True, padx=8, pady=8)
        self._make_readonly_selectable(box)
        return box

    def _append(self, widget: ctk.CTkTextbox, text: str, tag: str | None = None) -> None:
        widget.configure(state="normal")
        widget.insert("end", text + "\n", tag)
        widget.see("end")
        widget.configure(state="disabled")

    @staticmethod
    def _make_readonly_selectable(widget) -> None:
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

    def _append_chat(self, role: str, text: str) -> None:
        """Append a rounded message bubble to the scrollable chat surface."""
        is_user = role == "you" or role == "你"
        is_system = role in {"system", "系统", "撤销", "验证", "保存", "导出", "Goal"}
        bubble_bg = USER_BG if is_user else (CARD_BG if is_system else ASSISTANT_BG)
        bubble_fg = "#d9f2e5" if is_user else TEXT
        label = "你" if is_user else role

        row = ctk.CTkFrame(self.chat, fg_color="transparent")
        row.grid(sticky="e" if is_user else "w", padx=6, pady=5)
        row.grid_columnconfigure(0, weight=1)
        row.grid_columnconfigure(1, weight=1)

        card = ctk.CTkFrame(row, corner_radius=14, fg_color=bubble_bg,
                            border_width=1, border_color=BORDER)
        card.grid(row=0, column=1 if is_user else 0, sticky="e" if is_user else "w")
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(card, text=label, font=ctk.CTkFont("Microsoft YaHei UI", 10, "bold"),
                     text_color="#8fb5a2" if is_user else "#8fa4b5").grid(row=0, column=0, padx=14, pady=(10, 0), sticky="w")
        body = ctk.CTkLabel(card, text=text, justify="left", anchor="w",
                            wraplength=640, font=ctk.CTkFont("Microsoft YaHei UI", 13),
                            text_color=bubble_fg)
        body.grid(row=1, column=0, padx=14, pady=(4, 12), sticky="w")
        ctk.CTkButton(card, text="复制", width=42, height=24, corner_radius=7,
                      fg_color="transparent", border_width=1, border_color=BORDER,
                      hover_color="#263342", text_color=MUTED,
                      font=ctk.CTkFont("Microsoft YaHei UI", 9),
                      command=lambda t=text: self._copy_text(t)).grid(row=0, column=1, padx=(8, 10), pady=(8, 0), sticky="e")
        self.chat._parent_canvas.yview_moveto(1.0)
        if role in {"小朴", "you", "你"}:
            self._last_chat_label = body

    def _copy_text(self, text: str) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status.set("已复制到剪贴板")

    # ------------------------------------------------------------------ model
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

    def _toggle_activity(self) -> None:
        if self.activity_visible:
            self.activity.grid_forget()
            self.activity_visible = False
            self.chat.grid(padx=(18, 8))
        else:
            self.activity.grid(row=1, column=1, sticky="nsew", padx=(0, 18), pady=(0, 8))
            self.activity_visible = True
            self.chat.grid(padx=(18, 8))

    # ------------------------------------------------------------------ runs
    def _on_stream_token(self, piece: str) -> None:
        self.events.put(("stream", piece))

    def _on_reasoning(self, piece: str) -> None:
        self.events.put(("reasoning", piece))

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
                    self._finish_stream(str(payload))
                    self._set_running(False)
                    self._refresh_status()
                elif kind == "error":
                    self._finish_stream("")
                    self._append_chat("错误", str(payload))
                    self._set_running(False)
                    self._refresh_status()
                elif kind == "stream":
                    self._on_stream_piece(str(payload))
                elif kind == "reasoning":
                    self._reasoning_text += str(payload)
                    self._append(self.cot_box, str(payload))
                elif kind == "runtime":
                    self._show_event(payload)
        except queue.Empty:
            pass
        self.root.after(60, self._drain_events)

    def _on_stream_piece(self, piece: str) -> None:
        self._stream_buffer += piece
        if not self._streaming_started:
            self._streaming_started = True
            self._append_chat("小朴", "")
            self._stream_bubble_label = self._last_chat_label
        if self._stream_bubble_label is not None:
            self._stream_bubble_label.configure(text=self._stream_buffer)

    def _finish_stream(self, reply: str) -> None:
        if self._streaming_started:
            if reply and reply.strip() != self._stream_buffer.strip():
                if self._stream_bubble_label is not None:
                    self._stream_bubble_label.configure(text=reply)
            self._streaming_started = False
            self._stream_buffer = ""
            self._stream_bubble_label = None
            return
        if reply:
            self._append_chat("小朴", reply)

    def _show_event(self, event) -> None:
        if not self.activity_visible:
            return
        p = event.payload
        if event.kind == EventKind.TURN_STARTED:
            self.live_action.set("正在分析任务并选择执行路线…")
            self.live_phase.set("阶段：intake")
            self._reasoning_text = ""
            self._trajectory = []
            self._refresh_status()
            return
        if event.kind == EventKind.CONTROLLER_DECISION:
            self.live_action.set(f"控制器决策：{p.get('action', 'planning')}")
            self.live_phase.set(f"阶段：{p.get('phase', '—')}")
            line = f"控制器决策 · {p.get('action')} · {p.get('reason', '')}"
            self._trajectory.append(line)
            self._append(self.trajectory_box, line)
            return
        if event.kind == EventKind.PLANNING_DECISION:
            line = f"计划 · {p.get('next_action', '')}\n依据 · {p.get('reason', '')}"
            self._trajectory.append(line)
            self._append(self.trajectory_box, line)
            self.live_action.set(str(p.get("next_action", "正在规划…")))
            self.live_phase.set(f"阶段：{p.get('stage', '—')}")
            return
        if event.kind == EventKind.TOOL_STARTED:
            self.tool_started_count += 1
            self._refresh_counts()
            self.live_action.set(f"正在调用 {p.get('tool', '未知工具')}…")
            line = f"▸ {p.get('tool', '?')}  {p.get('arguments', '')[:240]}"
            self.tool_log_lines.append(line)
            self._trajectory.append(line)
            self._append(self.trajectory_box, line)
            return
        if event.kind == EventKind.TOOL_COMPLETED:
            self.tool_completed_count += 1
            self._refresh_counts()
            self.live_action.set(f"{p.get('tool', '工具')} 已完成，正在处理结果…")
            line = f"✓ {p.get('tool', '?')}\n结果：{str(p.get('output', ''))[:800]}"
            self._trajectory.append(line)
            self._append(self.trajectory_box, line)
            return
        if event.kind == EventKind.TOOL_FAILED:
            self.tool_failed_count += 1
            self._refresh_counts()
            self.live_action.set(f"{p.get('tool', '工具')} 失败，正在调整路线…")
            line = f"✕ {p.get('tool', '?')}: {str(p.get('error', ''))[:320]}"
            self._trajectory.append(line)
            self._append(self.trajectory_box, line)
            return
        if event.kind == EventKind.MODEL_RESPONSE:
            reasoning = str(p.get("reasoning_content") or self._reasoning_text or "")
            if reasoning.strip():
                self._append(self.cot_box, "\n── 模型响应 ──\n" + reasoning + "\n")
                self._trajectory.append("原始思维链：\n" + reasoning)
                self._append(self.trajectory_box, "原始思维链：\n" + reasoning)
            else:
                self._append(self.cot_box, "\n本次响应 provider 未返回原始思维链。\n")
            self.live_action.set("模型已返回，正在执行工具…" if p.get("tool_call_count") else "正在检查完成条件…")
            return
        if event.kind == EventKind.PHASE_CHANGED:
            line = f"阶段 · {p.get('from_phase')} → {p.get('to_phase')}"
            self._trajectory.append(line)
            self._append(self.trajectory_box, line)
            self.live_phase.set(f"阶段：{p.get('to_phase', '—')}")
            return

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
        self._append_chat("you", task)
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

    # ------------------------------------------------------------------ commands
    def _start_goal(self) -> None:
        objective = self.goal_entry.get().strip()
        if objective:
            try:
                self._append_chat("Goal", self.h.start_goal(objective))
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
        self._append_chat("system", "已保存当前会话并创建新会话。")
        self._refresh_sessions()
        self._refresh_status()

    def _verify(self) -> None:
        try:
            result = dispatch("ppt_check", json.dumps({"policy": "auto"}), self.h)
            self._append_chat("验证", result)
        except Exception as exc:
            messagebox.showerror("验证失败", str(exc))

    def _save_ppt(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".pptx", filetypes=[("PowerPoint", "*.pptx")])
        if path:
            try:
                result = dispatch("ppt_save", json.dumps({"path": path}), self.h)
                self._append_chat("保存", result)
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
            self._append_chat("导出", f"会话已导出：{exported}")
        except Exception as exc:
            messagebox.showerror("导出失败", str(exc))

    def _undo(self) -> None:
        self._append_chat("撤销", self.h.undo())

    # ------------------------------------------------------------------ sidebar data
    def _refresh_sessions(self) -> None:
        from .session_store import list_sessions

        for child in self.session_frame.winfo_children():
            child.destroy()
        self._session_records = list_sessions()
        if not self._session_records:
            ctk.CTkLabel(self.session_frame, text="暂无保存的会话", text_color="#5e6c78").grid(row=0, column=0, pady=10)
            return
        for index, record in enumerate(self._session_records[:40]):
            frame = ctk.CTkFrame(self.session_frame, corner_radius=10, fg_color="#1c2632")
            frame.grid(row=index, column=0, padx=6, pady=3, sticky="ew")
            frame.grid_columnconfigure(0, weight=1)
            ctk.CTkButton(frame, text=f"{record.id[:8]} · {record.title[:24]}", anchor="w",
                          height=30, corner_radius=8, fg_color="transparent", hover_color="#263342",
                          command=lambda i=index: self._resume_session(i)).grid(row=0, column=0, sticky="ew", padx=2, pady=2)
            ctk.CTkButton(frame, text="✕", width=26, height=26, corner_radius=7,
                          fg_color="transparent", hover_color="#4a3038", text_color="#c98787",
                          command=lambda i=index: self._delete_session(i)).grid(row=0, column=1, padx=4)

    def _resume_session(self, index: int) -> None:
        from .session_store import load_session, restore_harness

        record = self._session_records[index]
        payload = load_session(record.id)
        if payload is None:
            messagebox.showerror("恢复失败", "会话文件不可用。")
            return
        report = restore_harness(self.h, payload)
        self._append_chat("system", report)
        self._refresh_status()

    def _delete_session(self, index: int) -> None:
        from .session_store import delete_session

        record = self._session_records[index]
        if messagebox.askyesno("删除会话", f"删除会话 {record.id[:8]}？此操作不可撤销。"):
            delete_session(record.id)
            self._refresh_sessions()

    def _refresh_workspaces(self) -> None:
        from .workspace_store import list_workspaces

        values = [str(w) for w in list_workspaces()]
        if self.workspace_var.get() not in values:
            values.insert(0, self.workspace_var.get())
        self._workspace_records = values
        self.workspace_menu.configure(values=values)
        self.workspace_menu.set(self.workspace_var.get())

    def _switch_workspace_value(self, value: str) -> None:
        os.environ["WORKSPACE"] = value
        self.workspace_var.set(value)
        self.status.set(f"工作区已切换：{value}")

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
