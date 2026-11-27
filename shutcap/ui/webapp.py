"""
ShutCap user interface (pywebview + HTML/CSS in shutcap/ui/web).

Two kinds of window, one design system (web/base.css):
- The main window: setup, home, settings and history in one frameless window.
- One alert window that changes shape: warning card, curfew, emergency, countdown pill, failed.

Pop-up policy: alerts are the only separate windows. Confirms are sheets inside the main
window, success has no message, and errors show next to the field.
"""

from __future__ import annotations

import ctypes
import logging
import os
import subprocess
import sys
import threading
import time
from ctypes import wintypes
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import webview

from shutcap import __version__
from shutcap.autostart import disable_autostart, enable_autostart, is_autostart_enabled
from shutcap.config import MILESTONES, Config, ConfigManager, ScheduleError
from shutcap.logger import AuditLogger
from shutcap.notifications import NotificationManager
from shutcap.scheduler import Scheduler
from shutcap.state import CurfewStatus, StateManager
from shutcap.time_provider import TimeProvider


def web_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "shutcap" / "ui" / "web"
    return Path(__file__).resolve().parent / "web"


WEB = web_dir()
ICON_ICO = WEB.parent.parent.parent / "assets" / "icon.ico" if not getattr(sys, "frozen", False) else \
    Path(getattr(sys, "_MEIPASS", "")) / "assets" / "icon.ico"

LABELS: Dict[str, str] = {
    "warning_1_time": "First warning",
    "warning_2_time": "Last warning",
    "curfew_time": "Curfew",
    "grace_reminder_1_time": "Reminder",
    "grace_reminder_2_time": "Reminder",
    "final_warning_time": "Last minute",
    "shutdown_time": "Off",
}
TIME_FIELDS = [field for _, field, _ in MILESTONES]

EVENT_NAMES: Dict[str, str] = {
    "WARNING_1": "First warning",
    "WARNING_2": "Last warning",
    "CURFEW_TRIGGERED": "Curfew",
    "CURFEW_ACCEPTED": "Curfew accepted",
    "SHUTDOWN_REMINDER_1": "Reminder",
    "SHUTDOWN_REMINDER_2": "Reminder",
    "FINAL_WARNING": "Last minute",
    "SHUTDOWN_INITIATED": "Turning off",
    "SHUTDOWN_COMPLETED": "Turned off",
    "SHUTDOWN_FAILED": "Did not turn off",
    "SHUTDOWN_CANCELLED": "Shutdown cancelled",
    "EMERGENCY_GRANTED": "Emergency",
    "CURFEW_REARMED": "Curfew back on",
    "SESSION_MISSED": "Missed: the PC was off",
    "SESSION_SKIPPED": "Skipped: the PC started after curfew",
}
HIDDEN_EVENTS = {"STARTUP", "APP_EXIT"}


# --- Win32 helpers ---------------------------------------------------------------------

def _work_area() -> tuple[float, float, float, float]:
    """Primary work area (excludes the taskbar) in logical pixels."""
    r = wintypes.RECT()
    ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(r), 0)
    try:
        scale = ctypes.windll.user32.GetDpiForSystem() / 96
    except Exception:
        scale = 1.0
    return r.left / scale, r.top / scale, r.right / scale, r.bottom / scale


def _polish_window(window: webview.Window, tool_window: bool = False) -> None:
    """Win11 rounded corners, app icon, and (for alerts) no taskbar button."""
    try:
        hwnd = window.native.Handle.ToInt32()
        pref = ctypes.c_int(2)  # DWMWCP_ROUND
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(pref), ctypes.sizeof(pref))
        if tool_window:
            GWL_EXSTYLE, WS_EX_TOOLWINDOW, WS_EX_APPWINDOW = -20, 0x80, 0x40000
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, (style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW)
        if ICON_ICO.exists():
            # Win32 WM_SETICON, posted: safe from any thread (setting the .NET Icon here deadlocks).
            user32 = ctypes.windll.user32
            user32.LoadImageW.restype = wintypes.HANDLE
            for kind, size in ((0, 16), (1, 32)):  # ICON_SMALL, ICON_BIG
                hicon = user32.LoadImageW(None, str(ICON_ICO), 1, size, size, 0x0010)  # IMAGE_ICON, LR_LOADFROMFILE
                if hicon:
                    user32.PostMessageW(hwnd, 0x0080, kind, hicon)
    except Exception as e:
        logging.debug(f"Window polish skipped: {e}")


