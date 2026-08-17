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

def _session_json(record) -> dict:
    return {
        "id": record.id,
        "title": record.title,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "time_ago": _time_ago(record.updated_at),
        "model": record.model,
        "workspace": record.workspace,
        "turn_count": record.turn_count,
        "summary": record.summary,
        "pinned": bool(record.pinned),
        "status": record.status,
    }


def _workspace_json(record) -> dict:
    return {
        "path": record.path,
        "name": record.name,
        "display_name": record.display_name or record.name,
        "last_used": record.last_used,
        "pinned": bool(record.pinned),
        "archived": bool(record.archived),
        "removed_at": record.removed_at or "",
    }


from . import config
from .events import EventKind, RuntimeEvent
from .harness import Harness
from .session_store import (
    archive_session,
    batch_session_action,
    delete_session,
    export_session,
    list_sessions,
    load_session,
    purge_expired_sessions,
    purge_session,
    rename_session,
    restore_harness,
    restore_session,
    save_session,
    set_session_pinned,
    trash_session,
)
from .tools.registry import dispatch
from .workspace_store import (
    archive_workspace,
    list_workspaces,
    purge_workspace,
    register_workspace,
    remove_workspace,
    rename_workspace,
    restore_workspace,
    set_workspace_pinned,
    touch_workspace,
)

WEB_DIR = Path(__file__).resolve().parent / "web"
ASSETS_DIR = Path(__file__).resolve().parent / "assets"


