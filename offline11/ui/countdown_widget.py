"""
Persistent floating countdown widget for OFFLINE 11.
Stays topmost during the 11:00 PM - 11:15 PM shutdown grace period,
showing remaining time in large monospace format.
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
    BORDER_COLOR,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_CAPTION,
    FONT_MONO_LARGE,
    TEXT_DANGER,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class CountdownWidget(tk.Toplevel):
    """Floating persistent countdown widget during curfew grace period."""

    def __init__(
        self,
        parent: tk.Tk,
        on_emergency_click: Callable[[], None],
        is_dry_run: bool = True,
    ) -> None:
        super().__init__(parent)
        self.on_emergency_click = on_emergency_click
        self.is_dry_run = is_dry_run

        self.title("CURFEW COUNTDOWN — OFFLINE 11")
        self.configure(bg=BG_DARK)
        self.overrideredirect(False)  # Keep window frame for moving/docking
        self.geometry("380x170")
        self.resizable(False, False)

        # Always topmost
        self.attributes("-topmost", True)

        self._build_ui()
        self._position_top_right()

    def _position_top_right(self) -> None:
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        x = sw - 410
        y = 40
        self.geometry(f"+{x}+{y}")

    def _build_ui(self) -> None:
        frame = tk.Frame(self, bg=BG_DARK, padx=16, pady=12)
        frame.pack(fill=tk.BOTH, expand=True)

        # Top info row
        header_row = tk.Frame(frame, bg=BG_DARK)
        header_row.pack(fill=tk.X)

        title_lbl = tk.Label(
            header_row,
            text="PC SHUTDOWN IN PROGRESS",
            font=FONT_CAPTION,
            fg=TEXT_SECONDARY,
            bg=BG_DARK,
        )
        title_lbl.pack(side=tk.LEFT)

        if self.is_dry_run:
            dry_badge = tk.Label(
                header_row,
                text="[ DRY RUN ]",
                font=FONT_CAPTION,
                fg=TEXT_SECONDARY,
                bg=BG_SURFACE,
                padx=4,
            )
            dry_badge.pack(side=tk.RIGHT)

        # Large Digital Countdown
        self.countdown_label = tk.Label(
            frame,
            text="15:00",
            font=FONT_MONO_LARGE,
            fg=TEXT_PRIMARY,
            bg=BG_DARK,
            pady=4,
        )
        self.countdown_label.pack(fill=tk.X)

        # Subtext instruction
        self.msg_label = tk.Label(
            frame,
            text="Save your files and close all open applications.",
            font=FONT_BODY,
            fg=TEXT_SECONDARY,
            bg=BG_DARK,
        )
        self.msg_label.pack(fill=tk.X, pady=(0, 8))

        # Action button
        btn_row = tk.Frame(frame, bg=BG_DARK)
        btn_row.pack(fill=tk.X)

        emerg_btn = tk.Button(
            btn_row,
            text="Declare Genuine Emergency",
            font=FONT_CAPTION,
            bg=BG_SURFACE,
            fg=TEXT_DANGER,
            activebackground=BG_BUTTON_HOVER,
            activeforeground=TEXT_PRIMARY,
            relief=tk.FLAT,
            command=self.on_emergency_click,
            pady=3,
        )
        emerg_btn.pack(side=tk.RIGHT)

    def update_remaining(self, remaining_seconds: float) -> None:
        """Updates the countdown display with mm:ss."""
        rem = max(0, int(remaining_seconds))
        mins = rem // 60
        secs = rem % 60
        time_str = f"{mins:02d}:{secs:02d}"
        self.countdown_label.config(text=time_str)

        if rem <= 60:
            self.countdown_label.config(fg=TEXT_DANGER)
            self.msg_label.config(text="Final minute! Shutdown is imminent.", fg=TEXT_DANGER)
        elif rem <= 300:
            self.countdown_label.config(fg="#FFA500")
            self.msg_label.config(text="5 minutes remaining! Finish winding down.", fg="#FFA500")
        else:
            self.countdown_label.config(fg=TEXT_PRIMARY)
            self.msg_label.config(text="Save your files and close all open applications.", fg=TEXT_SECONDARY)
