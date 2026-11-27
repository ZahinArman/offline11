"""
The window that install.py and uninstall.py show (web/setup.html, same design system as the app).
"""

from __future__ import annotations

import ctypes
import sys
import threading
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import webview


def setup_web_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", "")) / "web"
    return Path(__file__).resolve().parent / "web"


def _bg() -> str:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            return "#FAF9F5" if winreg.QueryValueEx(k, "AppsUseLightTheme")[0] else "#1F1E1D"
    except Exception:
        return "#FAF9F5"


def _round(window: webview.Window) -> None:
    try:
        hwnd = window.native.Handle.ToInt32()
        pref = ctypes.c_int(2)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(pref), ctypes.sizeof(pref))
    except Exception:
        pass


class SetupApi:
    """State machine shared by the installer and the uninstaller. Work runs on a thread."""

    def __init__(self, mode: str, state: Dict[str, Any], worker: Callable[..., Dict[str, Any]],
                 choose_folder: Optional[Callable[[str], Dict[str, Any]]] = None,
                 failed_action: Optional[Callable[[], None]] = None) -> None:
        self._mode = mode
        self._state = dict(state, mode=mode)
        self._worker = worker
        self._choose = choose_folder
        self._failed_action = failed_action
        self._window: Optional[webview.Window] = None

    def status(self) -> Dict[str, Any]:
        return dict(self._state)

    def choose_folder(self) -> Dict[str, Any]:
        if self._choose and self._window:
            result = self._window.create_file_dialog(webview.FileDialog.FOLDER, directory=str(Path(self._state["folder"]).parent))
            if result:
                picked = result[0] if isinstance(result, (list, tuple)) else result
                self._state.update(self._choose(str(picked)))
        return self.status()

    def _run(self, **kwargs: Any) -> Dict[str, Any]:
        self._state.update(stage="working", error="")

        def work() -> None:
            try:
                self._state.update(self._worker(**kwargs))
            except Exception as e:
                self._state.update(stage="failed", error=str(e))

        threading.Thread(target=work, daemon=True).start()
        return self.status()

    def install(self, autostart: bool) -> Dict[str, Any]:
        return self._run(autostart=bool(autostart))

    def uninstall(self, keep_data: bool) -> Dict[str, Any]:
        return self._run(keep_data=bool(keep_data))

    def failed_action(self) -> None:
        if self._failed_action:
            self._failed_action()

    def close(self) -> None:
        if self._state.get("stage") != "working" and self._window:
            self._window.destroy()


def run_setup_window(api: SetupApi, title: str, height: int = 440) -> None:
    window = webview.create_window(
        title, url=str(setup_web_dir() / "setup.html"), js_api=api, width=400, height=height,
        frameless=True, easy_drag=False, resizable=False, background_color=_bg(), on_top=False,
    )
    api._window = window
    window.events.shown += lambda: _round(window)
    webview.start(gui="edgechromium", private_mode=True)
