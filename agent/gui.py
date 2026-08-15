"""Native Windows GUI for the complete Xiaopu Harness."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import config
from .events import EventKind
from .tools.registry import dispatch


class AgentGUI:
    def __init__(self, root: tk.Tk, model: str | None = None) -> None:
        from .harness import Harness

        self.root = root
        self.model = model
        self.h = Harness(model=model, interactive=True)
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.approvals: queue.Queue = queue.Queue()
        self.running = False
        self.process_visible = tk.BooleanVar(value=True)
        self.detail_visible = tk.BooleanVar(value=True)
        self.tool_rows: dict[str, str] = {}
        self.tool_payloads: dict[str, dict] = {}
        self.status = tk.StringVar(value="就绪")
        self.live_action = tk.StringVar(value="等待任务")
        self.live_phase = tk.StringVar(value="阶段：—")
        self.live_elapsed = tk.StringVar(value="0 秒")
        self.live_counts = tk.StringVar(value="工具 0 · 完成 0 · 失败 0")
        self.model_var = tk.StringVar(value=getattr(self.h.llm, "model", config.model()))
        self.theme_var = tk.StringVar(value=config.theme())
        self.permissions_var = tk.StringVar(value=config.command_policy())
        self.started_at = None
        self.tool_started_count = self.tool_completed_count = self.tool_failed_count = 0
        self.workspace = tk.StringVar(value=str(config.sandbox_root()))
        self._streaming_started = False
        self.h.approval_handler = self._approve_command
        self.h.stream_callback = self._on_stream_token
        self.h.subscribe(self._capture_runtime_event)
        self._build()
        from .workspace_store import register_workspace
        try:
            register_workspace(self.workspace.get())
        except Exception:
            pass
        self._refresh_sessions()
        self._refresh_workspaces()
        self.root.after(60, self._drain_events)
        self.root.after(120, self._drain_approvals)
        self.root.after(250, self._tick_elapsed)
        self._refresh_status()

    def _build(self) -> None:
        self.root.title("小朴 Agent")
        self.root.geometry("1180x780")
        self.root.minsize(820, 560)
        self.root.configure(bg="#111111")
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TFrame", background="#111111")
        style.configure("TLabel", background="#111111", foreground="#e8e8e8")
        style.configure("TButton", padding=(12, 7))

        top = ttk.Frame(self.root, padding=(14, 10))
        top.pack(fill="x")
        ttk.Label(top, text="小朴", font=("Microsoft YaHei UI", 18, "bold")).pack(side="left")
        ttk.Label(top, text="  通用 Agent · PowerPoint 强化", foreground="#999999").pack(side="left")
        ttk.Label(top, text="模型 ").pack(side="left", padx=(18, 0))
        self.model_box = ttk.Combobox(top, textvariable=self.model_var, values=config.known_models(), width=20, state="readonly")
        self.model_box.pack(side="left")
        self.model_box.bind("<<ComboboxSelected>>", self._switch_model)
        ttk.Label(top, text=" 主题 ").pack(side="left", padx=(10, 0))
        self.theme_box = ttk.Combobox(top, textvariable=self.theme_var, values=list(config.THEMES), width=8, state="readonly")
        self.theme_box.pack(side="left")
        self.theme_box.bind("<<ComboboxSelected>>", self._switch_theme)
        ttk.Label(top, text=" 权限 ").pack(side="left", padx=(10, 0))
        self.permissions_box = ttk.Combobox(top, textvariable=self.permissions_var, values=("allow", "ask", "deny"), width=6, state="readonly")
        self.permissions_box.pack(side="left")
        self.permissions_box.bind("<<ComboboxSelected>>", self._switch_permissions)
        ttk.Button(top, text="导出", command=self._export_session).pack(side="right")
        ttk.Button(top, text="撤销", command=self._undo).pack(side="right", padx=5)
        ttk.Button(top, text="选择工作区", command=self._choose_workspace).pack(side="right")
        ttk.Button(top, text="保存 PPT", command=self._save_ppt).pack(side="right", padx=5)
        ttk.Button(top, text="验证", command=self._verify).pack(side="right")
        ttk.Button(top, text="新会话", command=self._new_session).pack(side="right", padx=5)

        workspace = ttk.Frame(self.root, padding=(14, 0, 14, 8))
        workspace.pack(fill="x")
        ttk.Label(workspace, text="工作区  ").pack(side="left")
        ttk.Label(workspace, textvariable=self.workspace, foreground="#8fbcbb").pack(side="left")

        live = ttk.Frame(self.root, padding=(14, 7))
        live.pack(fill="x")
        ttk.Label(live, text="●", foreground="#73c991").pack(side="left")
        ttk.Label(live, textvariable=self.live_action, font=("Microsoft YaHei UI", 10, "bold")).pack(side="left", padx=(6, 16))
        ttk.Label(live, textvariable=self.live_phase, foreground="#9aa7b2").pack(side="left")
        ttk.Label(live, textvariable=self.live_counts, foreground="#777777").pack(side="right")
        ttk.Label(live, textvariable=self.live_elapsed, foreground="#9aa7b2").pack(side="right", padx=(0, 14))

        pane = ttk.Panedwindow(self.root, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=14)
        session_frame = ttk.Frame(pane)
        chat_frame = ttk.Frame(pane)
        process_frame = ttk.Frame(pane)
        pane.add(session_frame, weight=1)
        pane.add(chat_frame, weight=4)
        pane.add(process_frame, weight=2)

        # Sidebar: sessions and workspace management live together.
        sidebar = ttk.Notebook(session_frame)
        sidebar.pack(fill="both", expand=True)
        sessions_tab = ttk.Frame(sidebar)
        workspaces_tab = ttk.Frame(sidebar)
        sidebar.add(sessions_tab, text="会话")
        sidebar.add(workspaces_tab, text="工作区")

        ttk.Label(sessions_tab, text="已保存会话", font=("Microsoft YaHei UI", 10, "bold")).pack(anchor="w", pady=(0, 5))
        self.session_list = tk.Listbox(sessions_tab, bg="#151515", fg="#e8e8e8", selectbackground="#2867b2",
                                       relief="flat", activestyle="none", height=18)
        self.session_list.pack(fill="both", expand=True)
        session_buttons = ttk.Frame(sessions_tab)
        session_buttons.pack(fill="x", pady=(6, 0))
        ttk.Button(session_buttons, text="恢复", command=self._resume_session).pack(side="left")
        ttk.Button(session_buttons, text="删除", command=self._delete_session).pack(side="left", padx=(5, 0))
        ttk.Button(session_buttons, text="刷新", command=self._refresh_sessions).pack(side="left", padx=(5, 0))

        ttk.Label(workspaces_tab, text="工作区", font=("Microsoft YaHei UI", 10, "bold")).pack(anchor="w", pady=(0, 5))
        self.workspace_list = tk.Listbox(workspaces_tab, bg="#151515", fg="#e8e8e8", selectbackground="#2867b2",
                                         relief="flat", activestyle="none", height=18)
        self.workspace_list.pack(fill="both", expand=True)
        workspace_buttons = ttk.Frame(workspaces_tab)
        workspace_buttons.pack(fill="x", pady=(6, 0))
        ttk.Button(workspace_buttons, text="添加", command=self._add_workspace).pack(side="left")
        ttk.Button(workspace_buttons, text="切换", command=self._switch_workspace).pack(side="left", padx=(5, 0))
        ttk.Button(workspace_buttons, text="移除", command=self._remove_workspace).pack(side="left", padx=(5, 0))

        ttk.Label(chat_frame, text="对话", font=("Microsoft YaHei UI", 11, "bold")).pack(anchor="w", pady=(0, 5))
        self.chat = tk.Text(chat_frame, wrap="word", bg="#151515", fg="#ededed", insertbackground="white",
                            selectbackground="#2867b2", selectforeground="#ffffff", exportselection=True,
                            relief="flat", padx=14, pady=12, font=("Microsoft YaHei UI", 11))
        self.chat.pack(fill="both", expand=True)
        self._make_readonly_selectable(self.chat)
        self.chat.tag_configure("user", foreground="#ffffff", background="#303030", spacing1=8, spacing3=8)
        self.chat.tag_configure("assistant", foreground="#e7e7e7", spacing1=8, spacing3=8)
        self.chat.tag_configure("error", foreground="#ff8a80")

        process_header = ttk.Frame(process_frame)
        process_header.pack(fill="x", padx=(10, 0), pady=(0, 5))
        ttk.Label(process_header, text="过程与证据", font=("Microsoft YaHei UI", 11, "bold")).pack(side="left")
        ttk.Checkbutton(process_header, text="显示", variable=self.process_visible).pack(side="right")
        self.process_tabs = ttk.Notebook(process_frame)
        self.process_tabs.pack(fill="both", expand=True, padx=(10, 0))
        plan_tab = ttk.Frame(self.process_tabs)
        tools_tab = ttk.Frame(self.process_tabs)
        signal_tab = ttk.Frame(self.process_tabs)
        self.process_tabs.add(plan_tab, text="计划")
        self.process_tabs.add(tools_tab, text="工具")
        self.process_tabs.add(signal_tab, text="推理信号")
        self.process = tk.Text(plan_tab, wrap="word", bg="#0f0f0f", fg="#b9c7d5", relief="flat",
                               selectbackground="#2867b2", selectforeground="#ffffff", exportselection=True,
                               padx=12, pady=10, font=("Microsoft YaHei UI", 9))
        self.process.pack(fill="both", expand=True)
        self._make_readonly_selectable(self.process)
        self.tool_tree = ttk.Treeview(tools_tab, columns=("status", "tool"), show="headings", height=10)
        self.tool_tree.heading("status", text="状态")
        self.tool_tree.heading("tool", text="工具")
        self.tool_tree.column("status", width=62, stretch=False)
        self.tool_tree.column("tool", width=190)
        self.tool_tree.pack(fill="both", expand=True)
        self.tool_tree.bind("<<TreeviewSelect>>", self._select_tool)
        detail_bar = ttk.Frame(tools_tab)
        detail_bar.pack(fill="x")
        ttk.Checkbutton(detail_bar, text="展开详情", variable=self.detail_visible,
                        command=self._toggle_tool_detail).pack(side="left")
        self.tool_detail = tk.Text(tools_tab, wrap="word", height=9, bg="#0f0f0f", fg="#c7c7c7",
                                   selectbackground="#2867b2", selectforeground="#ffffff", exportselection=True,
                                   relief="flat", padx=10, pady=8, font=("Consolas", 9))
        self.tool_detail.pack(fill="x")
        self._make_readonly_selectable(self.tool_detail)
        self.signal = tk.Text(signal_tab, wrap="word", bg="#0f0f0f", fg="#aaa7c8", relief="flat",
                              selectbackground="#2867b2", selectforeground="#ffffff", exportselection=True,
                              padx=12, pady=10, font=("Microsoft YaHei UI", 9))
        self.signal.pack(fill="both", expand=True)
        self._make_readonly_selectable(self.signal)
        self._append(self.signal, "这里显示模型实际返回的推理信号状态和可审计摘要。\n"
                                  "不会伪造或展示模型未提供的私有思维链。")

        goal = ttk.Frame(self.root, padding=(14, 9, 14, 4))
        goal.pack(fill="x")
        ttk.Label(goal, text="长期目标").pack(side="left")
        self.goal_entry = ttk.Entry(goal)
        self.goal_entry.pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(goal, text="启动 Goal", command=self._start_goal).pack(side="left")
        ttk.Button(goal, text="查看", command=self._show_goal).pack(side="left", padx=(5, 0))

        composer = ttk.Frame(self.root, padding=(14, 6))
        composer.pack(fill="x")
        self.input = tk.Text(composer, height=5, wrap="word", bg="#262626", fg="#ffffff", insertbackground="white",
                             relief="flat", padx=12, pady=10, font=("Microsoft YaHei UI", 11))
        self.input.pack(side="left", fill="x", expand=True)
        self.input.bind("<Control-Return>", lambda _e: self._send() or "break")
        buttons = ttk.Frame(composer)
        buttons.pack(side="left", fill="y", padx=(8, 0))
        self.send = ttk.Button(buttons, text="发送  Ctrl+Enter", command=self._send)
        self.send.pack(fill="x")
        self.stop = ttk.Button(buttons, text="中断", command=self._cancel, state="disabled")
        self.stop.pack(fill="x", pady=(7, 0))

        bottom = ttk.Frame(self.root, padding=(14, 0, 14, 10))
        bottom.pack(fill="x")
        ttk.Label(bottom, textvariable=self.status).pack(side="left")
        ttk.Label(bottom, textvariable=self.model_var, foreground="#777777").pack(side="right")
        ttk.Label(bottom, text=f"{config.provider()} · ", foreground="#777777").pack(side="right")
        self._append_chat("小朴", "已就绪。输入一句任务，或先启动长期 Goal。", "assistant")

    def _append(self, widget: tk.Text, text: str, tag: str | None = None) -> None:
        widget.insert("end", text + "\n", tag)
        widget.see("end")

    @staticmethod
    def _make_readonly_selectable(widget: tk.Text) -> None:
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

    def _switch_theme(self, _event=None) -> None:
        config.set_theme(self.theme_var.get())
        self._apply_theme()

    def _apply_theme(self) -> None:
        palettes = {
            "dark": {"bg": "#111111", "text_bg": "#151515", "input_bg": "#262626", "fg": "#ededed"},
            "light": {"bg": "#f2f2f2", "text_bg": "#ffffff", "input_bg": "#ffffff", "fg": "#111111"},
            "dracula": {"bg": "#282a36", "text_bg": "#282a36", "input_bg": "#44475a", "fg": "#f8f8f2"},
        }
        p = palettes.get(self.theme_var.get(), palettes["dark"])
        self.root.configure(bg=p["bg"])
        style = ttk.Style(self.root)
        style.configure("TFrame", background=p["bg"])
        style.configure("TLabel", background=p["bg"], foreground=p["fg"])
        for widget in (self.chat, self.process, self.tool_detail, self.signal):
            widget.configure(bg=p["text_bg"], fg=p["fg"], insertbackground=p["fg"])
        self.input.configure(bg=p["input_bg"], fg=p["fg"], insertbackground=p["fg"])

    def _switch_permissions(self, _event=None) -> None:
        os.environ["COMMAND_POLICY"] = self.permissions_var.get()
        self.status.set(f"Shell 策略：{self.permissions_var.get()}")

    def _undo(self) -> None:
        self._append_chat("撤销", self.h.undo(), "assistant")

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

    def _refresh_sessions(self) -> None:
        from .session_store import list_sessions

        self.session_list.delete(0, "end")
        self._session_records = list_sessions()
        for record in self._session_records:
            self.session_list.insert("end", f"{record.id[:8]} · {record.title[:32]}")

    def _resume_session(self) -> None:
        selection = self.session_list.curselection()
        if not selection:
            return
        from .session_store import load_session, restore_harness

        record = self._session_records[selection[0]]
        payload = load_session(record.id)
        if payload is None:
            messagebox.showerror("恢复失败", "会话文件不可用。")
            return
        report = restore_harness(self.h, payload)
        self._append_chat("系统", report, "assistant")
        self._refresh_status()

    def _delete_session(self) -> None:
        selection = self.session_list.curselection()
        if not selection:
            return
        from .session_store import delete_session

        record = self._session_records[selection[0]]
        if messagebox.askyesno("删除会话", f"删除会话 {record.id[:8]}？此操作不可撤销。"):
            delete_session(record.id)
            self._refresh_sessions()

    def _refresh_status(self) -> None:
        state = self.h.state
        fresh = len(state.fresh_evidence())
        self.status.set(
            f"{state.phase.value} · epoch {state.mutation_epoch} · 证据 {fresh} · "
            f"tokens {state.total_tokens} · repair {state.repair_attempts}/{state.max_repairs}"
        )

    def _capture_runtime_event(self, event) -> None:
        self.events.put(("runtime", event))

    def _drain_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "result":
                    if self._streaming_started:
                        self._streaming_started = False
                        self._append(self.chat, "\n" + str(payload) + "\n", "assistant")
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
                    self.chat.insert("end", str(payload), "assistant")
                    self.chat.see("end")
                elif kind == "runtime":
                    self._show_event(payload)
        except queue.Empty:
            pass
        self.root.after(60, self._drain_events)

    def _show_event(self, event) -> None:
        if not self.process_visible.get():
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
            self._upsert_tool(p, "运行中")
            return
        elif event.kind == EventKind.TOOL_COMPLETED:
            self.tool_completed_count += 1
            self._refresh_counts()
            self.live_action.set(f"{p.get('tool', '工具')} 已完成，正在处理结果…")
            self._upsert_tool(p, "完成")
            return
        elif event.kind == EventKind.TOOL_FAILED:
            self.tool_failed_count += 1
            self._refresh_counts()
            self.live_action.set(f"{p.get('tool', '工具')} 失败，正在调整路线…")
            self._upsert_tool(p, "失败")
            return
        elif event.kind == EventKind.MODEL_RESPONSE:
            chars = int(p.get("reasoning_chars", 0) or 0)
            self.live_action.set("模型已返回，正在执行工具…" if p.get("tool_call_count") else "正在检查完成条件…")
            self._append(self.signal, f"模型响应 · 推理信号 {chars} 字符 · "
                                      f"工具请求 {p.get('tool_call_count', 0)} 个\n")
            return
        elif event.kind == EventKind.PHASE_CHANGED:
            line = f"阶段 · {p.get('from_phase')} → {p.get('to_phase')}"
            self.live_phase.set(f"阶段：{p.get('to_phase', '—')}")
        else:
            return
        self._append(self.process, line + "\n")

    def _upsert_tool(self, payload: dict, status: str) -> None:
        call_id = str(payload.get("call_id", ""))
        tool = str(payload.get("tool", "未知工具"))
        row = self.tool_rows.get(call_id)
        if row:
            self.tool_tree.item(row, values=(status, tool))
        else:
            row = self.tool_tree.insert("", "end", values=(status, tool))
            self.tool_rows[call_id] = row
        existing = self.tool_payloads.setdefault(call_id, {})
        existing.update(payload)
        existing["status"] = status
        existing["tool"] = tool
        if self.tool_tree.selection() == (row,):
            self._render_tool_detail(existing)

    def _select_tool(self, _event=None) -> None:
        selection = self.tool_tree.selection()
        if not selection:
            return
        row = selection[0]
        call_id = next((key for key, value in self.tool_rows.items() if value == row), "")
        self._render_tool_detail(self.tool_payloads.get(call_id, {}))

    def _render_tool_detail(self, payload: dict) -> None:
        arguments = payload.get("arguments", "")
        try:
            arguments = json.dumps(json.loads(arguments), ensure_ascii=False, indent=2)
        except Exception:
            arguments = str(arguments)
        sections = [f"工具：{payload.get('tool', '')}", f"状态：{payload.get('status', '')}"]
        if arguments:
            sections.append("参数：\n" + arguments)
        if payload.get("output"):
            sections.append("结果：\n" + str(payload["output"]))
        if payload.get("error"):
            sections.append("错误：\n" + str(payload["error"]))
        self.tool_detail.delete("1.0", "end")
        self.tool_detail.insert("end", "\n\n".join(sections))

    def _toggle_tool_detail(self) -> None:
        if self.detail_visible.get():
            self.tool_detail.pack(fill="x")
        else:
            self.tool_detail.pack_forget()

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
        self._refresh_status()

    def _verify(self) -> None:
        try:
            result = dispatch("ppt_check", json.dumps({"scope": "affected"}), self.h)
            self._append_chat("验证", result, "assistant")
        except Exception as exc:
            messagebox.showerror("验证失败", str(exc))

    def _save_ppt(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".pptx", filetypes=[("PowerPoint", "*.pptx")])
        if path:
            try:
                result = dispatch("ppt_save", json.dumps({"path": path, "role": "final"}), self.h)
                self._append_chat("保存", result, "assistant")
            except Exception as exc:
                messagebox.showerror("保存失败", str(exc))

    def _refresh_workspaces(self) -> None:
        from .workspace_store import list_workspaces

        self.workspace_list.delete(0, "end")
        self._workspace_records = list_workspaces()
        current = str(Path(self.workspace.get()).resolve())
        for index, record in enumerate(self._workspace_records):
            marker = "● " if Path(record.path) == Path(current) else "  "
            self.workspace_list.insert("end", f"{marker}{record.name} · {record.path}")

    def _add_workspace(self) -> None:
        from .workspace_store import register_workspace

        path = filedialog.askdirectory(initialdir=self.workspace.get())
        if not path:
            return
        try:
            register_workspace(path)
        except ValueError as exc:
            messagebox.showerror("添加工作区失败", str(exc))
            return
        self._refresh_workspaces()

    def _switch_workspace(self) -> None:
        selection = self.workspace_list.curselection()
        if not selection:
            messagebox.showinfo("切换工作区", "请先在列表中选择一个工作区。")
            return
        record = self._workspace_records[selection[0]]
        if Path(record.path) == Path(self.workspace.get()).resolve():
            return
        if self.running:
            messagebox.showinfo("切换工作区", "当前任务执行中，请先中断。")
            return
        if messagebox.askyesno("切换工作区", f"切换将保存当前会话并进入：\n{record.path}\n\n是否继续？"):
            from .session_store import save_session
            save_session(self.h)
            self._replace_harness(record.path)

    def _remove_workspace(self) -> None:
        selection = self.workspace_list.curselection()
        if not selection:
            return
        record = self._workspace_records[selection[0]]
        if Path(record.path) == Path(self.workspace.get()).resolve():
            messagebox.showinfo("移除工作区", "当前使用中的工作区不能移除，请先切换到其他工作区。")
            return
        if messagebox.askyesno("移除工作区", f"从管理列表移除：\n{record.path}\n\n（磁盘目录不会被删除）"):
            from .workspace_store import remove_workspace
            remove_workspace(record.path)
            self._refresh_workspaces()

    def _replace_harness(self, path: str) -> None:
        from .harness import Harness

        os.environ["WORKSPACE"] = str(Path(path).resolve())
        self.h = Harness(model=self.model, interactive=True)
        self.h.approval_handler = self._approve_command
        self.h.stream_callback = self._on_stream_token
        self.h.subscribe(self._capture_runtime_event)
        self.workspace.set(os.environ["WORKSPACE"])
        self.model_var.set(getattr(self.h.llm, "model", config.model()))
        self._append_chat("系统", f"已切换工作区：{path}", "assistant")
        self._refresh_sessions()
        self._refresh_workspaces()
        self._refresh_status()

    def _choose_workspace(self) -> None:
        if self.running:
            return
        path = filedialog.askdirectory(initialdir=self.workspace.get())
        if not path:
            return
        if not messagebox.askyesno("切换工作区", "切换将保存当前会话并创建新的会话，是否继续？"):
            return
        from .session_store import save_session
        from .workspace_store import register_workspace

        save_session(self.h)
        register_workspace(path)
        self._replace_harness(path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-gui", description="Launch the native Xiaopu Agent window.")
    parser.add_argument("--workspace")
    parser.add_argument("--model")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.workspace:
        workspace = Path(args.workspace).expanduser().resolve()
        if not workspace.is_dir():
            build_parser().error(f"workspace does not exist: {workspace}")
        os.environ["WORKSPACE"] = str(workspace)
    root = tk.Tk()
    AgentGUI(root, model=args.model)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