def _find_active_deck(ws_path: Path | None = None) -> Path | None:
    root = ws_path or config.sandbox_root()
    if not root.is_dir():
        return None
    d = root / "deck.pptx"
    if d.exists() and d.is_file() and d.stat().st_size > 0:
        return d
    pptxs = sorted(
        [p for p in root.glob("*.pptx") if not p.name.startswith("~$") and p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if pptxs:
        return pptxs[0]
    rec_pptxs = sorted(
        [p for p in root.rglob("*.pptx") if not p.name.startswith("~$") and p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if rec_pptxs:
        return rec_pptxs[0]
    return None


def _get_deck_content_data(pptx_path: Path) -> dict[str, Any]:
    from pptx import Presentation
    try:
        prs = Presentation(str(pptx_path))
    except Exception as exc:
        return {"success": False, "error": str(exc), "total_slides": 0, "slides": [], "text_content": ""}

    slides_info = []
    text_sections = []
    for idx, slide in enumerate(prs.slides, 1):
        slide_title = ""
        items = []
        for sh in slide.shapes:
            if getattr(sh, "has_text_frame", False) and sh.text_frame:
                txt = (sh.text_frame.text or "").strip()
                if not txt:
                    continue
                top = 0.0
                try:
                    top = sh.top.inches if sh.top is not None else 0.0
                except Exception:
                    pass
                if not slide_title and top < 1.5:
                    slide_title = txt
                else:
                    for p in sh.text_frame.paragraphs:
                        ptxt = (p.text or "").strip()
                        if ptxt and ptxt != slide_title and ptxt not in items:
                            items.append(ptxt)
            elif getattr(sh, "has_table", False):
                for row in sh.table.rows:
                    row_txt = " | ".join((c.text or "").strip() for c in row.cells if (c.text or "").strip())
                    if row_txt and row_txt not in items:
                        items.append(f"表格: {row_txt}")

        title_display = slide_title or f"第 {idx} 页"
        slides_info.append({
            "slide_number": idx,
            "title": title_display,
            "items": items,
        })
        text_sections.append(f"=== 第 {idx} 页: {title_display} ===")
        for it in items:
            prefix = "" if any(it.startswith(k) for k in ("•", "-", "▶", "*", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9")) else "• "
            text_sections.append(f"{prefix}{it}")
        text_sections.append("")

    html_files = []
    try:
        parent_dir = pptx_path.parent
        for html_candidate in sorted(parent_dir.glob("*.html")):
            if html_candidate.is_file() and not html_candidate.name.startswith("."):
                html_files.append({
                    "filename": html_candidate.name,
                    "content": html_candidate.read_text(encoding="utf-8", errors="ignore")[:15000],
                })
    except Exception:
        pass

    return {
        "success": True,
        "deck_name": pptx_path.name,
        "deck_path": str(pptx_path.resolve()),
        "total_slides": len(prs.slides),
        "slides": slides_info,
        "text_content": "\n".join(text_sections).strip(),
        "html_files": html_files,
    }


_COM_RENDER_LOCK = threading.Lock()


def _render_deck_slide_preview(pptx_path: Path, slide_number: int = 1) -> bytes | None:
    import io
    # 1. Try Windows PowerPoint COM for 100% native pixel-perfect quality
    if sys.platform == "win32":
        cache_dir = config.sandbox_root() / ".xiaopu" / "preview_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        out_png = cache_dir / f"slide_{slide_number}_{int(pptx_path.stat().st_mtime)}.png"
        if out_png.exists() and out_png.stat().st_size > 0:
            return out_png.read_bytes()

        with _COM_RENDER_LOCK:
            if out_png.exists() and out_png.stat().st_size > 0:
                return out_png.read_bytes()
            try:
                import win32com.client
                import pythoncom
                pythoncom.CoInitialize()
                ppt_app = None
                prs = None
                try:
                    ppt_app = win32com.client.DispatchEx("PowerPoint.Application")
                    prs = ppt_app.Presentations.Open(str(pptx_path.resolve()), ReadOnly=True, Untitled=False, WithWindow=False)
                    if 1 <= slide_number <= prs.Slides.Count:
                        prs.Slides(slide_number).Export(str(out_png), "PNG", 1920, 1080)
                        if out_png.exists():
                            return out_png.read_bytes()
                finally:
                    if prs is not None:
                        try:
                            prs.Close()
                        except Exception:
                            pass
                        del prs
                    if ppt_app is not None:
                        try:
                            ppt_app.Quit()
                        except Exception:
                            pass
                        del ppt_app
                    try:
                        pythoncom.CoUninitialize()
                    except Exception:
                        pass
            except Exception:
                pass

    # 2. Fallback: PIL rasterizer
    try:
        from pptx import Presentation
        from PIL import Image, ImageDraw
        prs = Presentation(str(pptx_path))
        if 1 <= slide_number <= len(prs.slides):
            slide = prs.slides[slide_number - 1]
            img = Image.new("RGB", (1920, 1080), color=(15, 23, 42))
            draw = ImageDraw.Draw(img)
            draw.rectangle([(0, 0), (1920, 120)], fill=(30, 41, 59))
            draw.text((60, 45), f"幻灯片预览 · 第 {slide_number} 页", fill=(56, 189, 248))
            y = 180
            for sh in slide.shapes:
                if getattr(sh, "has_text_frame", False) and sh.text_frame:
                    t = (sh.text_frame.text or "").strip()
                    if t:
                        draw.text((80, y), t[:120], fill=(241, 245, 249))
                        y += 50
                        if y > 980:
                            break
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()
    except Exception:
        pass
    return None


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

    def _send_bytes(self, content: bytes, content_type: str = "image/png") -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache, must-revalidate")
        self.send_header("Access-Control-Allow-Origin", "*")
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
            view = query.get("view", ["active"])[0]
            records = list_workspaces(view=view)
            current = str(config.sandbox_root())
            self._send_json({
                "workspaces": [w.path for w in records],
                "current": current,
                "records": [_workspace_json(w) for w in records],
                "archived": [_workspace_json(w) for w in list_workspaces(view="archived")],
                "removed": [_workspace_json(w) for w in list_workspaces(view="removed")],
            })
            return

        if path == "/api/workspaces/manage":
            self._send_json({
                "active": [_workspace_json(w) for w in list_workspaces(view="active")],
                "archived": [_workspace_json(w) for w in list_workspaces(view="archived")],
                "removed": [_workspace_json(w) for w in list_workspaces(view="removed")],
                "current": str(config.sandbox_root()),
            })
            return

        if path == "/api/tree":
            # Trash self-cleans on read; cheap and avoids a background scheduler.
            purge_expired_sessions(days=30)
            view = query.get("view", ["active"])[0]
            if view not in {"active", "archive", "trash", "all"}:
                view = "active"
            q = (query.get("q", [""])[0] or "").strip().casefold()
            current_ws = str(config.sandbox_root())
            known_workspaces = []

            # Workspaces explicitly archived/removed stay hidden even when they
            # are the current workspace or own historical sessions.
            hidden_workspaces: set[str] = set()
            for w in list_workspaces(view="archived") + list_workspaces(view="removed"):
                try:
                    hidden_workspaces.add(str(Path(w.path).resolve()).casefold())
                except Exception:
                    pass

            # 1. Registered active workspaces
            for w in list_workspaces(view="active"):
                w_path = getattr(w, "path", str(w))
                if w_path and w_path not in known_workspaces:
                    try:
                        if Path(w_path).is_dir():
                            known_workspaces.append(str(Path(w_path).resolve()))
                    except Exception:
                        pass

            # 2. Current workspace (unless the user archived/removed it)
            try:
                curr_res = str(Path(current_ws).resolve())
                if curr_res.casefold() not in hidden_workspaces and curr_res not in known_workspaces:
                    known_workspaces.insert(0, curr_res)
            except Exception:
                if current_ws not in known_workspaces:
                    known_workspaces.insert(0, current_ws)

            # 3. Auto-discover valid workspaces from all historical sessions
            active_sessions = list_sessions(view="active")
            for s in active_sessions:
                if s.workspace:
                    try:
                        p = Path(s.workspace)
                        if p.is_dir():
                            resolved = str(p.resolve())
                            # Ignore temporary pytest directories and
                            # explicitly archived/removed workspaces.
                            if "pytest-" not in resolved and "Temp" not in resolved \
                                    and resolved.casefold() not in hidden_workspaces \
                                    and resolved not in known_workspaces:
                                known_workspaces.append(resolved)
                    except Exception:
                        pass

            # Workspace metadata (display alias, pin) keyed by resolved path.
            ws_meta: dict[str, dict] = {}
            for w in list_workspaces(view="all"):
                try:
                    ws_meta[str(Path(w.path).resolve()).casefold()] = _workspace_json(w)
                except Exception:
                    pass

            def matches_query(session) -> bool:
                if not q:
                    return True
                haystack = f"{session.title} {session.summary}".casefold()
                return q in haystack

            assigned_session_ids = set()
            projects = []
            view_sessions = list_sessions(view=view)
            for ws_path in known_workspaces:
                p_path = Path(ws_path)
                p_name = p_path.name or str(ws_path)
                ws_sessions = [s for s in list_sessions(workspace=ws_path, view=view) if matches_query(s)]
                s_list = []
                for r in ws_sessions:
                    assigned_session_ids.add(r.id)
                    s_list.append(_session_json(r))
                try:
                    meta = ws_meta.get(str(Path(ws_path).resolve()).casefold(), {})
                except Exception:
                    meta = {}
                is_curr = False
                try:
                    is_curr = (Path(ws_path).resolve() == Path(current_ws).resolve())
                except Exception:
                    is_curr = (str(ws_path).casefold() == str(current_ws).casefold())

                projects.append({
                    "name": meta.get("display_name") or p_name,
                    "path": ws_path,
                    "is_current": is_curr,
                    "pinned": meta.get("pinned", False),
                    "sessions": s_list,
                })

            general_sessions = []
            for r in view_sessions:
                if r.id not in assigned_session_ids and matches_query(r):
                    general_sessions.append(_session_json(r))

            self._send_json({
                "projects": projects,
                "conversations": general_sessions,
                "current_workspace": current_ws,
                "view": view,
                "query": q,
                "workspace_groups": {
                    "active": [_workspace_json(w) for w in list_workspaces(view="active")],
                    "archived": [_workspace_json(w) for w in list_workspaces(view="archived")],
                    "removed": [_workspace_json(w) for w in list_workspaces(view="removed")],
                },
            })
            return

        if path == "/api/sessions":
            ws = query.get("workspace", [None])[0]
            view = query.get("view", ["active"])[0]
            records = list_sessions(workspace=ws, view=view)
            self._send_json({"sessions": [_session_json(r) for r in records]})
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
                    # Recursive discovery: task outputs live under tasks/<id>/output,
                    # so a root-only scan hides the artifacts the agent just made.
                    candidates = []
                    for f in ws_root.rglob("*"):
                        if f.is_file() and f.suffix.lower() in candidate_exts:
                            candidates.append(f)
                            if len(candidates) >= 300:
                                break
                    candidates.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
                    for f in candidates[:200]:
                        stat = f.stat()
                        size_kb = stat.st_size / 1024
                        size_str = f"{stat.st_size} B" if stat.st_size < 1024 else (f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.2f} MB")
                        file_type = f.suffix.lower().lstrip(".")

                        slides_count = None
                        if file_type in ("pptx", "ppt"):
                            try:
                                from pptx import Presentation as _Presentation
                                slides_count = len(_Presentation(str(f)).slides)
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

        if path == "/api/ppt/content":
            ws_param = query.get("workspace", [None])[0]
            ws_root = Path(ws_param) if ws_param else config.sandbox_root()
            deck_path = _find_active_deck(ws_root)
            if not deck_path or not deck_path.exists():
                self._send_json({
                    "success": False,
                    "error": "当前工作区暂未生成 PPT 文件",
                    "deck_name": "",
                    "total_slides": 0,
                    "slides": [],
                    "text_content": "",
                })
                return
            data = _get_deck_content_data(deck_path)
            self._send_json(data)
            return

        if path == "/api/ppt/preview":
            ws_param = query.get("workspace", [None])[0]
            ws_root = Path(ws_param) if ws_param else config.sandbox_root()
            slide_idx = int(query.get("slide", ["1"])[0])
            deck_path = _find_active_deck(ws_root)
            if not deck_path or not deck_path.exists():
                # Return empty fallback image
                from PIL import Image
                import io
                img = Image.new("RGB", (1920, 1080), color=(15, 23, 42))
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                self._send_bytes(buf.getvalue(), "image/png")
                return
            png_bytes = _render_deck_slide_preview(deck_path, slide_idx)
            if png_bytes:
                self._send_bytes(png_bytes, "image/png")
                return
            self.send_error(500, "Failed to render slide preview")
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
                try:
                    register_workspace(new_ws)
                except Exception:
                    pass
                self.harness.reset()
                self._send_json({"status": "ok", "workspace": str(config.sandbox_root())})
                return
            self.send_error(400, "Missing workspace argument")
            return

        if path == "/api/workspace/action":
            ws_path = body.get("path")
            action = body.get("action")
            if not ws_path or not action:
                self.send_error(400, "Missing path or action")
                return
            handlers = {
                "rename": lambda: rename_workspace(ws_path, body.get("display_name", "")),
                "pin": lambda: set_workspace_pinned(ws_path, bool(body.get("pinned", False))),
                "archive": lambda: archive_workspace(ws_path),
                "restore": lambda: restore_workspace(ws_path),
                "remove": lambda: remove_workspace(ws_path),
                "purge": lambda: purge_workspace(ws_path),
            }
            handler = handlers.get(action)
            if handler is None:
                self.send_error(400, f"Unsupported workspace action: {action}")
                return
            try:
                ok = handler()
            except Exception as exc:
                self._send_json({"status": "error", "error": str(exc)}, status=400)
                return
            self._send_json({"status": "ok" if ok else "not_found", "action": action, "path": ws_path})
            return

        if path == "/api/session/action":
            session_id = body.get("id")
            action = body.get("action")
            if not session_id or not action:
                self.send_error(400, "Missing id or action")
                return
            if action == "rename":
                ok = rename_session(session_id, body.get("title", ""))
                result = {"status": "ok" if ok else "not_found", "action": action}
            elif action == "pin":
                ok = set_session_pinned(session_id, bool(body.get("pinned", False)))
                result = {"status": "ok" if ok else "not_found", "action": action}
            elif action in {"archive", "trash", "restore", "purge"}:
                handlers = {
                    "archive": archive_session,
                    "trash": trash_session,
                    "restore": restore_session,
                    "purge": purge_session,
                }
                ok = handlers[action](session_id)
                result = {"status": "ok" if ok else "not_found", "action": action}
            elif action == "export":
                try:
                    out_file = config.sandbox_root() / f"xiaopu-session-{session_id[:8]}.md"
                    exported = export_session(session_id, out_file)
                    result = {"status": "ok", "action": action, "path": str(exported)}
                except ValueError:
                    result = {"status": "not_found", "action": action}
            else:
                self.send_error(400, f"Unsupported session action: {action}")
                return
            self._send_json(result)
            return

        if path == "/api/sessions/batch":
            ids = [str(i) for i in body.get("ids", [])]
            action = body.get("action", "")
            if not ids or action not in {"archive", "trash", "restore", "purge"}:
                self.send_error(400, "Missing ids or unsupported action")
                return
            result = batch_session_action(ids, action)
            self._send_json({"status": "ok", **result})
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

        if path == "/api/ppt/apply_content":
            text_content = (body.get("text_content") or "").strip()
            if not text_content:
                self.send_error(400, "Missing text_content")
                return
            instruction = (
                "请保持当前演示文稿的精美排版、布局结构与视觉设计风格，按照以下修改后的文本内容更新 PPT 对应的页面标题、卡片内容与要点细节，更新后自动保存并校验：\n\n"
                + text_content
            )
            self._send_json({
                "status": "ok",
                "instruction": instruction,
            })
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
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/session/"):
            session_id = path[len("/api/session/"):]
            mode = urllib.parse.parse_qs(parsed.query).get("mode", ["trash"])[0]
            if mode == "purge":
                ok = delete_session(session_id)
                status = "deleted"
            else:
                ok = trash_session(session_id)
                status = "trashed"
            self._send_json({"status": status if ok else "not_found"})
            return
        self.send_error(404, "Not Found")

    def _handle_chat_stream(self, body: dict) -> None:
        # The browser frontend posts `prompt`; older API clients post `task`.
        # Accept both so the web composer always reaches the harness.
        task = body.get("task") or body.get("prompt") or ""
        session_id = body.get("session_id")
        model = body.get("model")
        permission = body.get("permission") or body.get("command_policy")
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
            elif kind == EventKind.MODEL_RESPONSE:
                event_queue.put({
                    "type": "model_response",
                    "payload": {
                        "content": str(p.get("content") or ""),
                        "reasoning_content": str(p.get("reasoning_content") or ""),
                        "has_tool_calls": bool(p.get("has_tool_calls")),
                        "phase": p.get("phase"),
                    },
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


def _kill_existing_server_on_port(port: int = 8765) -> None:
    """Ensure any stale/zombie process occupying port is terminated before starting."""
    if sys.platform != "win32":
        return
    import subprocess
    import os
    import time
    current_pid = os.getpid()
    try:
        cmd = f'netstat -ano | findstr :{port}'
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, errors="ignore")
        pids_to_kill = set()
        for line in (res.stdout or "").strip().splitlines():
            parts = line.strip().split()
            if len(parts) >= 5 and "LISTENING" in parts[3].upper():
                try:
                    pid = int(parts[4])
                    if pid != current_pid and pid > 0:
                        pids_to_kill.add(pid)
                except ValueError:
                    pass
        for pid in pids_to_kill:
            try:
                subprocess.run(f"taskkill /F /PID {pid}", shell=True, capture_output=True)
            except Exception:
                pass
        if pids_to_kill:
            time.sleep(0.6)
    except Exception:
        pass


def run_web_gui(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True, model: str | None = None) -> None:
    _kill_existing_server_on_port(port)
    XiaopuWebHandler.harness = Harness(model=model, interactive=True, max_steps=50)
    server = ThreadingHTTPServer((host, port), XiaopuWebHandler)
    url = f"http://{host}:{port}"
    print(f"\n=======================================================")
    print(f"  报一 Baoyi Web GUI is running at: {url}")
    print(f"=======================================================\n")

    if open_browser:
        try:
            import shutil
            from pathlib import Path
            browser_bin = None
            if sys.platform == "win32":
                candidates = [
                    shutil.which("msedge"),
                    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                    shutil.which("chrome"),
                    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                ]
                for cand in candidates:
                    if cand and Path(cand).is_file():
                        browser_bin = str(cand)
                        break

            if browser_bin:
                subprocess.Popen([browser_bin, f"--app={url}"])
            else:
                webbrowser.open(url)
        except Exception:
            try:
                webbrowser.open(url)
            except Exception:
                pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Baoyi Web GUI server...")
        server.shutdown()


if __name__ == "__main__":
    run_web_gui()