def _bg() -> str:
    """Window background before the page paints (matches base.css light/dark)."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            light = winreg.QueryValueEx(k, "AppsUseLightTheme")[0]
        return "#FAF9F5" if light else "#1F1E1D"
    except Exception:
        return "#FAF9F5"


def _bg_surface() -> str:
    return "#FFFFFF" if _bg() == "#FAF9F5" else "#2A2927"


# --- Shared services -------------------------------------------------------------------

class Core:
    """Holds the app services and the lock that keeps the tick thread and the UI in step."""

    def __init__(self, config_mgr: ConfigManager, state_mgr: StateManager, scheduler: Scheduler,
                 audit_logger: AuditLogger, time_provider: TimeProvider,
                 notifications: Optional[NotificationManager], simulated: bool) -> None:
        self.config_mgr = config_mgr
        self.state_mgr = state_mgr
        self.scheduler = scheduler
        self.audit = audit_logger
        self.clock = time_provider
        self.notifications = notifications
        self.simulated = simulated
        self.lock = threading.RLock()

    @property
    def config(self) -> Config:
        return self.config_mgr.config

    def apply_config(self, new_config: Config) -> None:
        self.config_mgr.save(new_config)
        self.scheduler.config = new_config
        self.scheduler.shutdown_mgr.dry_run = new_config.dry_run
        if self.notifications:
            self.notifications.update_config(new_config)

    def check_times(self, times: Dict[str, str], lock_off: bool = False) -> Dict[str, Any]:
        """Validates the schedule. Errors name one field so the UI can mark that row."""
        merged = self.config.to_dict()
        for f in TIME_FIELDS:
            if f not in times:
                continue
            try:
                Config.parse_time_str(times[f])
            except (ValueError, TypeError):
                return {"ok": False, "field": f, "message": "Use HH:MM."}
            merged[f] = times[f]
        cfg = Config.from_dict(merged)
        offsets = cfg.milestone_offsets()
        for (_, label_a, off_a), (_, label_b, off_b) in zip(offsets, offsets[1:]):
            if off_a >= off_b:
                field_a = TIME_FIELDS[[o[1] for o in offsets].index(label_a)]
                field_b = TIME_FIELDS[[o[1] for o in offsets].index(label_b)]
                if lock_off and field_b == "shutdown_time":
                    return {"ok": False, "field": field_a, "message": "Must be before Off."}
                return {"ok": False, "field": field_b, "message": f"Must be after {LABELS[field_a].lower()}."}
        return {"ok": True, "config": cfg}

    def shutdown_dt(self, now: datetime) -> datetime:
        curfew = self.scheduler.next_curfew_dt(now)
        return curfew + timedelta(minutes=self.config.minutes_between("curfew", "shutdown"))


# --- Main window API (called from app.js) ----------------------------------------------

class AppApi:
    def __init__(self, ui: "WebUI") -> None:
        self._ui = ui
        self._core = ui.core

    def state(self) -> Dict[str, Any]:
        core = self._core
        with core.lock:
            cfg = core.config
            now = core.clock.now()
            status = core.scheduler.tonight_status(now)
            mode, reason, rearm = {
                CurfewStatus.WARNING_1: ("warning", None, False),
                CurfewStatus.WARNING_2: ("warning", None, False),
                CurfewStatus.CURFEW_ACTIVE: ("pending", None, False),
                CurfewStatus.SHUTDOWN_PENDING: ("pending", None, False),
                CurfewStatus.SHUTDOWN_INITIATED: ("done", None, False),
                CurfewStatus.SHUTDOWN_COMPLETED: ("done", None, False),
                CurfewStatus.SHUTDOWN_FAILED: ("failed", None, False),
                CurfewStatus.EMERGENCY_EXCEPTION: ("off", "emergency", True),
                CurfewStatus.SHUTDOWN_CANCELLED: ("off", "cancelled", True),
                CurfewStatus.SKIPPED: ("off", "skipped", False),
                CurfewStatus.MISSED: ("off", "missed", False),
            }.get(status, ("armed", None, False))
            off_dt = core.shutdown_dt(now)
            curfew_dt = core.scheduler.next_curfew_dt(now)
            left = core.state_mgr.get_remaining_seconds_until_shutdown(now) if mode == "pending" else None
            open_view, self._ui.open_view = self._ui.open_view, None
            return {
                "setup_complete": cfg.setup_complete,
                "practice": cfg.dry_run,
                "version": __version__,
                "times": {f: getattr(cfg, f) for f in TIME_FIELDS},
                "mode": mode,
                "off_reason": reason,
                "can_rearm": rearm,
                "off_day": "Tonight" if off_dt - now <= timedelta(hours=18) else off_dt.strftime("%A"),
                "secs_to_off": max(0.0, (off_dt - now).total_seconds()),
                "secs_to_curfew": max(0.0, (curfew_dt - now).total_seconds()),
                "pending_left": left or 0,
                "pending_total": cfg.minutes_between("curfew", "shutdown") * 60,
                "settings": {
                    "sound_enabled": cfg.sound_enabled,
                    "ntfy_enabled": cfg.ntfy_enabled,
                    "ntfy_topic": cfg.ntfy_topic,
                    "dry_run": cfg.dry_run,
                    "autostart": cfg.autostart if core.simulated else is_autostart_enabled(),
                },
                "open_view": open_view,
            }

    def schedule_for(self, hhmm: str) -> Dict[str, str]:
        return Config.schedule_for_shutdown(hhmm)

    def validate(self, times: Dict[str, str]) -> Dict[str, Any]:
        res = self._core.check_times(times, lock_off=not self._core.config.setup_complete)
        res.pop("config", None)
        return res

    def derive(self, times: Dict[str, str]) -> Dict[str, Any]:
        """Setup shows 3 times (first warning, curfew, off); the other 4 follow from them."""
        try:
            full = Config.derive_schedule(times["warning_1_time"], times["curfew_time"], times["shutdown_time"])
        except ScheduleError as e:
            return {"ok": False, "field": e.field, "message": e.message}
        except (KeyError, ValueError, TypeError):
            return {"ok": False, "field": "warning_1_time", "message": "Use HH:MM."}
        return {"ok": True, "times": full}

    def finish_setup(self, times: Dict[str, str], practice: bool) -> Dict[str, Any]:
        core = self._core
        derived = self.derive(times)
        if not derived["ok"]:
            return derived
        times = derived["times"]
        with core.lock:
            res = core.check_times(times, lock_off=True)
            if not res["ok"]:
                return res
            cfg: Config = res["config"]
            cfg.dry_run = bool(practice)
            cfg.setup_complete = True
            core.apply_config(cfg)
        return {"ok": True}

    def save_times(self, times: Dict[str, str]) -> Dict[str, Any]:
        core = self._core
        with core.lock:
            res = core.check_times(times)
            if res["ok"]:
                core.apply_config(res["config"])
            res.pop("config", None)
            return res

    def save_setting(self, key: str, value: Any) -> Dict[str, Any]:
        if key not in {"sound_enabled", "ntfy_enabled", "ntfy_topic", "dry_run", "autostart"}:
            return {"ok": False}
        core = self._core
        with core.lock:
            data = core.config.to_dict()
            data[key] = value if key == "ntfy_topic" else bool(value)
            if key == "autostart" and not core.simulated:
                (enable_autostart if value else disable_autostart)()
            core.apply_config(Config.from_dict(data))
        return {"ok": True}

    def cancel_shutdown(self) -> None:
        with self._core.lock:
            self._core.scheduler.cancel_pending_shutdown(reason="Cancelled in the app")
        self._ui.alerts.close()

    def rearm(self) -> None:
        with self._core.lock:
            self._core.scheduler.rearm_curfew()

    def history(self) -> list:
        entries = [e for e in self._core.audit.get_entries() if e.event not in HIDDEN_EVENTS]
        today = self._core.clock.now().date()
        days: Dict[str, Dict[str, Any]] = {}
        for e in entries:
            try:
                dt = datetime.fromisoformat(e.timestamp)
            except ValueError:
                continue
            d = dt.date()
            label = "Today" if d == today else "Yesterday" if d == today - timedelta(days=1) else dt.strftime("%a %d %b")
            day = days.setdefault(d.isoformat(), {"day": label, "items": []})
            detail = ""
            if e.event == "EMERGENCY_GRANTED":
                detail = e.details.get("reason", "")
            elif e.event == "SHUTDOWN_COMPLETED" and "dry" in e.message.lower():
                detail = "Practice: the PC stayed on."
            elif e.event == "SHUTDOWN_FAILED":
                detail = e.message.split(":", 1)[-1].strip()
            day["items"].append({
                "time": dt.strftime("%H:%M"),
                "name": EVENT_NAMES.get(e.event, e.event.replace("_", " ").capitalize()),
                "detail": detail,
            })
        return [days[k] for k in sorted(days, reverse=True)]

    def export_history(self) -> Dict[str, Any]:
        docs = Path(os.environ.get("USERPROFILE", Path.home())) / "Documents"
        name = f"shutcap-history-{self._core.clock.now():%Y-%m-%d}.txt"
        result = self._ui.main.create_file_dialog(
            webview.FileDialog.SAVE, directory=str(docs if docs.exists() else Path.home()),
            save_filename=name, file_types=("Text files (*.txt)", "All files (*.*)"),
        )
        if not result:
            return {"ok": None}
        path = result[0] if isinstance(result, (list, tuple)) else result
        try:
            with open(path, "w", encoding="utf-8") as f:
                for entry in self._core.audit.get_entries():
                    f.write(entry.to_line() + "\n")
            return {"ok": True, "path": str(path)}
        except OSError as e:
            logging.error(f"History export failed: {e}")
            return {"ok": False}

    def reveal(self, path: str) -> None:
        if path and Path(path).exists():
            subprocess.Popen(["explorer", "/select,", str(Path(path))])

    def clear_history(self) -> None:
        self._core.audit.clear()

    def test_warning(self) -> None:
        self._ui.alerts.warning_for("warning_1", test=True)

    def preview_curfew(self) -> None:
        self._ui.alerts.show_curfew(preview=True)

    def minimize(self) -> None:
        self._ui.main.minimize()

    def hide(self) -> None:
        self._ui.main.hide()


# --- Alert window ----------------------------------------------------------------------

class AlertApi:
    def __init__(self, ctl: "AlertController") -> None:
        self._ctl = ctl

    def alert(self) -> Optional[Dict[str, Any]]:
        return self._ctl.payload()

    def fit(self, height: int) -> None:
        self._ctl.fit(height)

    def dismiss(self) -> None:
        self._ctl.close()

    def accept(self) -> None:
        self._ctl.accept()

    def to_emergency(self) -> None:
        self._ctl.set_mode("emergency")

    def leave_emergency(self) -> None:
        self._ctl.set_mode(self._ctl.return_mode)

    def emergency(self, reason: str) -> None:
        self._ctl.emergency(reason)

    def retry_shutdown(self) -> None:
        self._ctl.retry_shutdown()


class AlertController:
    """Owns the single alert window and its mode."""

    WIDTH = {"warning": 340, "curfew": 400, "emergency": 400, "pill": 236, "failed": 360}
    PILL_HEIGHT = 64
    MARGIN = 16

    def __init__(self, core: Core) -> None:
        self.core = core
        self.window: Optional[webview.Window] = None
        self.mode: Optional[str] = None
        self.return_mode = "curfew"
        self.data: Dict[str, Any] = {}
        self.preview = False
        self._close_timer: Optional[threading.Timer] = None
        self._shown = False
        self._lock = threading.RLock()

    # -- geometry --
    def _anchor(self, mode: str) -> str:
        return "center" if mode in ("curfew", "emergency") else "top-right"

    def _place(self, width: int, height: int, mode: str) -> tuple[int, int]:
        left, top, right, bottom = _work_area()
        if self._anchor(mode) == "center":
            return int(left + (right - left - width) / 2), int(top + (bottom - top - height) / 2.6)
        return int(right - width - self.MARGIN), int(top + self.MARGIN)

    def fit(self, height: int) -> None:
        with self._lock:
            if not self.window or not self.mode:
                return
            w = self.WIDTH[self.mode]
            h = self.PILL_HEIGHT if self.mode == "pill" or height <= 0 else height
            x, y = self._place(w, h, self.mode)
            try:
                self.window.resize(w, h)
                self.window.move(x, y)
                if not self._shown:
                    self.window.show()
                    self._shown = True
            except Exception as e:
                logging.debug(f"Alert fit failed: {e}")

    # -- lifecycle --
    def _open(self, mode: str) -> None:
        with self._lock:
            self._cancel_timer()
            self.mode = mode
            if self.window is not None:
                return
            w = self.WIDTH[mode]
            h = self.PILL_HEIGHT if mode == "pill" else 180
            x, y = self._place(w, h, mode)
            self._shown = False
            self.window = webview.create_window(
                "ShutCap alert", url=str(WEB / "alert.html"), js_api=AlertApi(self),
                width=w, height=h, x=x, y=y, frameless=True, easy_drag=False, resizable=False,
                on_top=True, focus=mode != "warning", hidden=True, background_color=_bg_surface(),
            )
            win = self.window
            win.events.shown += lambda: _polish_window(win, tool_window=True)
            win.events.closed += lambda: self._on_closed(win)

    def _on_closed(self, win: webview.Window) -> None:
        with self._lock:
            if self.window is win:
                self.window = None
                self.mode = None

    def close(self) -> None:
        with self._lock:
            self._cancel_timer()
            win, self.window, self.mode = self.window, None, None
        if win is not None:
            try:
                win.destroy()
            except Exception:
                pass

    def _cancel_timer(self) -> None:
        if self._close_timer:
            self._close_timer.cancel()
            self._close_timer = None

    def set_mode(self, mode: str) -> None:
        with self._lock:
            if mode == "emergency" and self.mode != "emergency":
                self.return_mode = self.mode if self.mode in ("curfew", "pill") else "pill"
            self.mode = mode
            if self.window is not None and mode in ("curfew", "emergency"):
                try:
                    self.window.restore()
                except Exception:
                    pass

    def payload(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            if not self.mode:
                return None
            data = dict(self.data, mode=self.mode, preview=self.preview)
        core = self.core
        cfg = core.config
        data["shutdown_time"] = cfg.shutdown_time
        data["practice"] = cfg.dry_run
        data["pending_total"] = cfg.minutes_between("curfew", "shutdown") * 60
        if self.mode == "pill":
            if self.preview:
                data["pending_left"] = data["pending_total"]
            else:
                left = core.state_mgr.get_remaining_seconds_until_shutdown(core.clock.now())
                data["pending_left"] = left or 0
        return data

    # -- what the scheduler and UI ask for --
    def warning_for(self, key: str, test: bool = False) -> None:
        cfg = self.core.config
        mins = cfg.minutes_between(key, "curfew")
        unit = "minute" if mins == 1 else "minutes"
        level = "urgent" if key == "warning_2" else ""
        body = f"Curfew at {cfg.curfew_time}." if key == "warning_1" else "Save your work."
        self.show_warning(f"{mins} {unit} left", body, level=level, test=test)

    def show_warning(self, title: str, body: str, level: str = "", auto_close: int = 30, test: bool = False) -> None:
        with self._lock:
            if self.mode in ("curfew", "emergency", "pill", "failed") and not self.preview:
                return  # never cover a more important alert
            self.preview = False
            self.data = {"title": title, "body": body, "level": level, "auto_close": auto_close, "test": test}
            self._open("warning")
            self._close_timer = threading.Timer(auto_close, self._auto_close)
            self._close_timer.daemon = True
            self._close_timer.start()

    def _auto_close(self) -> None:
        with self._lock:
            if self.mode == "warning":
                self.close()

    def show_curfew(self, preview: bool = False) -> None:
        with self._lock:
            if not preview and self.mode in ("curfew", "emergency", "pill"):
                return
            self.preview = preview
            self.data = {}
            if self.window is not None:
                self.set_mode("curfew")
            else:
                self._open("curfew")

    def show_pill(self) -> None:
        with self._lock:
            if self.mode in ("pill", "curfew", "emergency") and not self.preview:
                return
            self.preview = False
            if self.window is not None:
                self.set_mode("pill")
            else:
                self._open("pill")

    def show_failed(self) -> None:
        with self._lock:
            self.preview = False
            if self.window is not None:
                self.set_mode("failed")
            else:
                self._open("failed")

    def accept(self) -> None:
        if self.preview:
            self.set_mode("pill")
            threading.Timer(4.0, self._end_preview).start()
            return
        with self.core.lock:
            self.core.scheduler.user_accepts_curfew()
        self.set_mode("pill")

    def _end_preview(self) -> None:
        with self._lock:
            if self.preview:
                self.close()
                self.preview = False

    def emergency(self, reason: str) -> None:
        if not reason.strip():
            return
        if not self.preview:
            with self.core.lock:
                self.core.scheduler.user_declares_emergency(reason.strip())
        self.preview = False
        self.close()

    def retry_shutdown(self) -> None:
        core = self.core
        with core.lock:
            ok, msg = core.scheduler.shutdown_mgr.execute_shutdown(
                comment="ShutCap: curfew shutdown. Save your work.", grace_seconds=core.config.shutdown_grace_seconds)
            core.audit.log("SHUTDOWN_COMPLETED" if ok else "SHUTDOWN_FAILED",
                           f"Retry: {msg}", dt=core.clock.now())
            if ok:
                core.state_mgr.mark_shutdown_completed(core.clock.now())
        if ok:
            self.close()

    def sync(self, status: CurfewStatus) -> None:
        """Called every tick: keep the countdown pill in step with tonight's state."""
        with self._lock:
            if self.preview:
                return
            if status == CurfewStatus.SHUTDOWN_PENDING:
                if self.mode is None or self.mode == "warning":
                    if self.mode == "warning":
                        self.close()
                    self._open("pill")
            elif self.mode in ("pill", "curfew", "emergency"):
                self.close()


