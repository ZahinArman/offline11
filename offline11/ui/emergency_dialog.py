"""
Emergency declaration dialog for OFFLINE 11.
Requires explicit reason and confirmation before granting a 1-night curfew exception.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from offline11.ui.theme import (
    BG_BUTTON,
    BG_BUTTON_HOVER,
    BG_DARK,
    BG_INPUT,
    BG_SURFACE,
    BORDER_COLOR,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_CAPTION,
    FONT_HEADING,
    FONT_TITLE,
    TEXT_DANGER,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class EmergencyDialog(tk.Toplevel):
    """Modal dialog prompting for emergency reason and confirmation."""

    def __init__(self, parent: tk.Tk, on_confirm: Callable[[str], None]) -> None:
        super().__init__(parent)
        self.on_confirm = on_confirm
        self.title("GENUINE EMERGENCY DECLARATION — OFFLINE 11")
        self.configure(bg=BG_DARK)
        self.geometry("520x420")
        self.resizable(False, False)

        # Center on screen and keep on top
        self.attributes("-topmost", True)
        self.transient(parent)
        self.grab_set()

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
        container = tk.Frame(self, bg=BG_DARK, padx=24, pady=20)
        container.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = tk.Label(
            container,
            text="GENUINE EMERGENCY EXCEPTION",
            font=FONT_TITLE,
            fg=TEXT_PRIMARY,
            bg=BG_DARK,
            anchor="w",
        )
        title_label.pack(fill=tk.X, pady=(0, 8))

        # Self-discipline notice
        notice_box = tk.Frame(container, bg=BG_SURFACE, padx=12, pady=10, highlightbackground=BORDER_COLOR, highlightthickness=1)
        notice_box.pack(fill=tk.X, pady=(0, 16))

        notice_text = (
            "Self-discipline reminder:\n"
            "Ordinary gaming, browsing, entertainment, procrastination, or routine coursework "
            "do NOT qualify as genuine emergencies.\n\n"
            "This exception will cancel tonight's scheduled shutdown and record your reason to the audit log."
        )
        notice_lbl = tk.Label(
            notice_box,
            text=notice_text,
            font=FONT_CAPTION,
            fg=TEXT_SECONDARY,
            bg=BG_SURFACE,
            justify=tk.LEFT,
            wraplength=450,
        )
        notice_lbl.pack(fill=tk.X)

        # Reason prompt
        reason_lbl = tk.Label(
            container,
            text="Reason for tonight's emergency exception:",
            font=FONT_BODY_BOLD,
            fg=TEXT_PRIMARY,
            bg=BG_DARK,
            anchor="w",
        )
        reason_lbl.pack(fill=tk.X, pady=(0, 6))

        # Text area
        self.reason_text = tk.Text(
            container,
            height=4,
            bg=BG_INPUT,
            fg=TEXT_PRIMARY,
            font=FONT_BODY,
            insertbackground=TEXT_PRIMARY,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
            padx=8,
            pady=8,
        )
        self.reason_text.pack(fill=tk.X, pady=(0, 12))
        self.reason_text.bind("<KeyRelease>", lambda e: self._check_validity())

        # Confirmation Checkbox
        self.confirm_var = tk.BooleanVar(value=False)
        self.confirm_check = tk.Checkbutton(
            container,
            text="I confirm under my own personal accountability that this is a genuine emergency.",
            variable=self.confirm_var,
            command=self._check_validity,
            bg=BG_DARK,
            fg=TEXT_PRIMARY,
            activebackground=BG_DARK,
            activeforeground=TEXT_PRIMARY,
            selectcolor=BG_SURFACE,
            font=FONT_CAPTION,
            wraplength=450,
            justify=tk.LEFT,
        )
        self.confirm_check.pack(fill=tk.X, pady=(0, 20))

        # Button row
        btn_row = tk.Frame(container, bg=BG_DARK)
        btn_row.pack(fill=tk.X, side=tk.BOTTOM)

        self.submit_btn = tk.Button(
            btn_row,
            text="CONFIRM EMERGENCY EXCEPTION",
            font=FONT_BODY_BOLD,
            bg=BG_SURFACE,
            fg=TEXT_MUTED,
            activebackground=BG_BUTTON_HOVER,
            activeforeground=TEXT_PRIMARY,
            relief=tk.FLAT,
            padx=16,
            pady=8,
            state=tk.DISABLED,
            command=self._on_submit,
        )
        self.submit_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 8))

        cancel_btn = tk.Button(
            btn_row,
            text="CANCEL",
            font=FONT_BODY,
            bg=BG_BUTTON,
            fg=TEXT_PRIMARY,
            activebackground=BG_BUTTON_HOVER,
            activeforeground=TEXT_PRIMARY,
            relief=tk.FLAT,
            padx=16,
            pady=8,
            command=self.destroy,
        )
        cancel_btn.pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=(8, 0))

    def _check_validity(self) -> None:
        reason = self.reason_text.get("1.0", tk.END).strip()
        if len(reason) >= 1 and self.confirm_var.get():
            self.submit_btn.config(state=tk.NORMAL, fg=TEXT_DANGER, bg=BG_SURFACE)
        else:
            self.submit_btn.config(state=tk.DISABLED, fg=TEXT_MUTED, bg=BG_SURFACE)

    def _on_submit(self) -> None:
        reason = self.reason_text.get("1.0", tk.END).strip()
        if reason and self.confirm_var.get():
            try:
                self.grab_release()
            except Exception:
                pass
            self.destroy()
            self.on_confirm(reason)
