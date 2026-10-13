"""
System tray icon and menu for OFFLINE 11 using pystray.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Callable, Optional

from PIL import Image
import pystray
from pystray import Menu, MenuItem

from offline11.config import ConfigManager
from offline11.state import StateManager


class SystemTray:
    """Manages the background system tray icon and menu."""

    def __init__(
        self,
        config_mgr: ConfigManager,
        state_mgr: StateManager,
        on_show_window: Callable[[], None],
        on_open_settings: Callable[[], None],
        on_open_audit: Callable[[], None],
        on_exit_app: Callable[[], None],
        icon_path: Optional[Path] = None,
    ) -> None:
        self.config_mgr = config_mgr
        self.state_mgr = state_mgr
        self.on_show_window = on_show_window
        self.on_open_settings = on_open_settings
        self.on_open_audit = on_open_audit
        self.on_exit_app = on_exit_app

        if icon_path is None:
            icon_path = Path(__file__).parent.parent.parent / "assets" / "icon.png"
        self.icon_path = icon_path

        self._image = Image.open(self.icon_path)
        self._icon: Optional[pystray.Icon] = None
        self._thread: Optional[threading.Thread] = None

    def _create_menu(self) -> Menu:
        def _get_status_text(item: MenuItem) -> str:
            status = self.state_mgr.get_status().value
            mode = "DRY RUN" if self.config_mgr.config.dry_run else "LIVE"
            return f"Status: {status} [{mode}]"

        def _get_curfew_text(item: MenuItem) -> str:
            return f"Curfew: {self.config_mgr.config.curfew_time}"

        menu = Menu(
            MenuItem("Open OFFLINE 11", lambda: self.on_show_window(), default=True),
            MenuItem(_get_status_text, None, enabled=False),
            MenuItem(_get_curfew_text, None, enabled=False),
            Menu.SEPARATOR,
            MenuItem("Settings...", lambda: self.on_open_settings()),
            MenuItem("Audit Log...", lambda: self.on_open_audit()),
            Menu.SEPARATOR,
            MenuItem("Exit OFFLINE 11", lambda: self.on_exit_app()),
        )
        return menu

    def start(self) -> None:
        """Starts the system tray icon in a dedicated daemon thread."""
        self._icon = pystray.Icon(
            name="OFFLINE11",
            icon=self._image,
            title="OFFLINE 11 — Strict PC Curfew",
            menu=self._create_menu(),
        )

        def _run() -> None:
            try:
                self._icon.run()
            except Exception as e:
                logging.error(f"System tray icon error: {e}")

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stops and removes the system tray icon."""
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:
                pass
            self._icon = None
