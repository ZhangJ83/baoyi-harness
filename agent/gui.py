"""Modern CustomTkinter GUI for the complete Xiaopu Harness.

Layout follows current agent-app practice (ChatGPT / Claude / Cursor / Codex inspired):
- Left sidebar: Xiaopu brand, "+ New Session", session history list with delete, workspace selector;
- Center panel: Topbar (live state, model & permission selector, PPT tools, activity toggle),
  live metric strip, scrollable modern chat stream (user & assistant bubbles with copy),
  goal launcher strip, rounded composer with shortcuts (Ctrl+Enter to send, Esc to cancel);
- Right activity drawer (collapsible): Streamlined 2-tab layout (Timeline + Raw Provider CoT)
  with copy buttons, auto-scroll, and genuine reasoning signals (never synthesized).

The harness runs on a worker thread and the UI only drains thread-safe
queues, so streaming, approvals and interruption work cleanly and smoothly.
"""
from __future__ import annotations

import argparse
import json
import os
import queue
import sys
import threading
import time
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from . import config
from .events import EventKind, RuntimeEvent
from .tools.registry import dispatch

# Modern Slate + Emerald Design System
ACCENT = "#10b981"
ACCENT_HOVER = "#059669"
ACCENT_ACTIVE = "#047857"
DANGER = "#ef4444"
DANGER_HOVER = "#dc2626"
WARNING = "#f59e0b"

BG_ROOT = "#0b0f14"
SIDEBAR_BG = "#111720"
CARD_BG = "#161f2b"
CARD_HOVER = "#1c2736"
USER_BG = "#13382b"
USER_TEXT = "#ecfdf5"
ASSISTANT_BG = "#16202c"
ASSISTANT_TEXT = "#f1f5f9"
SYSTEM_BG = "#141c26"
BORDER = "#222d3a"
BORDER_LIGHT = "#2d3b4c"

TEXT_PRIMARY = "#f8fafc"
TEXT_SECONDARY = "#94a3b8"
TEXT_MUTED = "#64748b"


def _force_utf8_stdio() -> None:
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


