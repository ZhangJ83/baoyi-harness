"""Modern CustomTkinter GUI for the complete Xiaopu Harness.

Layout follows the Claude Desktop / Cowork 3-column paradigm:
- Left rail: Mode pill (Cowork / Code), + New session, Quick actions (Workspace, Artifacts, Goal, Doctor),
  Recents session history list with delete, Gateway status footer, and Dark/Light theme toggle;
- Center chat: Session title dropdown, PPT quick action pills, right drawer toggle,
  user bubbles, collapsible 'Thought process (思维链)' card with real-time genuine reasoning,
  clean assistant responses, and a floating bottom composer with model selector & send button;
- Right drawer: Progress metrics, Working folder info, Live timeline of tool calls,
  and Raw provider reasoning stream with copy buttons.

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

# Design Tokens: Clean Claude Desktop & Cowork Inspired Palette
THEMES = {
    "dark": {
        "bg_root": "#0d1117",
        "sidebar_bg": "#121720",
        "card_bg": "#161f2b",
        "card_hover": "#1c2736",
        "user_bg": "#16382c",
        "user_text": "#ecfdf5",
        "assistant_bg": "#16202c",
        "assistant_text": "#f1f5f9",
        "system_bg": "#141c26",
        "thought_bg": "#131922",
        "thought_border": "#283548",
        "thought_text": "#c4b5fd",
        "border": "#222d3a",
        "border_light": "#2d3b4c",
        "text_primary": "#f8fafc",
        "text_secondary": "#94a3b8",
        "text_muted": "#64748b",
        "accent": "#ea580c",        # Warm terracotta/orange accent
        "accent_hover": "#c2410c",
        "accent_emerald": "#10b981",
        "accent_blue": "#2563eb",
        "danger": "#ef4444",
        "danger_hover": "#dc2626",
    },
    "light": {
        "bg_root": "#fcfcfc",
        "sidebar_bg": "#f7f7f6",
        "card_bg": "#ffffff",
        "card_hover": "#f3f4f6",
        "user_bg": "#f0ede6",
        "user_text": "#1e293b",
        "assistant_bg": "#ffffff",
        "assistant_text": "#1e293b",
        "system_bg": "#f1f5f9",
        "thought_bg": "#fbfaf8",
        "thought_border": "#e5e7eb",
        "thought_text": "#7c3aed",
        "border": "#e5e7eb",
        "border_light": "#d1d5db",
        "text_primary": "#0f172a",
        "text_secondary": "#475569",
        "text_muted": "#94a3b8",
        "accent": "#ea580c",
        "accent_hover": "#c2410c",
        "accent_emerald": "#059669",
        "accent_blue": "#2563eb",
        "danger": "#dc2626",
        "danger_hover": "#b91c1c",
    },
}


def _force_utf8_stdio() -> None:
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _set_app_user_model_id() -> None:
    """Ensure Windows taskbar groups under Xiaopu and displays custom icon."""
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("xiaopu.agent.gui.v2")
        except Exception:
            pass


_set_app_user_model_id()


class AgentGUI:
    def __init__(self, root: ctk.CTk, model: str | None = None) -> None:
        from .harness import Harness

        self.root = root
        self.model = model
        self.h = Harness(model=model, interactive=True)
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.approvals: queue.Queue = queue.Queue()
        self.running = False
        self.theme_name = config.theme() if config.theme() in THEMES else "dark"
        self.colors = THEMES[self.theme_name]

        # Reactive string variables for UI bindings
        self.status = ctk.StringVar(value="就绪")
        self.current_title = ctk.StringVar(value="新对话")
        self.live_action = ctk.StringVar(value="就绪 · 等待指令")
        self.live_phase = ctk.StringVar(value="Phase: intake")
        self.live_elapsed = ctk.StringVar(value="0 秒")
        self.live_counts = ctk.StringVar(value="工具 0 · 完成 0 · 失败 0")
        self.model_var = ctk.StringVar(value=getattr(self.h.llm, "model", config.model()))
        self.permissions_var = ctk.StringVar(value=config.command_policy())
        self.workspace_var = ctk.StringVar(value=str(config.sandbox_root()))
        self.mode_var = ctk.StringVar(value="cowork")

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
        self.activity_visible = True
        self.sidebar_visible = True
        self._app_icon_ctk = None
        self._app_icon_small = None
        self._thought_box = None
        self._thought_container = None
        self._thought_visible = True

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
        self.root.title("小朴 Agent · Xiaopu")
        self.root.geometry("1420x900")
        self.root.minsize(1040, 680)
        ctk.set_appearance_mode(self.theme_name)
        ctk.set_default_color_theme("blue")
        self.root.configure(fg_color=self.colors["bg_root"])

        # Load & apply custom app icon
        self._apply_window_icon()

        self.root.grid_columnconfigure(0, weight=0)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_columnconfigure(2, weight=0)
        self.root.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main()
        self._build_activity_drawer()

    def _apply_window_icon(self) -> None:
        try:
            from PIL import Image, ImageTk
            assets_dir = Path(__file__).resolve().parent / "assets"
            ico_path = assets_dir / "icon.ico"
            png_path = assets_dir / "icon.png"

            if ico_path.exists() and os.name == "nt":
                try:
                    self.root.iconbitmap(str(ico_path))
                except Exception:
                    pass

            if png_path.exists():
                icon_img = Image.open(png_path).convert("RGBA")
                self._icon_photo = ImageTk.PhotoImage(icon_img)
                self.root.iconphoto(False, self._icon_photo)
                self._app_icon_ctk = ctk.CTkImage(light_image=icon_img, dark_image=icon_img, size=(30, 30))
                self._app_icon_small = ctk.CTkImage(light_image=icon_img, dark_image=icon_img, size=(18, 18))
        except Exception:
            pass

    def _build_sidebar(self) -> None:
        self.sidebar = ctk.CTkFrame(
            self.root, width=270, corner_radius=0, fg_color=self.colors["sidebar_bg"],
            border_width=1, border_color=self.colors["border"],
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_columnconfigure(0, weight=1)
        self.sidebar.grid_rowconfigure(3, weight=1)

        # Top Control Bar: Logo + Brand + Collapse button
        top_ctrl = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        top_ctrl.grid(row=0, column=0, padx=14, pady=(14, 10), sticky="ew")
        top_ctrl.grid_columnconfigure(1, weight=1)

        if getattr(self, "_app_icon_ctk", None) is not None:
            ctk.CTkLabel(top_ctrl, text="", image=self._app_icon_ctk).grid(row=0, column=0, padx=(0, 8), sticky="w")
        else:
            logo_box = ctk.CTkFrame(top_ctrl, width=28, height=28, corner_radius=6, fg_color=self.colors["accent_blue"])
            logo_box.grid(row=0, column=0, padx=(0, 8), sticky="w")
            logo_box.pack_propagate(False)
            ctk.CTkLabel(logo_box, text="朴", font=ctk.CTkFont("Microsoft YaHei UI", 13, "bold"),
                         text_color="#ffffff").place(relx=0.5, rely=0.5, anchor="center")

        brand_lbl = ctk.CTkLabel(
            top_ctrl, text="小朴 Xiaopu", font=ctk.CTkFont("Microsoft YaHei UI", 16, "bold"),
            text_color=self.colors["text_primary"],
        )
        brand_lbl.grid(row=0, column=1, sticky="w")

        # Mode Switcher Pill (⇄ Cowork / </> Code)
        mode_pill = ctk.CTkFrame(
            self.sidebar, corner_radius=9, fg_color=self.colors["bg_root"],
            border_width=1, border_color=self.colors["border"], height=34,
        )
        mode_pill.grid(row=1, column=0, padx=14, pady=(0, 10), sticky="ew")
        mode_pill.grid_columnconfigure(0, weight=1)
        mode_pill.grid_columnconfigure(1, weight=1)

        self.btn_cowork = ctk.CTkButton(
            mode_pill, text="⇄ 对话 / PPT", height=26, corner_radius=7,
            fg_color=self.colors["card_bg"], hover_color=self.colors["card_hover"],
            text_color=self.colors["text_primary"], font=ctk.CTkFont("Microsoft YaHei UI", 11, "bold"),
            command=lambda: self._set_mode("cowork"),
        )
        self.btn_cowork.grid(row=0, column=0, padx=3, pady=3, sticky="ew")

        self.btn_code = ctk.CTkButton(
            mode_pill, text="</> 代码模式", height=26, corner_radius=7,
            fg_color="transparent", hover_color=self.colors["card_hover"],
            text_color=self.colors["text_secondary"], font=ctk.CTkFont("Microsoft YaHei UI", 11),
            command=lambda: self._set_mode("code"),
        )
        self.btn_code.grid(row=0, column=1, padx=3, pady=3, sticky="ew")

        # Navigation & Quick Action Items
        actions = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        actions.grid(row=2, column=0, padx=12, pady=(0, 8), sticky="ew")

        # + New Session button
        ctk.CTkButton(
            actions, text="＋  新建对话 (New)", height=34, corner_radius=8,
            fg_color=self.colors["card_bg"], hover_color=self.colors["card_hover"],
            border_width=1, border_color=self.colors["border"],
            text_color=self.colors["text_primary"], anchor="w",
            font=ctk.CTkFont("Microsoft YaHei UI", 12, "bold"),
            command=self._new_session,
        ).pack(fill="x", pady=(0, 4))

        # Quick action pills
        for icon_text, handler in (
            ("📁  工作区目录 (Workspace)", self._choose_workspace),
            ("🎯  长期目标管理 (Goal)", self._show_goal_dialog),
            ("⚗  导出/保存 PPT (Artifacts)", self._save_ppt),
            ("⚙  环境诊断 (Doctor)", self._show_doctor_dialog),
        ):
            ctk.CTkButton(
                actions, text=icon_text, height=28, corner_radius=6,
                fg_color="transparent", hover_color=self.colors["card_hover"],
                text_color=self.colors["text_secondary"], anchor="w",
                font=ctk.CTkFont("Microsoft YaHei UI", 11),
                command=handler,
            ).pack(fill="x", pady=1)

        # Recents Session History List
        recents_header = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        recents_header.grid(row=3, column=0, padx=14, pady=(10, 2), sticky="new")
        ctk.CTkLabel(
            recents_header, text="历史会话 (Recents)", font=ctk.CTkFont("Microsoft YaHei UI", 11, "bold"),
            text_color=self.colors["text_muted"],
        ).pack(side="left")

        self.session_frame = ctk.CTkScrollableFrame(
            self.sidebar, corner_radius=8,
            fg_color="transparent",
        )
        self.session_frame.grid(row=3, column=0, padx=8, pady=(28, 6), sticky="nsew")
        self.session_frame.grid_columnconfigure(0, weight=1)

        # Bottom Footer: Gateway status + Theme Toggle
        footer = ctk.CTkFrame(
            self.sidebar, corner_radius=0, fg_color=self.colors["bg_root"],
            border_width=1, border_color=self.colors["border"], height=44,
        )
        footer.grid(row=4, column=0, sticky="ew")
        footer.grid_columnconfigure(0, weight=1)

        gw_lbl = ctk.CTkLabel(
            footer, text="☀️ Gateway · Online", font=ctk.CTkFont("Microsoft YaHei UI", 10, "bold"),
            text_color=self.colors["text_secondary"],
        )
        gw_lbl.grid(row=0, column=0, padx=12, pady=8, sticky="w")

        theme_btn = ctk.CTkButton(
            footer, text="🌓 主题", width=52, height=24, corner_radius=6,
            fg_color=self.colors["card_bg"], border_width=1, border_color=self.colors["border"],
            hover_color=self.colors["card_hover"], text_color=self.colors["text_secondary"],
            font=ctk.CTkFont("Microsoft YaHei UI", 10),
            command=self._toggle_theme,
        )
        theme_btn.grid(row=0, column=1, padx=10, pady=8, sticky="e")

    def _set_mode(self, mode: str) -> None:
        self.mode_var.set(mode)
        if mode == "cowork":
            self.btn_cowork.configure(fg_color=self.colors["card_bg"], text_color=self.colors["text_primary"])
            self.btn_code.configure(fg_color="transparent", text_color=self.colors["text_secondary"])
            config.set_plan_mode(False)
            self.status.set("已切换至 对话/PPT 协同模式")
        else:
            self.btn_code.configure(fg_color=self.colors["card_bg"], text_color=self.colors["text_primary"])
            self.btn_cowork.configure(fg_color="transparent", text_color=self.colors["text_secondary"])
            config.set_plan_mode(True)
            self.status.set("已切换至 代码与计划模式 (Plan Mode)")

    def _build_main(self) -> None:
        self.main_panel = ctk.CTkFrame(self.root, corner_radius=0, fg_color=self.colors["bg_root"])
        self.main_panel.grid(row=0, column=1, sticky="nsew")
        self.main_panel.grid_columnconfigure(0, weight=1)
        self.main_panel.grid_rowconfigure(1, weight=1)

        self._build_topbar(self.main_panel)

        # Center Chat Scrollable Surface
        self.chat = ctk.CTkScrollableFrame(self.main_panel, fg_color=self.colors["bg_root"], corner_radius=0)
        self.chat.grid(row=1, column=0, sticky="nsew", padx=(20, 20), pady=(0, 6))
        self.chat.grid_columnconfigure(0, weight=1)

        # Floating Bottom Composer & Status Footer
        self._build_composer(self.main_panel)
        self._build_statusbar(self.main_panel)

        self._append_chat("system", "小朴已就绪。输入任务描述开始执行，支持代码编写、文档生成与 PPT 自动化。")

    def _build_topbar(self, main: ctk.CTkFrame) -> None:
        bar = ctk.CTkFrame(
            main, fg_color=self.colors["bg_root"], height=48,
            border_width=0,
        )
        bar.grid(row=0, column=0, padx=16, pady=(10, 4), sticky="ew")
        bar.grid_columnconfigure(0, weight=1)

        # Left: Session Title Dropdown / Indicator
        left = ctk.CTkFrame(bar, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w")

        self.toggle_sidebar_btn = ctk.CTkButton(
            left, text="≡", width=30, height=28, corner_radius=6,
            fg_color="transparent", hover_color=self.colors["card_hover"],
            text_color=self.colors["text_secondary"], font=ctk.CTkFont("Microsoft YaHei UI", 14, "bold"),
            command=self._toggle_sidebar,
        )
        self.toggle_sidebar_btn.pack(side="left", padx=(0, 6))

        title_pill = ctk.CTkFrame(left, corner_radius=6, fg_color=self.colors["sidebar_bg"],
                                  border_width=1, border_color=self.colors["border"])
        title_pill.pack(side="left")
        ctk.CTkLabel(
            title_pill, textvariable=self.current_title, font=ctk.CTkFont("Microsoft YaHei UI", 12, "bold"),
            text_color=self.colors["text_primary"],
        ).pack(side="left", padx=(10, 4), pady=3)
        ctk.CTkLabel(
            title_pill, text="⌵", font=ctk.CTkFont("Microsoft YaHei UI", 10),
            text_color=self.colors["text_muted"],
        ).pack(side="left", padx=(0, 8), pady=3)

        # Right Toolbar Action Pills
        right = ctk.CTkFrame(bar, fg_color="transparent")
        right.grid(row=0, column=1, sticky="e")

        ctk.CTkButton(
            right, text="🔍 校验", width=56, height=28, corner_radius=6,
            fg_color=self.colors["card_bg"], border_width=1, border_color=self.colors["border"],
            hover_color=self.colors["card_hover"], text_color=self.colors["text_secondary"],
            font=ctk.CTkFont("Microsoft YaHei UI", 11),
            command=self._verify,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            right, text="💾 保存", width=56, height=28, corner_radius=6,
            fg_color=self.colors["card_bg"], border_width=1, border_color=self.colors["border"],
            hover_color=self.colors["card_hover"], text_color=self.colors["text_secondary"],
            font=ctk.CTkFont("Microsoft YaHei UI", 11),
            command=self._save_ppt,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            right, text="↩ 撤销", width=56, height=28, corner_radius=6,
            fg_color=self.colors["card_bg"], border_width=1, border_color=self.colors["border"],
            hover_color=self.colors["card_hover"], text_color=self.colors["text_secondary"],
            font=ctk.CTkFont("Microsoft YaHei UI", 11),
            command=self._undo,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            right, text="📤 导出", width=56, height=28, corner_radius=6,
            fg_color=self.colors["card_bg"], border_width=1, border_color=self.colors["border"],
            hover_color=self.colors["card_hover"], text_color=self.colors["text_secondary"],
            font=ctk.CTkFont("Microsoft YaHei UI", 11),
            command=self._export_session,
        ).pack(side="left", padx=4)

        self.activity_btn = ctk.CTkButton(
            right, text="◫ 活动", width=62, height=28, corner_radius=6,
            fg_color=self.colors["accent"], hover_color=self.colors["accent_hover"],
            text_color="#ffffff", font=ctk.CTkFont("Microsoft YaHei UI", 11, "bold"),
            command=self._toggle_activity,
        )
        self.activity_btn.pack(side="left", padx=(6, 0))

    def _build_composer(self, main: ctk.CTkFrame) -> None:
        # Floating rounded composer box (Claude Desktop style)
        composer_outer = ctk.CTkFrame(
            main, corner_radius=16, fg_color=self.colors["card_bg"],
            border_width=1, border_color=self.colors["border"],
        )
        composer_outer.grid(row=2, column=0, padx=20, pady=(0, 6), sticky="ew")
        composer_outer.grid_columnconfigure(0, weight=1)

        self.input = ctk.CTkTextbox(
            composer_outer, height=68, wrap="word", corner_radius=10,
            fg_color="transparent", border_width=0,
            text_color=self.colors["text_primary"],
            font=ctk.CTkFont("Microsoft YaHei UI", 13),
        )
        self.input.grid(row=0, column=0, padx=12, pady=(10, 4), sticky="ew")
        self.input.bind("<Control-Return>", lambda _e: self._send() or "break")

        # Bottom row inside composer
        bottom_bar = ctk.CTkFrame(composer_outer, fg_color="transparent")
        bottom_bar.grid(row=1, column=0, padx=10, pady=(0, 8), sticky="ew")
        bottom_bar.grid_columnconfigure(1, weight=1)

        # Left tools in composer: Goal + Workspace
        c_left = ctk.CTkFrame(bottom_bar, fg_color="transparent")
        c_left.grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            c_left, text="＋ 目标 (Goal)", width=80, height=26, corner_radius=6,
            fg_color=self.colors["bg_root"], border_width=1, border_color=self.colors["border"],
            hover_color=self.colors["card_hover"], text_color=self.colors["text_secondary"],
            font=ctk.CTkFont("Microsoft YaHei UI", 10),
            command=self._show_goal_dialog,
        ).pack(side="left", padx=(0, 6))

        self.workspace_menu = ctk.CTkOptionMenu(
            c_left, values=[self.workspace_var.get()],
            command=self._switch_workspace_value,
            corner_radius=6, height=26, width=140,
            fg_color=self.colors["bg_root"], button_color=self.colors["border"],
            button_hover_color=self.colors["card_hover"],
            text_color=self.colors["text_secondary"], font=ctk.CTkFont("Microsoft YaHei UI", 10),
            dynamic_resizing=False,
        )
        self.workspace_menu.pack(side="left")

        # Right tools in composer: Model + Permissions + Send button
        c_right = ctk.CTkFrame(bottom_bar, fg_color="transparent")
        c_right.grid(row=0, column=2, sticky="e")

        self.model_menu = ctk.CTkOptionMenu(
            c_right, variable=self.model_var, values=config.known_models(),
            command=self._switch_model, width=150, corner_radius=6, height=26,
            fg_color=self.colors["bg_root"], button_color=self.colors["border"],
            button_hover_color=self.colors["card_hover"],
            text_color=self.colors["text_primary"], font=ctk.CTkFont("Microsoft YaHei UI", 10, "bold"),
        )
        self.model_menu.pack(side="left", padx=(0, 6))

        self.perm_menu = ctk.CTkOptionMenu(
            c_right, variable=self.permissions_var, values=("allow", "ask", "deny"),
            command=self._switch_permissions, width=70, corner_radius=6, height=26,
            fg_color=self.colors["bg_root"], button_color=self.colors["border"],
            button_hover_color=self.colors["card_hover"],
            text_color=self.colors["text_secondary"], font=ctk.CTkFont("Microsoft YaHei UI", 10),
        )
        self.perm_menu.pack(side="left", padx=(0, 8))

        self.send = ctk.CTkButton(
            c_right, text="↑ 发送", width=68, height=28, corner_radius=7,
            fg_color=self.colors["accent"], hover_color=self.colors["accent_hover"],
            text_color="#ffffff", font=ctk.CTkFont("Microsoft YaHei UI", 12, "bold"),
            command=self._send,
        )
        self.send.pack(side="left")

        self.stop = ctk.CTkButton(
            c_right, text="⏹ 中断", width=62, height=28, corner_radius=7,
            fg_color=self.colors["danger"], hover_color=self.colors["danger_hover"],
            text_color="#ffffff", font=ctk.CTkFont("Microsoft YaHei UI", 11, "bold"),
            command=self._cancel, state="disabled",
        )
        self.stop.pack(side="left", padx=(6, 0))

    def _build_statusbar(self, main: ctk.CTkFrame) -> None:
        bar = ctk.CTkFrame(main, corner_radius=0, fg_color="transparent", height=22)
        bar.grid(row=3, column=0, sticky="ew")

        ctk.CTkLabel(
            bar, textvariable=self.status, text_color=self.colors["text_muted"],
            font=ctk.CTkFont("Microsoft YaHei UI", 10),
        ).pack(side="left", padx=22)

        ctk.CTkLabel(
            bar, text="小朴 Agent 智能体 · Ctrl+Enter 发送 · Esc 中断",
            text_color=self.colors["text_muted"], font=ctk.CTkFont("Microsoft YaHei UI", 10),
        ).pack(side="right", padx=22)

    def _build_activity_drawer(self) -> None:
        self.activity = ctk.CTkFrame(
            self.root, width=380, corner_radius=0, fg_color=self.colors["sidebar_bg"],
            border_width=1, border_color=self.colors["border"],
        )
        self.activity.grid(row=0, column=2, sticky="nsew")
        self.activity.grid_propagate(False)
        self.activity.grid_columnconfigure(0, weight=1)
        self.activity.grid_rowconfigure(2, weight=1)

        # Drawer Header
        header = ctk.CTkFrame(self.activity, fg_color="transparent")
        header.grid(row=0, column=0, padx=14, pady=(14, 6), sticky="ew")
        ctk.CTkLabel(
            header, text="活动与上下文 (Context)", font=ctk.CTkFont("Microsoft YaHei UI", 13, "bold"),
            text_color=self.colors["text_primary"],
        ).pack(side="left")

        ctk.CTkButton(
            header, text="✕", width=26, height=24, corner_radius=6,
            fg_color="transparent", border_width=1, border_color=self.colors["border"],
            hover_color=self.colors["card_hover"], text_color=self.colors["text_secondary"],
            font=ctk.CTkFont("Microsoft YaHei UI", 10, "bold"),
            command=self._toggle_activity,
        ).pack(side="right")

        # Progress / State Metric Strip
        p_card = ctk.CTkFrame(
            self.activity, corner_radius=10, fg_color=self.colors["card_bg"],
            border_width=1, border_color=self.colors["border"],
        )
        p_card.grid(row=1, column=0, padx=12, pady=(4, 8), sticky="ew")
        p_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            p_card, textvariable=self.live_action, font=ctk.CTkFont("Microsoft YaHei UI", 11, "bold"),
            text_color=self.colors["text_primary"], anchor="w",
        ).pack(fill="x", padx=10, pady=(8, 2))

        sub_p = ctk.CTkFrame(p_card, fg_color="transparent")
        sub_p.pack(fill="x", padx=10, pady=(0, 8))
        ctk.CTkLabel(
            sub_p, textvariable=self.live_phase, font=ctk.CTkFont("Microsoft YaHei UI", 10),
            text_color=self.colors["text_secondary"],
        ).pack(side="left")
        ctk.CTkLabel(
            sub_p, textvariable=self.live_elapsed, font=ctk.CTkFont("Microsoft YaHei UI", 10, "bold"),
            text_color=self.colors["accent_emerald"],
        ).pack(side="right")

        # 2 High-value Tabs: 时间线 (Timeline) + 思维链 (Reasoning)
        self.activity_tabs = ctk.CTkTabview(
            self.activity, corner_radius=10,
            fg_color=self.colors["card_bg"], segmented_button_fg_color=self.colors["bg_root"],
            segmented_button_selected_color=self.colors["accent_blue"],
            segmented_button_selected_hover_color=self.colors["accent_hover"],
            text_color=self.colors["text_primary"],
        )
        self.activity_tabs.grid(row=2, column=0, padx=12, pady=(0, 10), sticky="nsew")
        self.activity_tabs.add("时间线")
        self.activity_tabs.add("思维链")

        # Tab 1: Timeline
        timeline_tab = self.activity_tabs.tab("时间线")
        t_head = ctk.CTkFrame(timeline_tab, fg_color="transparent")
        t_head.pack(fill="x", padx=2, pady=(0, 4))
        ctk.CTkLabel(
            t_head, textvariable=self.live_counts, font=ctk.CTkFont("Microsoft YaHei UI", 10),
            text_color=self.colors["text_muted"],
        ).pack(side="left")
        ctk.CTkButton(
            t_head, text="复制时间线", width=70, height=22, corner_radius=6,
            fg_color=self.colors["bg_root"], border_width=1, border_color=self.colors["border"],
            hover_color=self.colors["card_hover"], text_color=self.colors["text_secondary"],
            font=ctk.CTkFont("Microsoft YaHei UI", 9),
            command=self._copy_timeline,
        ).pack(side="right")

        self.trajectory_box = self._readonly_box(timeline_tab)

        # Tab 2: Reasoning (CoT)
        cot_tab = self.activity_tabs.tab("思维链")
        c_head = ctk.CTkFrame(cot_tab, fg_color="transparent")
        c_head.pack(fill="x", padx=2, pady=(0, 4))
        ctk.CTkLabel(
            c_head, text="原始 reasoning_content (未伪造)", font=ctk.CTkFont("Microsoft YaHei UI", 10),
            text_color=self.colors["text_muted"],
        ).pack(side="left")
        ctk.CTkButton(
            c_head, text="复制思维链", width=70, height=22, corner_radius=6,
            fg_color=self.colors["bg_root"], border_width=1, border_color=self.colors["border"],
            hover_color=self.colors["card_hover"], text_color=self.colors["text_secondary"],
            font=ctk.CTkFont("Microsoft YaHei UI", 9),
            command=self._copy_cot,
        ).pack(side="right")

        self.cot_box = self._readonly_box(cot_tab)
        self._append(self.cot_box, "模型实际返回的 reasoning_content 会实时显示在这里。\nprovider 未返回时明确提示，绝不伪造。")

    # ------------------------------------------------------------------ Chat & Boxes
    def _readonly_box(self, parent) -> ctk.CTkTextbox:
        box = ctk.CTkTextbox(
            parent, wrap="word", corner_radius=8, fg_color=self.colors["bg_root"],
            border_width=1, border_color=self.colors["border"],
            text_color=self.colors["text_primary"], font=ctk.CTkFont("Consolas", 11),
        )
        box.pack(fill="both", expand=True, padx=2, pady=2)
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

    def _append_thought_block(self, reasoning_text: str) -> None:
        """Render a collapsible Claude-style 'Thought process' card."""
        if not reasoning_text.strip():
            return

        row = ctk.CTkFrame(self.chat, fg_color="transparent")
        row._xiaopu_bubble = True
        row.grid(sticky="w", padx=6, pady=4)
        row.grid_columnconfigure(0, weight=1)

        card = ctk.CTkFrame(
            row, corner_radius=12, fg_color=self.colors["thought_bg"],
            border_width=1, border_color=self.colors["thought_border"],
        )
        card.grid(row=0, column=0, sticky="w")
        card.grid_columnconfigure(0, weight=1)

        # Thought header with toggle
        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.grid(row=0, column=0, padx=12, pady=6, sticky="ew")
        hdr.grid_columnconfigure(1, weight=1)

        t_lbl = ctk.CTkLabel(
            hdr, text="⏱  Thought process (思考过程)",
            font=ctk.CTkFont("Microsoft YaHei UI", 11, "bold"),
            text_color=self.colors["thought_text"],
        )
        t_lbl.grid(row=0, column=0, sticky="w")

        done_badge = ctk.CTkLabel(
            hdr, text="✓ Done", font=ctk.CTkFont("Microsoft YaHei UI", 10, "bold"),
            text_color=self.colors["accent_emerald"],
        )
        done_badge.grid(row=0, column=1, padx=10, sticky="w")

        body_box = ctk.CTkTextbox(
            card, height=120, wrap="word", corner_radius=6,
            fg_color=self.colors["bg_root"], border_width=0,
            text_color=self.colors["text_secondary"], font=ctk.CTkFont("Consolas", 11),
        )
        body_box.grid(row=1, column=0, padx=12, pady=(0, 10), sticky="ew")
        body_box.insert("1.0", reasoning_text.strip())
        self._make_readonly_selectable(body_box)

        def toggle():
            if body_box.winfo_viewable():
                body_box.grid_remove()
            else:
                body_box.grid()

        t_btn = ctk.CTkButton(
            hdr, text="折叠/展开", width=62, height=22, corner_radius=5,
            fg_color="transparent", border_width=1, border_color=self.colors["border"],
            hover_color=self.colors["card_hover"], text_color=self.colors["text_muted"],
            font=ctk.CTkFont("Microsoft YaHei UI", 9),
            command=toggle,
        )
        t_btn.grid(row=0, column=2, sticky="e")

        if hasattr(self.chat, "_parent_canvas"):
            self.chat._parent_canvas.yview_moveto(1.0)

    def _append_chat(self, role: str, text: str) -> None:
        """Append a modern message bubble to the scrollable chat stream."""
        is_user = role in {"you", "你"}
        is_system = role in {"system", "系统", "撤销", "验证", "保存", "导出", "Goal", "错误"}
        bubble_bg = self.colors["user_bg"] if is_user else (self.colors["system_bg"] if is_system else self.colors["assistant_bg"])
        bubble_fg = self.colors["user_text"] if is_user else (self.colors["text_primary"] if not is_system else "#93c5fd")
        label = "你" if is_user else ("小朴" if role in {"小朴", "assistant"} else role)

        row = ctk.CTkFrame(self.chat, fg_color="transparent")
        row._xiaopu_bubble = True
        row.grid(sticky="e" if is_user else ("ew" if is_system else "w"), padx=6, pady=6)
        row.grid_columnconfigure(0, weight=1)
        row.grid_columnconfigure(1, weight=1)

        card = ctk.CTkFrame(
            row, corner_radius=14, fg_color=bubble_bg,
            border_width=1, border_color=self.colors["border"],
        )
        if is_system:
            card.grid(row=0, column=0, columnspan=2, sticky="ew", padx=24)
        else:
            card.grid(row=0, column=1 if is_user else 0, sticky="e" if is_user else "w")

        card.grid_columnconfigure(0, weight=1)

        # Header row with role tag, icon, and copy button
        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.grid(row=0, column=0, padx=14, pady=(8, 2), sticky="ew")
        hdr.grid_columnconfigure(0, weight=1)

        tag_frame = ctk.CTkFrame(hdr, fg_color="transparent")
        tag_frame.grid(row=0, column=0, sticky="w")

        if not is_user and not is_system:
            if getattr(self, "_app_icon_small", None) is not None:
                ctk.CTkLabel(tag_frame, text="", image=self._app_icon_small).pack(side="left", padx=(0, 6))
            else:
                badge = ctk.CTkFrame(tag_frame, width=16, height=16, corner_radius=4, fg_color=self.colors["accent_blue"])
                badge.pack(side="left", padx=(0, 6))
                badge.pack_propagate(False)
                ctk.CTkLabel(
                    badge, text="朴", font=ctk.CTkFont("Microsoft YaHei UI", 9, "bold"),
                    text_color="#ffffff",
                ).place(relx=0.5, rely=0.5, anchor="center")

        tag_color = self.colors["accent_emerald"] if is_user else (self.colors["accent_blue"] if is_system else self.colors["accent"])
        ctk.CTkLabel(
            tag_frame, text=label, font=ctk.CTkFont("Microsoft YaHei UI", 11, "bold"),
            text_color=tag_color,
        ).pack(side="left")

        if not is_system:
            ctk.CTkButton(
                hdr, text="复制", width=38, height=20, corner_radius=5,
                fg_color="transparent", border_width=1, border_color=self.colors["border"],
                hover_color=self.colors["card_hover"], text_color=self.colors["text_muted"],
                font=ctk.CTkFont("Microsoft YaHei UI", 9),
                command=lambda t=text: self._copy_text(t),
            ).grid(row=0, column=1, sticky="e")

        # Message body
        body = ctk.CTkLabel(
            card, text=text, justify="left", anchor="w",
            wraplength=680, font=ctk.CTkFont("Microsoft YaHei UI", 13),
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
            self.activity.grid_remove()
            self.activity_visible = False
            self.activity_btn.configure(fg_color=self.colors["card_bg"], text_color=self.colors["text_secondary"])
        else:
            self.activity.grid(row=0, column=2, sticky="nsew")
            self.activity_visible = True
            self.activity_btn.configure(fg_color=self.colors["accent"], text_color="#ffffff")

    def _toggle_sidebar(self) -> None:
        if self.sidebar_visible:
            self.sidebar.grid_remove()
            self.sidebar_visible = False
        else:
            self.sidebar.grid(row=0, column=0, sticky="nsew")
            self.sidebar_visible = True

    def _toggle_theme(self) -> None:
        new_theme = "light" if self.theme_name == "dark" else "dark"
        self.theme_name = new_theme
        config.set_theme(new_theme)
        self.colors = THEMES[new_theme]
        ctk.set_appearance_mode(new_theme)
        self.status.set(f"已切换主题为：{new_theme}")

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
            # If we had reasoning stream, append the Thought process block first!
            if self._reasoning_text.strip():
                self._append_thought_block(self._reasoning_text)
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
            if self._reasoning_text.strip():
                self._append_thought_block(self._reasoning_text)
            self._append_chat("小朴", reply)

    def _show_event(self, event) -> None:
        p = getattr(event, "payload", {})
        kind = getattr(event, "kind", None)
        if kind == EventKind.TURN_STARTED:
            if hasattr(self, "live_action"):
                self.live_action.set("正在分析任务并选择路线…")
            if hasattr(self, "live_phase"):
                self.live_phase.set("Phase: intake")
            self._reasoning_text = ""
            self._trajectory = []
            self._refresh_status()
            return
        if kind == EventKind.CONTROLLER_DECISION:
            if hasattr(self, "live_action"):
                self.live_action.set(f"决策：{p.get('action', 'planning')}")
            if hasattr(self, "live_phase"):
                self.live_phase.set(f"Phase: {p.get('phase', '—')}")
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
                self.live_phase.set(f"Phase: {p.get('stage', '—')}")
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
                self.live_phase.set(f"Phase: {p.get('to_phase', '—')}")
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
                self.live_phase.set("Phase: intake")
            self._refresh_counts()
        else:
            self.started_at = None
            if hasattr(self, "live_action"):
                self.live_action.set("就绪 · 等待指令")
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
        if hasattr(self, "current_title") and self.current_title.get() == "新对话":
            self.current_title.set(task[:18] + ("…" if len(task) > 18 else ""))
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

    # ------------------------------------------------------------------ Dialog Actions
    def _show_goal_dialog(self) -> None:
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("长期目标管理 (Goal)")
        dialog.geometry("480x260")
        dialog.transient(self.root)

        ctk.CTkLabel(dialog, text="🎯 长期目标设定与查看", font=ctk.CTkFont("Microsoft YaHei UI", 13, "bold")).pack(pady=(14, 6))
        entry = ctk.CTkEntry(dialog, width=420, placeholder_text="输入目标描述，例如：全套产品发布会 PPT 制作")
        entry.pack(pady=8)

        def on_start():
            val = entry.get().strip()
            if val:
                try:
                    res = self.h.start_goal(val)
                    self._append_chat("Goal", res)
                    dialog.destroy()
                except Exception as exc:
                    messagebox.showerror("启动失败", str(exc))

        def on_view():
            try:
                summary = self.h.goal_summary()
                messagebox.showinfo("当前目标", summary)
            except Exception as exc:
                messagebox.showerror("获取失败", str(exc))

        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack(pady=12)
        ctk.CTkButton(btn_row, text="启动新目标", command=on_start, width=100, fg_color=self.colors["accent"]).pack(side="left", padx=6)
        ctk.CTkButton(btn_row, text="查看当前状态", command=on_view, width=100).pack(side="left", padx=6)

    def _start_goal(self) -> None:
        self._show_goal_dialog()

    def _show_goal(self) -> None:
        try:
            summary = self.h.goal_summary()
            messagebox.showinfo("长期目标状态", summary)
        except Exception as exc:
            messagebox.showerror("获取 Goal 失败", str(exc))

    def _show_doctor_dialog(self) -> None:
        from .doctor import report
        data = report()
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("小朴 · 环境诊断 (Doctor)")
        dialog.geometry("520x360")
        dialog.transient(self.root)

        ctk.CTkLabel(dialog, text="⚙ 环境与依赖诊断报告", font=ctk.CTkFont("Microsoft YaHei UI", 13, "bold")).pack(pady=(12, 6))
        box = ctk.CTkTextbox(dialog, wrap="word", font=ctk.CTkFont("Consolas", 11))
        box.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        box.insert("1.0", json.dumps(data, indent=2, ensure_ascii=False))
        self._make_readonly_selectable(box)

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
        self.current_title.set("新对话")
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
                text_color=self.colors["text_muted"],
            ).grid(row=0, column=0, pady=16)
            return

        for index, record in enumerate(self._session_records[:50]):
            card = ctk.CTkFrame(
                self.session_frame, corner_radius=8, fg_color=self.colors["card_bg"],
                border_width=1, border_color=self.colors["border"],
            )
            card.grid(row=index, column=0, padx=4, pady=3, sticky="ew")
            card.grid_columnconfigure(0, weight=1)

            title_text = record.title[:20] + ("…" if len(record.title) > 20 else "")
            time_text = record.updated_at[:16] if getattr(record, "updated_at", None) else ""

            btn_content = f"💬  {title_text}\n     {time_text}" if time_text else f"💬  {title_text}"
            ctk.CTkButton(
                card, text=btn_content, anchor="w",
                height=36, corner_radius=6, fg_color="transparent",
                hover_color=self.colors["card_hover"], text_color=self.colors["text_primary"],
                font=ctk.CTkFont("Microsoft YaHei UI", 11),
                command=lambda i=index: self._resume_session(i),
            ).grid(row=0, column=0, sticky="ew", padx=4, pady=2)

            ctk.CTkButton(
                card, text="✕", width=22, height=22, corner_radius=5,
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
        self.current_title.set(record.title[:18] + ("…" if len(record.title) > 18 else ""))
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
