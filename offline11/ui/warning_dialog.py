"""
Warning Popup Dialog for OFFLINE 11.
Prominent, topmost on-screen window displayed at warning milestones
(30-minute warning, 10-minute warning, and grace period countdowns).
Guarantees visual notice regardless of Windows notification center or Focus Assist settings.
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

from offline11.ui.theme import (
    BG_BUTTON,
    BG_BUTTON_HOVER,
    BG_CRITICAL,
    BG_DARK,
    BG_SURFACE,
    BG_WARNING,
    BORDER_COLOR,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_CAPTION,
    FONT_HEADING,
    FONT_TITLE,
    TEXT_DANGER,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class WarningDialog(tk.Toplevel):
    """
    Topmost visual alert popup for curfew warnings.
    Appears over all applications and games.
    Automatically closes after auto_close_seconds if unattended.
    """

    def __init__(
        self,
        parent: tk.Tk,
        tag_text: str,
        title: str,
        message: str,
        level: str = "warning",
        auto_close_seconds: int = 30,
        on_open_dashboard: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(parent)
        self.level = level
        self.remaining_seconds = auto_close_seconds
        self.on_open_dashboard = on_open_dashboard

        self.title(f"OFFLINE 11 — {title}")
        self.configure(bg=BG_DARK)
        self.geometry("480x250")
        self.resizable(False, False)

        # Force window to stay topmost above full-screen games/apps
        self.attributes("-topmost", True)
        self.lift()
        self.focus_force()

        self._build_ui(tag_text, title, message)
        self._center_window()
        self._start_countdown()

    def _center_window(self) -> None:
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - w) // 2
        y = max(40, (sh - h) // 3)  # Slightly above center for immediate eye-level notice
        self.geometry(f"+{x}+{y}")

    def _build_ui(self, tag_text: str, title: str, message: str) -> None:
        accent_color = TEXT_DANGER if self.level in ("critical", "urgent") else "#F59E0B"
        bg_card = BG_CRITICAL if self.level == "critical" else BG_SURFACE

        container = tk.Frame(self, bg=BG_DARK, padx=24, pady=20)
        container.pack(fill=tk.BOTH, expand=True)

        # Tag header
        tag_lbl = tk.Label(
            container,
            text=f"[ {tag_text.upper()} ]",
            font=FONT_CAPTION,
            fg=accent_color,
            bg=BG_DARK,
            anchor="w",
        )
        tag_lbl.pack(fill=tk.X, pady=(0, 6))

        # Main alert card
        card = tk.Frame(
            container,
            bg=bg_card,
            padx=16,
            pady=14,
            highlightbackground=BORDER_COLOR,
            highlightthickness=1,
        )
        card.pack(fill=tk.BOTH, expand=True, pady=(0, 14))

        # Big alert title
        title_lbl = tk.Label(
            card,
            text=title,
            font=("Segoe UI", 14, "bold"),
            fg=TEXT_PRIMARY,
            bg=bg_card,
            anchor="w",
        )
        title_lbl.pack(fill=tk.X, pady=(0, 6))

        # Detailed message body
        msg_lbl = tk.Label(
            card,
            text=message,
            font=FONT_BODY,
            fg=TEXT_SECONDARY if self.level != "critical" else TEXT_PRIMARY,
            bg=bg_card,
            anchor="w",
            justify="left",
            wraplength=410,
        )
        msg_lbl.pack(fill=tk.X)

        # Bottom buttons row
        btn_row = tk.Frame(container, bg=BG_DARK)
        btn_row.pack(fill=tk.X)

        self.countdown_lbl = tk.Label(
            btn_row,
            text=f"Auto-closing in {self.remaining_seconds}s...",
            font=FONT_CAPTION,
            fg=TEXT_SECONDARY,
            bg=BG_DARK,
        )
        self.countdown_lbl.pack(side=tk.LEFT)

        dismiss_btn = tk.Button(
            btn_row,
            text="I UNDERSTAND",
            font=FONT_BODY_BOLD,
            bg=BG_BUTTON,
            fg=TEXT_PRIMARY,
            activebackground=BG_BUTTON_HOVER,
            activeforeground=TEXT_PRIMARY,
            relief=tk.FLAT,
            padx=14,
            pady=4,
            command=self._dismiss,
        )
        dismiss_btn.pack(side=tk.RIGHT)

        if self.on_open_dashboard:
            dash_btn = tk.Button(
                btn_row,
                text="OPEN DASHBOARD",
                font=FONT_BODY,
                bg=BG_DARK,
                fg=TEXT_SECONDARY,
                activebackground=BG_BUTTON,
                activeforeground=TEXT_PRIMARY,
                relief=tk.FLAT,
                padx=10,
                pady=4,
                command=self._open_dashboard_and_dismiss,
            )
            dash_btn.pack(side=tk.RIGHT, padx=(0, 8))

    def _start_countdown(self) -> None:
        if self.remaining_seconds > 0:
            self.countdown_lbl.config(text=f"Auto-closing in {self.remaining_seconds}s...")
            self.remaining_seconds -= 1
            self.after(1000, self._start_countdown)
        else:
            self._dismiss()

    def _dismiss(self) -> None:
        try:
            self.destroy()
        except Exception:
            pass

    def _open_dashboard_and_dismiss(self) -> None:
        if self.on_open_dashboard:
            self.on_open_dashboard()
        self._dismiss()