# --- The UI as a whole -----------------------------------------------------------------

class WebUI:
    def __init__(self, core: Core, start_hidden: bool, on_quit: Callable[[], None]) -> None:
        self.core = core
        self.on_quit = on_quit
        self.open_view: Optional[str] = None
        self.alerts = AlertController(core)
        self._running = True
        hidden = start_hidden and core.config.setup_complete
        self.main = webview.create_window(
            "ShutCap", url=str(WEB / "app.html"), js_api=AppApi(self),
            width=400, height=580, frameless=True, easy_drag=False, resizable=False,
            hidden=hidden, background_color=_bg(),
        )
        self.main.events.shown += lambda: _polish_window(self.main)
        self.main.events.closing += self._on_closing
        self._wire_scheduler()

    def _on_closing(self) -> bool:
        # Alt+F4 hides to the tray, like the close button. Quit is in the tray menu.
        if self._running:
            self.main.hide()
            return False
        return True

    def _wire_scheduler(self) -> None:
        s, core = self.core.scheduler, self.core

        def notify(title: str, message: str, sound: str, priority: str, tags: str) -> None:
            if core.notifications:
                core.notifications.notify(title, message, sound_type=sound, push_priority=priority,
                                          push_tags=tags, toast=False)

        def warning(key: str) -> None:
            mins = core.config.minutes_between(key, "curfew")
            notify(f"ShutCap: {mins} minutes left", f"Curfew at {core.config.curfew_time}.",
                   "warning" if key == "warning_1" else "urgent", "default" if key == "warning_1" else "high", "clock")
            self.alerts.warning_for(key)

        def curfew() -> None:
            notify("ShutCap: curfew", f"The PC turns off at {core.config.shutdown_time}.", "urgent", "urgent", "stop_sign")
            self.alerts.show_curfew()

        def reminder(key: str) -> None:
            # The countdown pill already shows the time. Reminders only play a sound and push.
            mins = core.config.minutes_between(key, "shutdown")
            notify(f"ShutCap: off in {mins} min", "Save your work.", "urgent", "high", "hourglass")

        def executed(success: bool, msg: str) -> None:
            if success:
                notify("ShutCap: turning off", "Windows is turning off the PC.", "urgent", "max", "zzz")
                self.alerts.close()
            else:
                notify("ShutCap: the PC did not turn off", msg, "urgent", "max", "warning")
                self.alerts.show_failed()

        s.on_warning_1 = lambda: warning("warning_1")
        s.on_warning_2 = lambda: warning("warning_2")
        s.on_curfew_start = curfew
        s.on_grace_reminder_1 = lambda: reminder("reminder_1")
        s.on_grace_reminder_2 = lambda: reminder("reminder_2")
        s.on_final_warning = lambda: reminder("final_warning")
        s.on_shutdown_executed = executed

    # -- tray / single-instance hooks (any thread) --
    def show_main(self, view: Optional[str] = None) -> None:
        self.open_view = view
        try:
            self.main.show()
            self.main.restore()
        except Exception:
            pass

    def quit(self) -> None:
        self._running = False
        self.alerts.close()
        try:
            self.main.destroy()
        except Exception:
            pass

    # -- loop --
    def _tick_loop(self) -> None:
        core = self.core
        while self._running:
            try:
                with core.lock:
                    if core.config.setup_complete or core.simulated:
                        core.scheduler.tick()
                    status = core.scheduler.tonight_status(core.clock.now())
                self.alerts.sync(status)
            except Exception as e:
                logging.error(f"Tick failed: {e}", exc_info=True)
            time.sleep(1.0)

    def run(self) -> None:
        def started() -> None:
            threading.Thread(target=self._tick_loop, daemon=True, name="shutcap-tick").start()

        storage = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "ShutCap" / "webview"
        webview.start(started, gui="edgechromium", private_mode=True, storage_path=str(storage))
        self._running = False
        self.on_quit()
