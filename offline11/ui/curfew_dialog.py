"""
Curfew Dialog for OFFLINE 11.
Prominent, always-visible dialog displayed at 11:00 PM asking:
"PC TIME IS OVER. Is there a genuine emergency?"
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable

from offline11.ui.theme import (
    BG_BUTTON,
    BG_BUTTON_HOVER,
    BG_CRITICAL,
    BG_DARK,
    BG_SURFACE,
    BORDER_COLOR,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_HEADING,
    FONT_TITLE,
    TEXT_DANGER,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class CurfewDialog(tk.Toplevel):
    """
    Prominent curfew modal shown at 11:00 PM.
    Stays topmost. Closing it does NOT bypass curfew enforcement.
    """

    def __init__(
        self,
        parent: tk.Tk,
        on_no_emergency: Callable[[], None],
        on_genuine_emergency: Callable[[], None],
    ) -> None:
        super().__init__(parent)
        self.on_no_emergency = on_no_emergency
        self.on_genuine_emergency = on_genuine_emergency

        self.title("OFFLINE 11 — PC TIME IS OVER")
        self.configure(bg=BG_DARK)
        self.geometry("560x360")
        self.resizable(False, False)

        # Always topmost and focused
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", self._on_close_attempt)

        self._build_ui()
        self._center_window()

    def _center_window(self) -> None:
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"+{x}+{y}")

    def _build_ui(self) -> None:
        container = tk.Frame(self, bg=BG_DARK, padx=32, pady=28)
        container.pack(fill=tk.BOTH, expand=True)

        # Header tag
        tag = tk.Label(
            container,
            text="[ CURFEW ENFORCEMENT ]",
            font=FONT_BODY_BOLD,
            fg=TEXT_SECONDARY,
            bg=BG_DARK,
            anchor="center",
        )
        tag.pack(fill=tk.X, pady=(0, 10))

        # Big curfew message
        msg_title = tk.Label(
            container,
            text="PC TIME IS OVER.",
            font=("Segoe UI", 24, "bold"),
            fg=TEXT_PRIMARY,
            bg=BG_DARK,
            anchor="center",
        )
        msg_title.pack(fill=tk.X, pady=(0, 6))

        msg_question = tk.Label(
            container,
            text="Is there a genuine emergency?",
            font=FONT_HEADING,
            fg=TEXT_SECONDARY,
            bg=BG_DARK,
            anchor="center",
        )
        msg_question.pack(fill=tk.X, pady=(0, 20))

        # Information card
        info_card = tk.Frame(
            container,
            bg=BG_SURFACE,
            padx=16,
            pady=12,
            highlightbackground=BORDER_COLOR,
            highlightthickness=1,
        )
        info_card.pack(fill=tk.X, pady=(0, 24))

        info_text = (
            "Selecting NO EMERGENCY grants a 15-minute shutdown grace period (until 11:15 PM) "
            "to save your work and close applications.\n\n"
            "Ignoring this dialog will NOT cancel or delay the scheduled shutdown."
        )
        info_lbl = tk.Label(
            info_card,
            text=info_text,
            font=FONT_BODY,
            fg=TEXT_PRIMARY,
            bg=BG_SURFACE,
            justify=tk.CENTER,
            wraplength=460,
        )
        info_lbl.pack(fill=tk.X)

        # Action Buttons
        btn_frame = tk.Frame(container, bg=BG_DARK)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)

        no_emerg_btn = tk.Button(
            btn_frame,
            text="NO EMERGENCY\n(Accept Curfew & Begin Grace Countdown)",
            font=FONT_BODY_BOLD,
            bg=BG_BUTTON,
            fg=TEXT_PRIMARY,
            activebackground=BG_BUTTON_HOVER,
            activeforeground=TEXT_PRIMARY,
            relief=tk.FLAT,
            padx=16,
            pady=10,
            command=self._handle_no_emergency,
        )
        no_emerg_btn.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=(0, 8))

        gen_emerg_btn = tk.Button(
            btn_frame,
            text="GENUINE EMERGENCY\n(Declare Exception)",
            font=FONT_BODY_BOLD,
            bg=BG_SURFACE,
            fg=TEXT_DANGER,
            activebackground=BG_BUTTON_HOVER,
            activeforeground=TEXT_PRIMARY,
            relief=tk.FLAT,
            padx=16,
            pady=10,
            command=self._handle_genuine_emergency,
        )
        gen_emerg_btn.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH, padx=(8, 0))

    def _handle_no_emergency(self) -> None:
        self.destroy()
        self.on_no_emergency()

    def _handle_genuine_emergency(self) -> None:
        self.destroy()
        self.on_genuine_emergency()

    def _on_close_attempt(self) -> None:
        # Closing window does not bypass curfew. Dismissing window accepts curfew countdown.
        self.destroy()
        self.on_no_emergency()
