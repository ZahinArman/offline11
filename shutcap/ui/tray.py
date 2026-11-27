"""
System tray icon and menu for ShutCap (pystray).
"""

from __future__ import annotations

import logging
import sys
import threading
from pathlib import Path
from typing import Callable, Optional

import pystray
from PIL import Image
from pystray import Menu, MenuItem


def _icon_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", "")) / "assets" / "icon.png"
    return Path(__file__).resolve().parent.parent.parent / "assets" / "icon.png"


class SystemTray:
    """The icon near the clock. Left-click opens ShutCap; the menu has the rest."""

    def __init__(
        self,
        status_text: Callable[[], str],
        on_open: Callable[[], None],
        on_settings: Callable[[], None],
        on_history: Callable[[], None],
        on_quit: Callable[[], None],
        icon_path: Optional[Path] = None,
    ) -> None:
        self.status_text = status_text
        self.on_open = on_open
        self.on_settings = on_settings
        self.on_history = on_history
        self.on_quit = on_quit
        self._image = Image.open(icon_path or _icon_path())
        self._icon: Optional[pystray.Icon] = None

    def _menu(self) -> Menu:
        return Menu(
            MenuItem("Open ShutCap", lambda: self.on_open(), default=True),
            MenuItem(lambda _item: self.status_text(), None, enabled=False),
            Menu.SEPARATOR,
            MenuItem("Settings", lambda: self.on_settings()),
            MenuItem("History", lambda: self.on_history()),
            Menu.SEPARATOR,
            MenuItem("Quit ShutCap", lambda: self.on_quit()),
        )

    def start(self) -> None:
        self._icon = pystray.Icon(name="ShutCap", icon=self._image, title="ShutCap", menu=self._menu())

        def _run() -> None:
            try:
                self._icon.run()
            except Exception as e:
                logging.error(f"System tray icon error: {e}")

        threading.Thread(target=_run, daemon=True, name="shutcap-tray").start()

    def refresh(self) -> None:
        if self._icon is not None:
            try:
                self._icon.update_menu()
            except Exception:
                pass

    def stop(self) -> None:
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:
                pass
            self._icon = None
