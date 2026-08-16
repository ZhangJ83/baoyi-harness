"""Lightweight Web GUI Server for Xiaopu Harness.

Serves the modern Claude Desktop / Cowork-inspired HTML5/CSS3 frontend and provides
REST + SSE (Server-Sent Events) APIs for real-time streaming, tool calls, and workspace session management.
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import ctypes
from ctypes import wintypes
from typing import Any


class _BROWSEINFOW(ctypes.Structure):
    _fields_ = [
        ("hwndOwner", wintypes.HWND),
        ("pidlRoot", ctypes.c_void_p),
        ("pszDisplayName", wintypes.LPWSTR),
        ("lpszTitle", wintypes.LPCWSTR),
        ("ulFlags", wintypes.UINT),
        ("lpfn", ctypes.c_void_p),
        ("lParam", wintypes.LPARAM),
        ("iImage", ctypes.c_int),
    ]


class _OPENFILENAMEW(ctypes.Structure):
    _fields_ = [
        ("lStructSize", wintypes.DWORD),
        ("hwndOwner", wintypes.HWND),
        ("hInstance", wintypes.HINSTANCE),
        ("lpstrFilter", wintypes.LPCWSTR),
        ("lpstrCustomFilter", wintypes.LPWSTR),
        ("nMaxCustFilter", wintypes.DWORD),
        ("nFilterIndex", wintypes.DWORD),
        ("lpstrFile", wintypes.LPWSTR),
        ("nMaxFile", wintypes.DWORD),
        ("lpstrFileTitle", wintypes.LPWSTR),
        ("nMaxFileTitle", wintypes.DWORD),
        ("lpstrInitialDir", wintypes.LPCWSTR),
        ("lpstrTitle", wintypes.LPCWSTR),
        ("Flags", wintypes.DWORD),
        ("nFileOffset", wintypes.WORD),
        ("nFileExtension", wintypes.WORD),
        ("lpstrDefExt", wintypes.LPCWSTR),
        ("lCustData", wintypes.LPARAM),
        ("lpfnHook", ctypes.c_void_p),
        ("lpTemplateName", wintypes.LPCWSTR),
        ("pvReserved", ctypes.c_void_p),
        ("dwReserved", wintypes.DWORD),
        ("FlagsEx", wintypes.DWORD),
    ]


def _pick_directory_native(initial_dir: str = "") -> str | None:
    # 1. On Windows, use Win32 SHBrowseForFolderW (zero subprocess, zero PowerShell, zero Tkinter)
    if sys.platform == "win32":
        try:
            ole32 = ctypes.windll.ole32
            ole32.CoInitialize(None)
            shell32 = ctypes.windll.shell32

            display_name = ctypes.create_unicode_buffer(260)
            bi = _BROWSEINFOW()
            bi.hwndOwner = None
            bi.pidlRoot = None
            bi.pszDisplayName = ctypes.cast(display_name, wintypes.LPWSTR)
            bi.lpszTitle = "请选择小朴项目 / 工作区目录"
            # BIF_RETURNONLYFSDIRS (0x1) | BIF_NEWDIALOGSTYLE (0x40) | BIF_USENEWUI (0x50)
            bi.ulFlags = 0x00000040 | 0x00000010 | 0x00000001

            pidl = shell32.SHBrowseForFolderW(ctypes.byref(bi))
            if pidl:
                path_buf = ctypes.create_unicode_buffer(1024)
                if shell32.SHGetPathFromIDListW(pidl, path_buf):
                    ole32.CoTaskMemFree(pidl)
                    ole32.CoUninitialize()
                    res_path = path_buf.value
                    if res_path and Path(res_path).is_dir():
                        return str(Path(res_path).resolve())
                ole32.CoTaskMemFree(pidl)
            ole32.CoUninitialize()
        except Exception:
            pass

    # 2. Cross-platform Tkinter fallback
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selected = filedialog.askdirectory(title="选择工作区/项目目录", initialdir=initial_dir or str(config.sandbox_root()))
        root.destroy()
        if selected and Path(selected).is_dir():
            return str(Path(selected).resolve())
    except Exception:
        pass

    return None


def _pick_save_file_native(initial_dir: str = "", default_name: str = "presentation.pptx") -> str | None:
    # 1. On Windows, use Win32 GetSaveFileNameW
    if sys.platform == "win32":
        try:
            ofn = _OPENFILENAMEW()
            ofn.lStructSize = ctypes.sizeof(_OPENFILENAMEW)
            file_buf = ctypes.create_unicode_buffer(1024)
            if default_name:
                file_buf.value = default_name
            ofn.lpstrFile = ctypes.cast(file_buf, wintypes.LPWSTR)
            ofn.nMaxFile = 1024
            ofn.lpstrFilter = "PowerPoint 演示文稿 (*.pptx)\0*.pptx\0所有文件 (*.*)\0*.*\0\0"
            ofn.lpstrTitle = "另存为 PPT 文件"
            ofn.lpstrDefExt = "pptx"
            if initial_dir:
                ofn.lpstrInitialDir = initial_dir
            ofn.Flags = 0x00000002 | 0x00000800  # OFN_OVERWRITEPROMPT | OFN_PATHMUSTEXIST
            if ctypes.windll.comdlg32.GetSaveFileNameW(ctypes.byref(ofn)):
                res_path = file_buf.value
                if res_path:
                    return str(Path(res_path).resolve())
        except Exception:
            pass

    # 2. Cross-platform Tkinter fallback
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selected = filedialog.asksaveasfilename(
            title="另存为 PPT 文件",
            defaultextension=".pptx",
            filetypes=[("PowerPoint", "*.pptx")],
            initialdir=initial_dir or str(config.sandbox_root()),
            initialfile=default_name,
        )
        root.destroy()
        if selected:
            return str(Path(selected).resolve())
    except Exception:
        pass

    return None


def _time_ago(iso_str: str) -> str:
    if not iso_str:
        return "now"
    try:
        dt = datetime.fromisoformat(iso_str)
        now = datetime.now(timezone.utc)
        diff = now - dt
        seconds = max(0, int(diff.total_seconds()))
        if seconds < 60:
            return "now"
        elif seconds < 3600:
            return f"{seconds // 60}m"
        elif seconds < 86400:
            return f"{seconds // 3600}h"
        elif seconds < 2592000:
            return f"{seconds // 86400}d"
        elif seconds < 31536000:
            return f"{seconds // 2592000}mo"
        else:
            return f"{seconds // 31536000}y"
    except Exception:
        return "now"

from . import config
from .events import EventKind, RuntimeEvent
from .harness import Harness
from .session_store import (
    delete_session,
    export_session,
    list_sessions,
    load_session,
    restore_harness,
    save_session,
)
from .tools.registry import dispatch
from .workspace_store import list_workspaces, register_workspace

WEB_DIR = Path(__file__).resolve().parent / "web"
ASSETS_DIR = Path(__file__).resolve().parent / "assets"


class XiaopuWebHandler(BaseHTTPRequestHandler):
    harness: Harness = None  # Class-level shared harness instance
    active_stream_queue: queue.Queue | None = None

    def log_message(self, format, *args):
        # Suppress routine GET logging for clean console output
        pass

    def _send_json(self, data: Any, status: int = 200) -> None:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)

    def _send_file(self, file_path: Path, content_type: str) -> None:
        if not file_path.is_file():
            self.send_error(404, "File Not Found")
            return
        content = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _read_json_body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length <= 0:
                return {}
            body = self.rfile.read(length).decode("utf-8")
            return json.loads(body)
        except Exception:
            return {}

    def do_OPTIONS(self) -> None:
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # Static asset routing
        if path in {"/", "/index.html"}:
            self._send_file(WEB_DIR / "index.html", "text/html; charset=utf-8")
            return
        elif path == "/style.css":
            self._send_file(WEB_DIR / "style.css", "text/css; charset=utf-8")
            return
        elif path == "/app.js":
            self._send_file(WEB_DIR / "app.js", "application/javascript; charset=utf-8")
            return
        elif path == "/assets/icon.png":
            self._send_file(ASSETS_DIR / "icon.png", "image/png")
            return
        elif path == "/assets/icon.ico":
            self._send_file(ASSETS_DIR / "icon.ico", "image/x-icon")
            return

        # API routing
        if path == "/api/config":
            self._send_json({
                "known_models": config.known_models(),
                "current_model": getattr(self.harness.llm, "model", config.model()),
                "command_policy": config.command_policy(),
                "provider": config.provider(),
                "reasoning_effort": config.reasoning_effort(),
                "thinking_enabled": config.thinking_enabled(),
            })
            return

        if path == "/api/settings":
            raw_key = config.api_key()
            masked_key = (raw_key[:6] + "..." + raw_key[-4:]) if len(raw_key) > 10 else ("*" * len(raw_key))
            self._send_json({
                "provider": config.provider(),
                "api_base": config.api_base(),
                "api_key": raw_key,
                "masked_api_key": masked_key,
                "model": getattr(self.harness.llm, "model", config.model()),
                "known_models": config.known_models(),
                "models_csv": ",".join(config.known_models()),
                "reasoning_effort": config.reasoning_effort(),
                "command_policy": config.command_policy(),
            })
            return

        if path == "/api/workspaces":
            workspaces = []
            for w in list_workspaces():
                w_path = getattr(w, "path", str(w))
                if w_path and w_path not in workspaces:
                    workspaces.append(w_path)
            current = str(config.sandbox_root())
            if current not in workspaces:
                workspaces.insert(0, current)
            self._send_json({"workspaces": workspaces, "current": current})
            return

        if path == "/api/tree":
            current_ws = str(config.sandbox_root())
            known_workspaces = []

            # 1. Registered workspaces
            for w in list_workspaces():
                w_path = getattr(w, "path", str(w))
                if w_path and w_path not in known_workspaces:
                    try:
                        if Path(w_path).is_dir():
                            known_workspaces.append(str(Path(w_path).resolve()))
                    except Exception:
                        pass

            # 2. Current workspace
            try:
                curr_res = str(Path(current_ws).resolve())
                if curr_res not in known_workspaces:
                    known_workspaces.insert(0, curr_res)
            except Exception:
                if current_ws not in known_workspaces:
                    known_workspaces.insert(0, current_ws)

            # 3. Auto-discover valid workspaces from all historical sessions
            all_sessions = list_sessions()
            for s in all_sessions:
                if s.workspace:
                    try:
                        p = Path(s.workspace)
                        if p.is_dir():
                            resolved = str(p.resolve())
                            # Ignore temporary pytest directories
                            if "pytest-" not in resolved and "Temp" not in resolved:
                                if resolved not in known_workspaces:
                                    known_workspaces.append(resolved)
                    except Exception:
                        pass

            assigned_session_ids = set()
            projects = []
            for ws_path in known_workspaces:
                p_path = Path(ws_path)
                p_name = p_path.name or str(ws_path)
                ws_sessions = list_sessions(workspace=ws_path)
                s_list = []
                for r in ws_sessions:
                    assigned_session_ids.add(r.id)
                    s_list.append({
                        "id": r.id,
                        "title": r.title,
                        "updated_at": r.updated_at,
                        "time_ago": _time_ago(r.updated_at),
                        "turn_count": r.turn_count,
                        "workspace": r.workspace,
                    })
                
                is_curr = False
                try:
                    is_curr = (Path(ws_path).resolve() == Path(current_ws).resolve())
                except Exception:
                    is_curr = (str(ws_path).casefold() == str(current_ws).casefold())

                projects.append({
                    "name": p_name,
                    "path": ws_path,
                    "is_current": is_curr,
                    "sessions": s_list,
                })

            general_sessions = []
            for r in all_sessions:
                if r.id not in assigned_session_ids:
                    general_sessions.append({
                        "id": r.id,
                        "title": r.title,
                        "updated_at": r.updated_at,
                        "time_ago": _time_ago(r.updated_at),
                        "turn_count": r.turn_count,
                        "workspace": r.workspace,
                    })

            self._send_json({
                "projects": projects,
                "conversations": general_sessions,
                "current_workspace": current_ws,
            })
            return

        if path == "/api/sessions":
            ws = query.get("workspace", [None])[0]
            records = list_sessions(workspace=ws)
            self._send_json({
                "sessions": [
                    {
                        "id": r.id,
                        "title": r.title,
                        "created_at": r.created_at,
                        "updated_at": r.updated_at,
                        "model": r.model,
                        "workspace": r.workspace,
                        "turn_count": r.turn_count,
                        "summary": r.summary,
                    }
                    for r in records
                ]
            })
            return

        if path.startswith("/api/session/"):
            session_id = path[len("/api/session/"):]
            payload = load_session(session_id)
            if payload is None:
                self.send_error(404, "Session not found")
                return
            self._send_json(payload)
            return

        if path == "/api/goal":
            self._send_json({"summary": self.harness.goal_summary()})
            return

        if path == "/api/artifacts":
            ws_root = Path(config.sandbox_root())
            artifacts = []
            if ws_root.is_dir():
                candidate_exts = {".pptx", ".ppt", ".md", ".py", ".html", ".json", ".csv", ".xlsx", ".pdf", ".txt"}
                try:
                    for f in sorted(ws_root.glob("*"), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True):
                        if f.is_file() and f.suffix.lower() in candidate_exts:
                            stat = f.stat()
                            size_kb = stat.st_size / 1024
                            size_str = f"{stat.st_size} B" if stat.st_size < 1024 else (f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.2f} MB")
                            file_type = f.suffix.lower().lstrip(".")
                            
                            slides_count = None
                            if file_type in ("pptx", "ppt") and hasattr(self.harness, "deck") and self.harness.deck:
                                try:
                                    slides_count = len(getattr(self.harness.deck, "slides", []))
                                except Exception:
                                    slides_count = None

                            artifacts.append({
                                "name": f.name,
                                "path": str(f.resolve()),
                                "type": file_type,
                                "size": stat.st_size,
                                "size_human": size_str,
                                "updated_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                                "time_ago": _time_ago(datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()),
                                "slides_count": slides_count,
                                "is_pptx": file_type in ("pptx", "ppt"),
                            })
                except Exception:
                    pass

            self._send_json({
                "artifacts": artifacts,
                "workspace": str(ws_root),
                "count": len(artifacts),
            })
            return

        self.send_error(404, "Not Found")

    def do_POST(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        body = self._read_json_body()

        if path == "/api/reveal_file":
            file_path = body.get("path")
            if file_path and Path(file_path).exists():
                norm = str(Path(file_path).resolve())
                if sys.platform == "win32":
                    try:
                        subprocess.Popen(["explorer.exe", f"/select,{norm}"])
                    except Exception:
                        pass
                self._send_json({"status": "ok", "path": norm})
                return
            self.send_error(400, "File does not exist")
            return

        if path == "/api/choose_directory":
            selected_path = _pick_directory_native(initial_dir=str(config.sandbox_root()))
            if selected_path:
                self._send_json({"status": "ok", "path": selected_path})
            else:
                self._send_json({"status": "cancelled", "path": ""})
            return

        if path == "/api/choose_save_ppt":
            selected_path = _pick_save_file_native(
                initial_dir=str(config.sandbox_root()),
                default_name="presentation.pptx",
            )
            if selected_path:
                self._send_json({"status": "ok", "path": selected_path})
            else:
                self._send_json({"status": "cancelled", "path": ""})
            return

        if path == "/api/workspace":
            new_ws = body.get("workspace")
            if new_ws:
                os.environ["WORKSPACE"] = str(new_ws)
                config.set_sandbox_root(new_ws)
                try:
                    register_workspace(new_ws)
                except Exception:
                    pass
                self.harness.reset()
                self._send_json({"status": "ok", "workspace": str(config.sandbox_root())})
                return
            self.send_error(400, "Missing workspace argument")
            return

        if path == "/api/cancel":
            self.harness.request_cancel()
            self._send_json({"status": "cancelled"})
            return

        if path == "/api/ppt/verify":
            try:
                res = dispatch("ppt_check", json.dumps({"policy": "auto"}), self.harness)
                self._send_json({"result": res})
            except Exception as e:
                self._send_json({"result": f"校验失败: {e}"}, status=500)
            return

        if path == "/api/ppt/save":
            save_path = body.get("path", "presentation.pptx")
            try:
                res = dispatch("ppt_save", json.dumps({"path": save_path}), self.harness)
                self._send_json({"result": res})
            except Exception as e:
                self._send_json({"result": f"保存失败: {e}"}, status=500)
            return

        if path == "/api/ppt/undo":
            try:
                res = self.harness.undo()
                self._send_json({"result": res})
            except Exception as e:
                self._send_json({"result": f"撤销失败: {e}"}, status=500)
            return

        if path == "/api/session/export":
            session_id = body.get("session_id")
            if not session_id:
                rec = save_session(self.harness)
                session_id = rec.id
            out_file = config.sandbox_root() / f"xiaopu-session-{session_id[:8]}.md"
            exported = export_session(session_id, out_file)
            self._send_json({"path": str(exported)})
            return

        if path == "/api/goal":
            objective = body.get("objective", "")
            if objective:
                res = self.harness.start_goal(objective)
                self._send_json({"result": res})
                return
            self.send_error(400, "Missing objective")
            return

        if path == "/api/settings":
            updates = {}
            if "provider" in body and body["provider"].strip():
                updates["PROVIDER"] = str(body["provider"]).strip().lower()
            if "api_base" in body and body["api_base"].strip():
                updates["OPENAI_BASE_URL"] = str(body["api_base"]).strip()
                updates["ANTHROPIC_BASE_URL"] = str(body["api_base"]).strip()
            if "api_key" in body and body["api_key"].strip():
                updates["OPENAI_API_KEY"] = str(body["api_key"]).strip()
                updates["ANTHROPIC_API_KEY"] = str(body["api_key"]).strip()
            if "model" in body and body["model"].strip():
                updates["OPENAI_MODEL"] = str(body["model"]).strip()
                updates["ANTHROPIC_MODEL"] = str(body["model"]).strip()
            if "models_csv" in body:
                updates["XIAOPU_MODELS"] = str(body["models_csv"]).strip()
            if "reasoning_effort" in body and body["reasoning_effort"].strip():
                updates["REASONING_EFFORT"] = str(body["reasoning_effort"]).strip()
            if "command_policy" in body and body["command_policy"].strip():
                updates["XIAOPU_COMMAND_POLICY"] = str(body["command_policy"]).strip()

            if updates:
                config.update_env_settings(updates)
                try:
                    if hasattr(self.harness, "llm"):
                        from agent.llm import create_llm
                        self.harness.llm = create_llm(model=config.model())
                except Exception:
                    pass

            self._send_json({"status": "ok", "settings": body})
            return

        if path == "/api/chat":
            self._handle_chat_stream(body)
            return

        self.send_error(404, "Not Found")

    def do_DELETE(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if path.startswith("/api/session/"):
            session_id = path[len("/api/session/"):]
            ok = delete_session(session_id)
            self._send_json({"status": "deleted" if ok else "not_found"})
            return
        self.send_error(404, "Not Found")

    def _handle_chat_stream(self, body: dict) -> None:
        task = body.get("task", "")
        session_id = body.get("session_id")
        model = body.get("model")
        permission = body.get("permission")
        reasoning_effort = body.get("reasoning_effort")

        if reasoning_effort:
            os.environ["REASONING_EFFORT"] = str(reasoning_effort).strip()

        if model:
            if config.provider() == "anthropic":
                os.environ["ANTHROPIC_MODEL"] = model
            else:
                os.environ["OPENAI_MODEL"] = model
            if getattr(self.harness, "llm", None):
                self.harness.llm.model = model

        if permission:
            config.set_command_policy(permission)
            os.environ["COMMAND_POLICY"] = permission

        # If resuming a specific session ID
        if session_id and (not hasattr(self.harness, "session") or self.harness.session.id != session_id):
            payload = load_session(session_id)
            if payload:
                restore_harness(self.harness, payload)

        # Set up SSE Streaming headers
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        event_queue: queue.Queue = queue.Queue()

        def stream_token(piece: str):
            event_queue.put({"type": "token", "content": piece})

        def reasoning_token(piece: str):
            event_queue.put({"type": "reasoning", "content": piece})

        def runtime_listener(event: RuntimeEvent):
            p = getattr(event, "payload", {})
            kind = getattr(event, "kind", None)
            if kind == EventKind.TOOL_STARTED:
                event_queue.put({
                    "type": "tool_started",
                    "payload": {"tool": p.get("tool"), "arguments": p.get("arguments", "")[:240]},
                })
            elif kind == EventKind.TOOL_COMPLETED:
                event_queue.put({
                    "type": "tool_completed",
                    "payload": {"tool": p.get("tool"), "output": str(p.get("output", ""))[:400]},
                })
            elif kind == EventKind.TOOL_FAILED:
                event_queue.put({
                    "type": "tool_failed",
                    "payload": {"tool": p.get("tool"), "error": str(p.get("error", ""))[:240]},
                })
            elif kind == EventKind.PHASE_CHANGED:
                event_queue.put({
                    "type": "phase_changed",
                    "payload": {"from_phase": p.get("from_phase"), "to_phase": p.get("to_phase")},
                })

        self.harness.stream_callback = stream_token
        self.harness.reasoning_callback = reasoning_token
        unsub = self.harness.subscribe(runtime_listener)

        worker_done = threading.Event()
        worker_error: list[str] = []

        def worker():
            try:
                res = self.harness.run(task)
                event_queue.put({"type": "result", "content": res})
                rec = save_session(self.harness)
                event_queue.put({"type": "session_saved", "session_id": rec.id})
            except Exception as exc:
                worker_error.append(str(exc))
                event_queue.put({"type": "error", "content": f"{type(exc).__name__}: {exc}"})
            finally:
                worker_done.set()

        threading.Thread(target=worker, name="xiaopu-web-worker", daemon=True).start()

        try:
            while not worker_done.is_set() or not event_queue.empty():
                try:
                    ev = event_queue.get(timeout=0.1)
                    line = f"data: {json.dumps(ev, ensure_ascii=False)}\n\n".encode("utf-8")
                    self.wfile.write(line)
                    self.wfile.flush()
                except queue.Empty:
                    continue
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            unsub()
            self.close_connection = True


def run_web_gui(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True, model: str | None = None) -> None:
    XiaopuWebHandler.harness = Harness(model=model, interactive=True)
    server = ThreadingHTTPServer((host, port), XiaopuWebHandler)
    url = f"http://{host}:{port}"
    print(f"\n=======================================================")
    print(f"  小朴 Xiaopu Web GUI is running at: {url}")
    print(f"=======================================================\n")

    if open_browser:
        try:
            # Try launching in app mode if MS Edge or Chrome is available
            import subprocess
            if sys.platform == "win32":
                try:
                    subprocess.Popen(["msedge", f"--app={url}"])
                except Exception:
                    webbrowser.open(url)
            else:
                webbrowser.open(url)
        except Exception:
            webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Xiaopu Web GUI server...")
        server.shutdown()


if __name__ == "__main__":
    run_web_gui()