class AgentGUI:
    def __init__(self, root: ctk.CTk, model: str | None = None) -> None:
        from .harness import Harness

        self.root = root
        self.model = model
        self.h = Harness(model=model, interactive=True)
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.approvals: queue.Queue = queue.Queue()
        self.running = False

        # Reactive string variables for UI bindings
        self.status = ctk.StringVar(value="就绪")
        self.live_action = ctk.StringVar(value="等待任务输入")
        self.live_phase = ctk.StringVar(value="阶段：就绪")
        self.live_elapsed = ctk.StringVar(value="0 秒")
        self.live_counts = ctk.StringVar(value="工具 0 · 完成 0 · 失败 0")
        self.model_var = ctk.StringVar(value=getattr(self.h.llm, "model", config.model()))
        self.permissions_var = ctk.StringVar(value=config.command_policy())
        self.workspace_var = ctk.StringVar(value=str(config.sandbox_root()))

        self.started_at: float | None = None
        self.tool_started_count = 0
        self.tool_completed_count = 0
        self.tool_failed_count = 0
        self.tool_log_lines: list[str] = []
        self._trajectory: list[str] = []
        self._reasoning_text = ""
        self._streaming_started = False
        self._stream_buffer = ""
        self._stream_bubble_label = None
        self._last_chat_label = None
        self._session_records: list = []
        self._workspace_records: list = []
        self.activity_visible = False

        # Harness event bindings
        self.h.approval_handler = self._approve_command
        self.h.stream_callback = self._on_stream_token
        self.h.reasoning_callback = self._on_reasoning
        self.h.subscribe(self._capture_runtime_event)

        # Build UI layout
        self._build()

        from .workspace_store import register_workspace
        try:
            register_workspace(self.workspace_var.get())
        except Exception:
            pass

        self._refresh_sessions()
        self._refresh_workspaces()

        # UI event loops
        self.root.after(50, self._drain_events)
        self.root.after(100, self._drain_approvals)
        self.root.after(250, self._tick_elapsed)
        self._refresh_status()

    # ------------------------------------------------------------------ Layout
    def _build(self) -> None:
        self.root.title("小朴 Agent · Xiaopu (Coding & PowerPoint Agent)")
        self.root.geometry("1400x880")
        self.root.minsize(1020, 660)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.root.configure(fg_color=BG_ROOT)

        self.root.grid_columnconfigure(0, weight=0)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main()

    def _build_sidebar(self) -> None:
        rail = ctk.CTkFrame(self.root, width=260, corner_radius=0, fg_color=SIDEBAR_BG,
                            border_width=1, border_color=BORDER)
        rail.grid(row=0, column=0, sticky="nsew")
        rail.grid_propagate(False)
        rail.grid_columnconfigure(0, weight=1)
        rail.grid_rowconfigure(2, weight=1)

        # Brand / Logo
        brand = ctk.CTkFrame(rail, fg_color="transparent")
        brand.grid(row=0, column=0, padx=16, pady=(18, 12), sticky="ew")
        title_row = ctk.CTkFrame(brand, fg_color="transparent")
        title_row.pack(fill="x")
        ctk.CTkLabel(title_row, text="小朴", font=ctk.CTkFont("Microsoft YaHei UI", 24, "bold"),
                     text_color=TEXT_PRIMARY).pack(side="left")
        ctk.CTkLabel(title_row, text="●", font=ctk.CTkFont("Microsoft YaHei UI", 12),
                     text_color=ACCENT).pack(side="left", padx=(6, 0), pady=(4, 0))
        ctk.CTkLabel(title_row, text="v0.2.0", font=ctk.CTkFont("Microsoft YaHei UI", 10, "bold"),
                     text_color=TEXT_MUTED).pack(side="left", padx=(6, 0), pady=(4, 0))
        ctk.CTkLabel(brand, text="智能代码与演示文稿助手", font=ctk.CTkFont("Microsoft YaHei UI", 11),
                     text_color=TEXT_SECONDARY).pack(anchor="w", pady=(2, 0))

        # + New Session button
        ctk.CTkButton(
            rail, text="＋ 新建会话", height=38, corner_radius=10,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            font=ctk.CTkFont("Microsoft YaHei UI", 13, "bold"),
            text_color="#ffffff",
            command=self._new_session,
        ).grid(row=1, column=0, padx=14, pady=(0, 12), sticky="ew")

        # Session History List
        self.session_frame = ctk.CTkScrollableFrame(
            rail, label_text="历史会话", corner_radius=12,
            fg_color=BG_ROOT, label_fg_color="transparent",
            label_text_color=TEXT_SECONDARY,
            border_width=1, border_color=BORDER,
        )
        self.session_frame.grid(row=2, column=0, padx=14, pady=(0, 10), sticky="nsew")
        self.session_frame.grid_columnconfigure(0, weight=1)

        # Workspace selector
        ws = ctk.CTkFrame(rail, fg_color="transparent")
        ws.grid(row=3, column=0, padx=14, pady=(0, 14), sticky="ew")
        ws_header = ctk.CTkFrame(ws, fg_color="transparent")
        ws_header.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(ws_header, text="当前工作区", font=ctk.CTkFont("Microsoft YaHei UI", 11, "bold"),
                     text_color=TEXT_SECONDARY).pack(side="left")

        self.workspace_menu = ctk.CTkOptionMenu(
            ws, values=[self.workspace_var.get()],
            command=self._switch_workspace_value,
            corner_radius=8, height=30,
            fg_color=CARD_BG, button_color=BORDER_LIGHT,
            button_hover_color=CARD_HOVER,
            text_color=TEXT_PRIMARY,
            dynamic_resizing=False,
        )
        self.workspace_menu.pack(fill="x")

        ctk.CTkButton(
            ws, text="📁 选择其他目录…", height=28, corner_radius=8,
            fg_color="transparent", border_width=1, border_color=BORDER,
            hover_color=CARD_HOVER, text_color=TEXT_SECONDARY,
            font=ctk.CTkFont("Microsoft YaHei UI", 11),
            command=self._choose_workspace,
        ).pack(fill="x", pady=(6, 0))

        # Bottom Provider indicator
        footer = ctk.CTkFrame(rail, fg_color="transparent")
        footer.grid(row=4, column=0, padx=14, pady=(0, 14), sticky="ew")
        ctk.CTkLabel(
            footer, text=f"Provider: {config.provider()} · Ready",
            font=ctk.CTkFont("Microsoft YaHei UI", 10),
            text_color=TEXT_MUTED,
        ).pack(anchor="w")

    def _build_main(self) -> None:
        main = ctk.CTkFrame(self.root, corner_radius=0, fg_color=BG_ROOT)
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_columnconfigure(1, weight=0)
        main.grid_rowconfigure(2, weight=1)

        self._build_topbar(main)
        self._build_metric_strip(main)

        # Center Chat Area
        self.chat = ctk.CTkScrollableFrame(main, fg_color=BG_ROOT, corner_radius=0)
        self.chat.grid(row=2, column=0, sticky="nsew", padx=(16, 8), pady=(0, 6))
        self.chat.grid_columnconfigure(0, weight=1)

        # Collapsible Activity Drawer (Right Column)
        self._build_activity_drawer(main)

        # Bottom Composer & Statusbar
        self._build_composer(main)
        self._build_statusbar(main)

        self._append_chat("system", "小朴已就绪。输入任务描述开始执行，或在上方启动长期 Goal。")

    def _build_topbar(self, main: ctk.CTkFrame) -> None:
        bar = ctk.CTkFrame(main, fg_color="transparent")
        bar.grid(row=0, column=0, columnspan=2, padx=16, pady=(12, 4), sticky="ew")
        bar.grid_columnconfigure(0, weight=1)

        # Left status badge & phase
        left = ctk.CTkFrame(bar, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w")
        self.status_dot = ctk.CTkLabel(
            left, text="●", text_color=ACCENT, font=ctk.CTkFont("Microsoft YaHei UI", 13, "bold"),
        )
        self.status_dot.pack(side="left", padx=(0, 4))
        ctk.CTkLabel(
            left, textvariable=self.live_action,
            font=ctk.CTkFont("Microsoft YaHei UI", 12, "bold"), text_color=TEXT_PRIMARY,
        ).pack(side="left")
        ctk.CTkLabel(
            left, textvariable=self.live_phase,
            font=ctk.CTkFont("Microsoft YaHei UI", 11), text_color=TEXT_SECONDARY,
        ).pack(side="left", padx=(10, 0))

        # Right Action Toolbar
        right = ctk.CTkFrame(bar, fg_color="transparent")
        right.grid(row=0, column=1, sticky="e")

        ctk.CTkLabel(right, text="模型", text_color=TEXT_SECONDARY, font=ctk.CTkFont("Microsoft YaHei UI", 11)).pack(side="left", padx=(0, 4))
        ctk.CTkOptionMenu(
            right, variable=self.model_var, values=config.known_models(),
            command=self._switch_model, width=160, corner_radius=8, height=28,
            fg_color=CARD_BG, button_color=BORDER_LIGHT, button_hover_color=CARD_HOVER,
            text_color=TEXT_PRIMARY, font=ctk.CTkFont("Microsoft YaHei UI", 11),
        ).pack(side="left")

        ctk.CTkLabel(right, text="权限", text_color=TEXT_SECONDARY, font=ctk.CTkFont("Microsoft YaHei UI", 11)).pack(side="left", padx=(10, 4))
        ctk.CTkOptionMenu(
            right, variable=self.permissions_var, values=("allow", "ask", "deny"),
            command=self._switch_permissions, width=76, corner_radius=8, height=28,
            fg_color=CARD_BG, button_color=BORDER_LIGHT, button_hover_color=CARD_HOVER,
            text_color=TEXT_PRIMARY, font=ctk.CTkFont("Microsoft YaHei UI", 11),
        ).pack(side="left")

        self.activity_btn = ctk.CTkButton(
            right, text="⚡ 活动", width=62, height=28, corner_radius=8,
            fg_color=CARD_BG, border_width=1, border_color=BORDER,
            hover_color=CARD_HOVER, text_color=TEXT_PRIMARY,
            font=ctk.CTkFont("Microsoft YaHei UI", 11, "bold"),
            command=self._toggle_activity,
        )
        self.activity_btn.pack(side="left", padx=(10, 0))

        ctk.CTkButton(
            right, text="🔍 验证", width=58, height=28, corner_radius=8,
            fg_color=CARD_BG, border_width=1, border_color=BORDER,
            hover_color=CARD_HOVER, text_color=TEXT_PRIMARY,
            font=ctk.CTkFont("Microsoft YaHei UI", 11),
            command=self._verify,
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            right, text="💾 保存 PPT", width=74, height=28, corner_radius=8,
            fg_color=CARD_BG, border_width=1, border_color=BORDER,
            hover_color=CARD_HOVER, text_color=TEXT_PRIMARY,
            font=ctk.CTkFont("Microsoft YaHei UI", 11),
            command=self._save_ppt,
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            right, text="📤 导出", width=56, height=28, corner_radius=8,
            fg_color=CARD_BG, border_width=1, border_color=BORDER,
            hover_color=CARD_HOVER, text_color=TEXT_PRIMARY,
            font=ctk.CTkFont("Microsoft YaHei UI", 11),
            command=self._export_session,
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            right, text="↩ 撤销", width=56, height=28, corner_radius=8,
            fg_color=CARD_BG, border_width=1, border_color=BORDER,
            hover_color=CARD_HOVER, text_color=TEXT_PRIMARY,
            font=ctk.CTkFont("Microsoft YaHei UI", 11),
            command=self._undo,
        ).pack(side="left")

    def _build_metric_strip(self, main: ctk.CTkFrame) -> None:
        strip = ctk.CTkFrame(main, corner_radius=10, fg_color=CARD_BG,
                             border_width=1, border_color=BORDER, height=32)
        strip.grid(row=1, column=0, columnspan=2, padx=16, pady=(0, 8), sticky="ew")
        strip.grid_propagate(False)

        left = ctk.CTkFrame(strip, fg_color="transparent")
        left.pack(side="left", fill="y", padx=10)
        ctk.CTkLabel(
            left, text="📊", font=ctk.CTkFont("Microsoft YaHei UI", 11),
        ).pack(side="left", padx=(0, 6))
        ctk.CTkLabel(
            left, textvariable=self.live_counts, font=ctk.CTkFont("Microsoft YaHei UI", 11),
            text_color=TEXT_SECONDARY,
        ).pack(side="left")

        right = ctk.CTkFrame(strip, fg_color="transparent")
        right.pack(side="right", fill="y", padx=10)
        ctk.CTkLabel(
            right, text="⏱ 耗时:", font=ctk.CTkFont("Microsoft YaHei UI", 11),
            text_color=TEXT_MUTED,
        ).pack(side="left", padx=(0, 4))
        ctk.CTkLabel(
            right, textvariable=self.live_elapsed, font=ctk.CTkFont("Microsoft YaHei UI", 11, "bold"),
            text_color=ACCENT,
        ).pack(side="left")

    def _build_activity_drawer(self, main: ctk.CTkFrame) -> None:
        self.activity = ctk.CTkFrame(
            main, width=420, corner_radius=14, fg_color=SIDEBAR_BG,
            border_width=1, border_color=BORDER,
        )
        self.activity.grid_columnconfigure(0, weight=1)
        self.activity.grid_rowconfigure(1, weight=1)

        # Drawer Header
        header = ctk.CTkFrame(self.activity, fg_color="transparent")
        header.grid(row=0, column=0, padx=14, pady=(12, 6), sticky="ew")
        ctk.CTkLabel(
            header, text="⚡ 活动监视器", font=ctk.CTkFont("Microsoft YaHei UI", 13, "bold"),
            text_color=TEXT_PRIMARY,
        ).pack(side="left")

        ctk.CTkButton(
            header, text="✕", width=28, height=26, corner_radius=6,
            fg_color="transparent", border_width=1, border_color=BORDER,
            hover_color=CARD_BG, text_color=TEXT_SECONDARY,
            font=ctk.CTkFont("Microsoft YaHei UI", 11, "bold"),
            command=self._toggle_activity,
        ).pack(side="right")

        # 2 high-value tabs: 时间线 + 思维链
        self.activity_tabs = ctk.CTkTabview(
            self.activity, corner_radius=10,
            fg_color=CARD_BG, segmented_button_fg_color=BG_ROOT,
            segmented_button_selected_color=ACCENT,
            segmented_button_selected_hover_color=ACCENT_HOVER,
            text_color=TEXT_PRIMARY,
        )
        self.activity_tabs.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self.activity_tabs.add("时间线")
        self.activity_tabs.add("思维链")

        # Tab 1: Timeline
        timeline_tab = self.activity_tabs.tab("时间线")
        t_head = ctk.CTkFrame(timeline_tab, fg_color="transparent")
        t_head.pack(fill="x", padx=4, pady=(2, 4))
        ctk.CTkLabel(
            t_head, text="决策 / 工具 / 阶段流转", font=ctk.CTkFont("Microsoft YaHei UI", 10),
            text_color=TEXT_MUTED,
        ).pack(side="left")
        ctk.CTkButton(
            t_head, text="复制时间线", width=70, height=22, corner_radius=6,
            fg_color=BG_ROOT, border_width=1, border_color=BORDER,
            hover_color=CARD_HOVER, text_color=TEXT_SECONDARY,
            font=ctk.CTkFont("Microsoft YaHei UI", 9),
            command=self._copy_timeline,
        ).pack(side="right")

        self.trajectory_box = self._readonly_box(timeline_tab)

        # Tab 2: Reasoning (CoT)
        cot_tab = self.activity_tabs.tab("思维链")
        c_head = ctk.CTkFrame(cot_tab, fg_color="transparent")
        c_head.pack(fill="x", padx=4, pady=(2, 4))
        ctk.CTkLabel(
            c_head, text="模型原始 reasoning_content（绝不伪造）",
            font=ctk.CTkFont("Microsoft YaHei UI", 10),
            text_color=TEXT_MUTED,
        ).pack(side="left")
        ctk.CTkButton(
            c_head, text="复制思维链", width=70, height=22, corner_radius=6,
            fg_color=BG_ROOT, border_width=1, border_color=BORDER,
            hover_color=CARD_HOVER, text_color=TEXT_SECONDARY,
            font=ctk.CTkFont("Microsoft YaHei UI", 9),
            command=self._copy_cot,
        ).pack(side="right")

        self.cot_box = self._readonly_box(cot_tab)
        self._append(self.cot_box, "模型实际返回的 reasoning_content 会实时显示在这里。\nprovider 未返回时明确提示，绝不伪造。")

    def _build_composer(self, main: ctk.CTkFrame) -> None:
        # Long-term Goal Strip
        goal = ctk.CTkFrame(main, fg_color="transparent")
        goal.grid(row=3, column=0, columnspan=2, padx=16, pady=(0, 6), sticky="ew")
        goal.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            goal, text="🎯 长期目标", font=ctk.CTkFont("Microsoft YaHei UI", 11, "bold"),
            text_color=TEXT_SECONDARY,
        ).grid(row=0, column=0, padx=(0, 8))

        self.goal_entry = ctk.CTkEntry(
            goal, placeholder_text="可选：输入长期目标后点击启动（支持断点续跑）",
            corner_radius=8, height=30, fg_color=CARD_BG,
            border_color=BORDER, text_color=TEXT_PRIMARY,
            placeholder_text_color=TEXT_MUTED,
            font=ctk.CTkFont("Microsoft YaHei UI", 11),
        )
        self.goal_entry.grid(row=0, column=1, sticky="ew")

        ctk.CTkButton(
            goal, text="启动", width=58, height=30, corner_radius=8,
            fg_color=CARD_BG, border_width=1, border_color=BORDER,
            hover_color=CARD_HOVER, text_color=TEXT_PRIMARY,
            font=ctk.CTkFont("Microsoft YaHei UI", 11),
            command=self._start_goal,
        ).grid(row=0, column=2, padx=6)

        ctk.CTkButton(
            goal, text="查看", width=58, height=30, corner_radius=8,
            fg_color=CARD_BG, border_width=1, border_color=BORDER,
            hover_color=CARD_HOVER, text_color=TEXT_PRIMARY,
            font=ctk.CTkFont("Microsoft YaHei UI", 11),
            command=self._show_goal,
        ).grid(row=0, column=3)

        # Main Prompt Input Composer Box
        composer = ctk.CTkFrame(
            main, corner_radius=14, fg_color=CARD_BG,
            border_width=1, border_color=BORDER,
        )
        composer.grid(row=4, column=0, columnspan=2, padx=16, pady=(0, 8), sticky="ew")
        composer.grid_columnconfigure(0, weight=1)

        self.input = ctk.CTkTextbox(
            composer, height=72, wrap="word", corner_radius=10,
            fg_color=BG_ROOT, border_width=1, border_color=BORDER,
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont("Microsoft YaHei UI", 13),
        )
        self.input.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        self.input.bind("<Control-Return>", lambda _e: self._send() or "break")

        # Action button column
        buttons = ctk.CTkFrame(composer, fg_color="transparent")
        buttons.grid(row=0, column=1, padx=(0, 10), pady=10)

        self.send = ctk.CTkButton(
            buttons, text="发送", width=86, height=32, corner_radius=8,
            fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color="#ffffff",
            font=ctk.CTkFont("Microsoft YaHei UI", 12, "bold"),
            command=self._send,
        )
        self.send.pack()

        self.stop = ctk.CTkButton(
            buttons, text="中断", width=86, height=30, corner_radius=8,
            fg_color=DANGER, hover_color=DANGER_HOVER, text_color="#ffffff",
            font=ctk.CTkFont("Microsoft YaHei UI", 11, "bold"),
            command=self._cancel, state="disabled",
        )
        self.stop.pack(pady=(8, 0))

    def _build_statusbar(self, main: ctk.CTkFrame) -> None:
        bar = ctk.CTkFrame(main, corner_radius=0, fg_color="#080c10", height=26)
        bar.grid(row=5, column=0, columnspan=2, sticky="ew")

        ctk.CTkLabel(
            bar, textvariable=self.status, text_color=TEXT_MUTED,
            font=ctk.CTkFont("Microsoft YaHei UI", 10),
        ).pack(side="left", padx=16)

        ctk.CTkLabel(
            bar, text="Ctrl+Enter 发送 · Esc 中断 · 右上角切换活动抽屉",
            text_color=TEXT_MUTED, font=ctk.CTkFont("Microsoft YaHei UI", 10),
        ).pack(side="right", padx=16)

    # ------------------------------------------------------------------ Chat & Boxes
    def _readonly_box(self, parent) -> ctk.CTkTextbox:
        box = ctk.CTkTextbox(
            parent, wrap="word", corner_radius=8, fg_color=BG_ROOT,
            border_width=1, border_color=BORDER,
            text_color=TEXT_PRIMARY, font=ctk.CTkFont("Consolas", 11),
        )
        box.pack(fill="both", expand=True, padx=4, pady=4)
        self._make_readonly_selectable(box)
        return box

    def _append(self, widget: ctk.CTkTextbox, text: str, tag: str | None = None) -> None:
        if widget is None:
            return
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
        """Append a modern message bubble to the scrollable chat stream."""
        is_user = role in {"you", "你"}
        is_system = role in {"system", "系统", "撤销", "验证", "保存", "导出", "Goal", "错误"}
        bubble_bg = USER_BG if is_user else (SYSTEM_BG if is_system else ASSISTANT_BG)
        bubble_fg = USER_TEXT if is_user else (TEXT_PRIMARY if not is_system else "#93c5fd")
        label = "你" if is_user else ("小朴" if role in {"小朴", "assistant"} else role)

        row = ctk.CTkFrame(self.chat, fg_color="transparent")
        row._xiaopu_bubble = True
        row.grid(sticky="e" if is_user else ("ew" if is_system else "w"), padx=8, pady=6)
        row.grid_columnconfigure(0, weight=1)
        row.grid_columnconfigure(1, weight=1)

        card = ctk.CTkFrame(
            row, corner_radius=12, fg_color=bubble_bg,
            border_width=1, border_color=BORDER,
        )
        if is_system:
            card.grid(row=0, column=0, columnspan=2, sticky="ew", padx=30)
        else:
            card.grid(row=0, column=1 if is_user else 0, sticky="e" if is_user else "w")

        card.grid_columnconfigure(0, weight=1)

        # Header row with role tag and copy button
        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.grid(row=0, column=0, padx=14, pady=(8, 2), sticky="ew")
        hdr.grid_columnconfigure(0, weight=1)

        tag_color = "#34d399" if is_user else ("#60a5fa" if is_system else "#38bdf8")
        ctk.CTkLabel(
            hdr, text=label, font=ctk.CTkFont("Microsoft YaHei UI", 11, "bold"),
            text_color=tag_color,
        ).grid(row=0, column=0, sticky="w")

        if not is_system:
            ctk.CTkButton(
                hdr, text="复制", width=40, height=22, corner_radius=6,
                fg_color="transparent", border_width=1, border_color=BORDER,
                hover_color=CARD_HOVER, text_color=TEXT_MUTED,
                font=ctk.CTkFont("Microsoft YaHei UI", 9),
                command=lambda t=text: self._copy_text(t),
            ).grid(row=0, column=1, sticky="e")

        # Message body
        body = ctk.CTkLabel(
            card, text=text, justify="left", anchor="w",
            wraplength=660, font=ctk.CTkFont("Microsoft YaHei UI", 13),
            text_color=bubble_fg,
        )
        body.grid(row=1, column=0, padx=14, pady=(2, 10), sticky="w")

        if hasattr(self.chat, "_parent_canvas"):
            self.chat._parent_canvas.yview_moveto(1.0)

        if role in {"小朴", "assistant", "you", "你"}:
            self._last_chat_label = body

    def _copy_text(self, text: str) -> None:
        if not text:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status.set("已复制到剪贴板")

    def _copy_timeline(self) -> None:
        content = "\n".join(self._trajectory)
        if content:
            self._copy_text(content)
            self.status.set("已复制完整时间线")

    def _copy_cot(self) -> None:
        text = self._reasoning_text or (self.h.state.last_reasoning_text if hasattr(self, "h") and hasattr(self.h, "state") else "")
        if text.strip():
            self._copy_text(text)
            self.status.set("已复制原始思维链")
        else:
            self.status.set("暂无原始思维链可复制")

    # ------------------------------------------------------------------ Model & Controls
    def _switch_model(self, _event=None) -> None:
        value = self.model_var.get().strip()
        if not value:
            return
        if config.provider() == "anthropic":
            os.environ["ANTHROPIC_MODEL"] = value
        else:
            os.environ["OPENAI_MODEL"] = value
        if hasattr(self, "h") and getattr(self.h, "llm", None):
            self.h.llm.model = value
        self.status.set(f"模型已切换为：{value}")
        self._refresh_status()

    def _switch_permissions(self, _event=None) -> None:
        policy = self.permissions_var.get()
        os.environ["COMMAND_POLICY"] = policy
        config.set_command_policy(policy)
        self.status.set(f"Shell 命令策略：{policy}")

    def _toggle_activity(self) -> None:
        if self.activity_visible:
            self.activity.grid_forget()
            self.activity_visible = False
            self.activity_btn.configure(fg_color=CARD_BG, text_color=TEXT_PRIMARY)
        else:
            self.activity.grid(row=2, column=1, rowspan=3, sticky="nsew", padx=(0, 16), pady=(0, 8))
            self.activity_visible = True
            self.activity_btn.configure(fg_color=ACCENT, text_color="#ffffff")

    # ------------------------------------------------------------------ Streaming & Runtime
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
                ok = messagebox.askyesno("Shell 权限确认", f"智能体请求执行以下 Shell 命令：\n\n{command}\n\n是否允许执行？")
                holder["decision"] = "allow" if ok else "deny"
                decided.set()
        except queue.Empty:
            pass
        if hasattr(self, "root") and hasattr(self.root, "after"):
            self.root.after(100, self._drain_approvals)

    def _capture_runtime_event(self, event: RuntimeEvent) -> None:
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
                    self._reasoning_text = getattr(self, "_reasoning_text", "") + str(payload)
                    self._append(getattr(self, "cot_box", None), str(payload))
                elif kind == "runtime":
                    self._show_event(payload)
        except queue.Empty:
            pass
        if hasattr(self, "root") and hasattr(self.root, "after"):
            self.root.after(50, self._drain_events)

    def _on_stream_piece(self, piece: str) -> None:
        self._stream_buffer = getattr(self, "_stream_buffer", "") + piece
        if not getattr(self, "_streaming_started", False):
            self._streaming_started = True
            self._append_chat("小朴", "")
            self._stream_bubble_label = self._last_chat_label
        if self._stream_bubble_label is not None:
            self._stream_bubble_label.configure(text=self._stream_buffer)
            if hasattr(self.chat, "_parent_canvas"):
                self.chat._parent_canvas.yview_moveto(1.0)

    def _finish_stream(self, reply: str) -> None:
        if getattr(self, "_streaming_started", False):
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
        p = getattr(event, "payload", {})
        kind = getattr(event, "kind", None)
        if kind == EventKind.TURN_STARTED:
            if hasattr(self, "live_action"):
                self.live_action.set("正在分析任务并选择路线…")
            if hasattr(self, "live_phase"):
                self.live_phase.set("阶段：intake")
            self._reasoning_text = ""
            self._trajectory = []
            self._refresh_status()
            return
        if kind == EventKind.CONTROLLER_DECISION:
            if hasattr(self, "live_action"):
                self.live_action.set(f"决策：{p.get('action', 'planning')}")
            if hasattr(self, "live_phase"):
                self.live_phase.set(f"阶段：{p.get('phase', '—')}")
            line = f"决策 · {p.get('action')} · {p.get('reason', '')}"
            if hasattr(self, "_trajectory"):
                self._trajectory.append(line)
            self._append(getattr(self, "trajectory_box", None), line)
            return
        if kind == EventKind.PLANNING_DECISION:
            line = f"规划 · {p.get('next_action', '')}\n依据 · {p.get('reason', '')}"
            if hasattr(self, "_trajectory"):
                self._trajectory.append(line)
            self._append(getattr(self, "trajectory_box", None), line)
            if hasattr(self, "live_action"):
                self.live_action.set(str(p.get("next_action", "正在规划…")))
            if hasattr(self, "live_phase"):
                self.live_phase.set(f"阶段：{p.get('stage', '—')}")
            return
        if kind == EventKind.TOOL_STARTED:
            self.tool_started_count = getattr(self, "tool_started_count", 0) + 1
            self._refresh_counts()
            if hasattr(self, "live_action"):
                self.live_action.set(f"⚡ 调用 {p.get('tool', '未知工具')}…")
            line = f"▸ {p.get('tool', '?')}  {p.get('arguments', '')[:240]}"
            if hasattr(self, "tool_log_lines"):
                self.tool_log_lines.append(line)
            if hasattr(self, "_trajectory"):
                self._trajectory.append(line)
            self._append(getattr(self, "trajectory_box", None), line)
            return
        if kind == EventKind.TOOL_COMPLETED:
            self.tool_completed_count = getattr(self, "tool_completed_count", 0) + 1
            self._refresh_counts()
            if hasattr(self, "live_action"):
                self.live_action.set(f"✓ {p.get('tool', '工具')} 完成")
            line = f"✓ {p.get('tool', '?')}\n结果：{str(p.get('output', ''))[:800]}"
            if hasattr(self, "_trajectory"):
                self._trajectory.append(line)
            self._append(getattr(self, "trajectory_box", None), line)
            return
        if kind == EventKind.TOOL_FAILED:
            self.tool_failed_count = getattr(self, "tool_failed_count", 0) + 1
            self._refresh_counts()
            if hasattr(self, "live_action"):
                self.live_action.set(f"✕ {p.get('tool', '工具')} 失败")
            line = f"✕ {p.get('tool', '?')}: {str(p.get('error', ''))[:320]}"
            if hasattr(self, "_trajectory"):
                self._trajectory.append(line)
            self._append(getattr(self, "trajectory_box", None), line)
            return
        if kind == EventKind.MODEL_RESPONSE:
            reasoning = str(p.get("reasoning_content") or getattr(self, "_reasoning_text", "") or "")
            if reasoning.strip():
                self._append(getattr(self, "cot_box", None), "\n── 模型响应 ──\n" + reasoning + "\n")
                if hasattr(self, "_trajectory"):
                    self._trajectory.append("原始思维链：\n" + reasoning)
                self._append(getattr(self, "trajectory_box", None), "原始思维链：\n" + reasoning)
            else:
                self._append(getattr(self, "cot_box", None), "\n[本次响应 provider 未返回原始思维链]\n")
            if hasattr(self, "live_action"):
                self.live_action.set("模型已返回，正在处理结果…" if p.get("tool_call_count") else "检查目标达成情况…")
            return
        if kind == EventKind.PHASE_CHANGED:
            line = f"阶段流转 · {p.get('from_phase')} → {p.get('to_phase')}"
            if hasattr(self, "_trajectory"):
                self._trajectory.append(line)
            self._append(getattr(self, "trajectory_box", None), line)
            if hasattr(self, "live_phase"):
                self.live_phase.set(f"阶段：{p.get('to_phase', '—')}")
            return

    def _set_running(self, value: bool) -> None:
        self.running = value
        if hasattr(self, "send"):
            self.send.configure(state="disabled" if value else "normal")
        if hasattr(self, "stop"):
            self.stop.configure(state="normal" if value else "disabled")
        if hasattr(self, "status"):
            self.status.set("正在执行…" if value else "就绪")
        if value:
            self.started_at = time.monotonic()
            self.tool_started_count = self.tool_completed_count = self.tool_failed_count = 0
            if hasattr(self, "live_action"):
                self.live_action.set("已提交任务给模型…")
            if hasattr(self, "live_phase"):
                self.live_phase.set("阶段：intake")
            self._refresh_counts()
        else:
            self.started_at = None
            if hasattr(self, "live_action"):
                self.live_action.set("任务完成，等待下一条指令")
        self._refresh_status()

    def _refresh_counts(self) -> None:
        if hasattr(self, "live_counts"):
            started = getattr(self, "tool_started_count", 0)
            completed = getattr(self, "tool_completed_count", 0)
            failed = getattr(self, "tool_failed_count", 0)
            self.live_counts.set(f"工具 {started} · 完成 {completed} · 失败 {failed}")

    def _refresh_status(self) -> None:
        if not hasattr(self, "h") or not hasattr(self.h, "state"):
            return
        state = self.h.state
        fresh = len(state.fresh_evidence())
        phase_str = getattr(state.phase, "value", str(state.phase))
        if hasattr(self, "status"):
            self.status.set(
                f"{phase_str} · epoch {state.mutation_epoch} · 证据 {fresh} · "
                f"tokens {state.total_tokens} · repair {state.repair_attempts}/{state.max_repairs}"
            )

    def _tick_elapsed(self) -> None:
        if self.started_at is not None and hasattr(self, "live_elapsed"):
            elapsed = max(0, int(time.monotonic() - self.started_at))
            minutes, seconds = divmod(elapsed, 60)
            self.live_elapsed.set(f"{minutes:02d}:{seconds:02d}" if minutes else f"{seconds} 秒")
        if hasattr(self, "root") and hasattr(self.root, "after"):
            self.root.after(250, self._tick_elapsed)

    def _send(self) -> None:
        if getattr(self, "running", False):
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

        threading.Thread(target=worker, name="xiaopu-gui-worker", daemon=True).start()

    def _cancel(self) -> None:
        if hasattr(self, "h") and hasattr(self.h, "request_cancel"):
            self.h.request_cancel()
        if hasattr(self, "status"):
            self.status.set("正在安全中断…")

    # ------------------------------------------------------------------ Command Actions
    def _start_goal(self) -> None:
        objective = self.goal_entry.get().strip()
        if objective:
            try:
                self._append_chat("Goal", self.h.start_goal(objective))
            except Exception as exc:
                messagebox.showerror("Goal 启动失败", str(exc))

    def _show_goal(self) -> None:
        try:
            summary = self.h.goal_summary()
            messagebox.showinfo("长期目标状态", summary)
        except Exception as exc:
            messagebox.showerror("获取 Goal 失败", str(exc))

    def _new_session(self) -> None:
        if getattr(self, "running", False):
            return
        from .session_store import save_session
        try:
            save_session(self.h)
        except Exception:
            pass
        self.h.reset()
        self._clear_chat()
        self._append_chat("system", "已保存前序会话并创建全新会话。")
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
        try:
            record = save_session(self.h)
            path = filedialog.asksaveasfilename(
                defaultextension=".md",
                initialfile=f"xiaopu-session-{record.id[:8]}.md",
                filetypes=[("Markdown", "*.md")],
            )
            if not path:
                return
            exported = export_session(record.id, Path(path))
            self._append_chat("导出", f"会话已导出：{exported}")
        except Exception as exc:
            messagebox.showerror("导出失败", str(exc))

    def _undo(self) -> None:
        try:
            res = self.h.undo()
            self._append_chat("撤销", res)
        except Exception as exc:
            messagebox.showerror("撤销失败", str(exc))

    # ------------------------------------------------------------------ Sidebar Data
    def _refresh_sessions(self) -> None:
        from .session_store import list_sessions

        for child in self.session_frame.winfo_children():
            child.destroy()
        self._session_records = list_sessions()
        if not self._session_records:
            ctk.CTkLabel(
                self.session_frame, text="暂无保存的会话",
                font=ctk.CTkFont("Microsoft YaHei UI", 11),
                text_color=TEXT_MUTED,
            ).grid(row=0, column=0, pady=16)
            return

        for index, record in enumerate(self._session_records[:50]):
            card = ctk.CTkFrame(
                self.session_frame, corner_radius=8, fg_color=CARD_BG,
                border_width=1, border_color=BORDER,
            )
            card.grid(row=index, column=0, padx=4, pady=3, sticky="ew")
            card.grid_columnconfigure(0, weight=1)

            title_text = record.title[:22] + ("…" if len(record.title) > 22 else "")
            time_text = record.updated_at[:16] if getattr(record, "updated_at", None) else ""

            btn_content = f"{title_text}\n{time_text}" if time_text else title_text
            ctk.CTkButton(
                card, text=btn_content, anchor="w",
                height=36, corner_radius=6, fg_color="transparent",
                hover_color=CARD_HOVER, text_color=TEXT_PRIMARY,
                font=ctk.CTkFont("Microsoft YaHei UI", 11),
                command=lambda i=index: self._resume_session(i),
            ).grid(row=0, column=0, sticky="ew", padx=4, pady=2)

            ctk.CTkButton(
                card, text="✕", width=24, height=24, corner_radius=6,
                fg_color="transparent", hover_color="#451a1a", text_color="#f87171",
                font=ctk.CTkFont("Microsoft YaHei UI", 10, "bold"),
                command=lambda i=index: self._delete_session(i),
            ).grid(row=0, column=1, padx=4)

    def _clear_chat(self) -> None:
        for child in list(getattr(self.chat, "winfo_children", lambda: [])()):
            if getattr(child, "_xiaopu_bubble", False):
                child.destroy()
        self._streaming_started = False
        self._stream_buffer = ""
        self._stream_bubble_label = None

    @staticmethod
    def _history_messages(payload: dict) -> list[tuple[str, str]]:
        """Visible conversation turns from a session snapshot."""
        pairs = []
        for message in payload.get("messages", []):
            role = message.get("role")
            content = str(message.get("content", "")).strip()
            if role == "user" and content:
                pairs.append(("you", content))
            elif role == "assistant" and content:
                pairs.append(("小朴", content))
        return pairs

    def _render_history(self, payload: dict) -> None:
        self._clear_chat()
        pairs = self._history_messages(payload)
        for role, text in pairs:
            self._append_chat(role, text)

    def _resume_session(self, index: int) -> None:
        from .session_store import load_session, restore_harness

        if index >= len(self._session_records):
            return
        record = self._session_records[index]
        payload = load_session(record.id)
        if payload is None:
            messagebox.showerror("恢复失败", "无法读取会话文件。")
            return
        report = restore_harness(self.h, payload)
        self._render_history(payload)
        self._append_chat("system", f"✓ 已恢复会话 [{record.id[:8]}] · {report}")
        self._refresh_status()

    def _delete_session(self, index: int) -> None:
        from .session_store import delete_session

        if index >= len(self._session_records):
            return
        record = self._session_records[index]
        if messagebox.askyesno("删除会话", f"确认删除会话 [{record.id[:8]}]？\n{record.title}\n此操作不可撤销。"):
            delete_session(record.id)
            self._refresh_sessions()

    def _refresh_workspaces(self) -> None:
        from .workspace_store import list_workspaces

        values = [str(w) for w in list_workspaces()]
        current = self.workspace_var.get()
        if current not in values:
            values.insert(0, current)
        self._workspace_records = values
        self.workspace_menu.configure(values=values)
        self.workspace_menu.set(current)

    def _switch_workspace_value(self, value: str) -> None:
        os.environ["WORKSPACE"] = value
        self.workspace_var.set(value)
        self.status.set(f"工作区已切换为：{value}")

    def _choose_workspace(self) -> None:
        path = filedialog.askdirectory(title="选择工作区目录")
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
        self.status.set(f"工作区已更新为：{path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-gui", description="Launch the modern Xiaopu GUI")
    parser.add_argument("--workspace", type=str, default=None, help="working directory")
    parser.add_argument("--model", type=str, default=None, help="model override")
    return parser


def main() -> int:
    _force_utf8_stdio()
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
