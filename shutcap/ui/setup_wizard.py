"""
First-run setup for ShutCap.

Screen 1: "When should your PC turn off each night?"
Screen 2: the warning times worked out from that, which the user can change.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Callable, Dict

from shutcap.config import DEFAULT_MINUTES_BEFORE_SHUTDOWN, Config, ConfigManager
from shutcap.ui.theme import (
    BG_BUTTON,
    BG_BUTTON_HOVER,
    BG_DARK,
    BG_INPUT,
    BG_SURFACE,
    BORDER_COLOR,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_CAPTION,
    FONT_MONO_XLARGE,
    FONT_TITLE,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)

ROWS = [
    ("warning_1_time", "First warning"),
    ("warning_2_time", "Second warning"),
    ("curfew_time", "Curfew starts (countdown begins)"),
    ("grace_reminder_1_time", "Reminder"),
    ("grace_reminder_2_time", "Reminder"),
    ("final_warning_time", "Last-minute warning"),
    ("shutdown_time", "PC turns off"),
]


class SetupWizard(tk.Toplevel):
    """Two-screen first-run setup. Calls on_done(config) when finished or closed."""

    def __init__(self, parent: tk.Tk, config_mgr: ConfigManager, on_done: Callable[[Config], None]) -> None:
        super().__init__(parent)
        self.config_mgr = config_mgr
        self.on_done = on_done
        self._finished = False

        self.title("Welcome to ShutCap")
        self.configure(bg=BG_DARK)
        self.geometry("520x560")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        shutdown = Config.parse_time_str(config_mgr.config.shutdown_time)
        self.hour_var = tk.StringVar(value=f"{shutdown.hour:02d}")
        self.minute_var = tk.StringVar(value=f"{shutdown.minute:02d}")
        self.practice_var = tk.BooleanVar(value=config_mgr.config.dry_run)
        self.entries: Dict[str, tk.Entry] = {}

        self.body = tk.Frame(self, bg=BG_DARK, padx=28, pady=24)
        self.body.pack(fill=tk.BOTH, expand=True)
        self._show_time_screen()
        self._center()
        self.lift()
        self.focus_force()

    # --- helpers -------------------------------------------------------------------------

    def _center(self) -> None:
        self.update_idletasks()
        x = (self.winfo_screenwidth() - self.winfo_width()) // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _clear(self) -> None:
        for child in self.body.winfo_children():
            child.destroy()

    def _button(self, parent: tk.Widget, text: str, command: Callable[[], None], primary: bool = False) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            font=FONT_BODY_BOLD if primary else FONT_BODY,
            bg=BG_BUTTON if primary else BG_SURFACE,
            fg=TEXT_PRIMARY if primary else TEXT_SECONDARY,
            activebackground=BG_BUTTON_HOVER,
            activeforeground=TEXT_PRIMARY,
            relief=tk.FLAT,
            padx=18,
            pady=8,
            command=command,
        )

    def _chosen_time(self) -> str:
        try:
            hour, minute = int(self.hour_var.get()), int(self.minute_var.get())
        except ValueError:
            raise ValueError("Enter the hour (0-23) and minute (0-59) as numbers.")
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError("Enter an hour from 0 to 23 and a minute from 0 to 59.")
        return f"{hour:02d}:{minute:02d}"

    # --- screen 1 ------------------------------------------------------------------------

    def _show_time_screen(self) -> None:
        self._clear()
        tk.Label(self.body, text="STEP 1 OF 2", font=FONT_CAPTION, fg=TEXT_SECONDARY, bg=BG_DARK).pack(anchor="w")
        tk.Label(self.body, text="When should your PC turn off each night?", font=FONT_TITLE,
                 fg=TEXT_PRIMARY, bg=BG_DARK, wraplength=460, justify=tk.LEFT).pack(anchor="w", pady=(4, 8))
        tk.Label(
            self.body,
            text="ShutCap warns you before this time, then turns the PC off once. "
                 "If you turn the PC on again later that night, ShutCap does not stop you.",
            font=FONT_BODY, fg=TEXT_SECONDARY, bg=BG_DARK, wraplength=460, justify=tk.LEFT,
        ).pack(anchor="w", pady=(0, 28))

        picker = tk.Frame(self.body, bg=BG_DARK)
        picker.pack(pady=(10, 6))
        spin_opts = dict(font=FONT_MONO_XLARGE, width=3, justify=tk.CENTER, wrap=True, bg=BG_INPUT, fg=TEXT_PRIMARY,
                         buttonbackground=BG_SURFACE, insertbackground=TEXT_PRIMARY, relief=tk.FLAT,
                         highlightthickness=1, highlightbackground=BORDER_COLOR)
        hour = tk.Spinbox(picker, from_=0, to=23, format="%02.0f", textvariable=self.hour_var, **spin_opts)
        hour.pack(side=tk.LEFT)
        tk.Label(picker, text=":", font=FONT_MONO_XLARGE, fg=TEXT_PRIMARY, bg=BG_DARK).pack(side=tk.LEFT, padx=6)
        minute = tk.Spinbox(picker, from_=0, to=59, format="%02.0f", textvariable=self.minute_var, **spin_opts)
        minute.pack(side=tk.LEFT)
        tk.Label(self.body, text="24-hour time, e.g. 23:15 or 00:30", font=FONT_CAPTION,
                 fg=TEXT_MUTED, bg=BG_DARK).pack(pady=(4, 0))

        nav = tk.Frame(self.body, bg=BG_DARK)
        nav.pack(side=tk.BOTTOM, fill=tk.X)
        self._button(nav, "NEXT", self._go_to_schedule, primary=True).pack(side=tk.RIGHT)

    def _go_to_schedule(self) -> None:
        try:
            chosen = self._chosen_time()
        except ValueError as e:
            messagebox.showerror("Check the time", str(e), parent=self)
            return
        self._show_schedule_screen(Config.schedule_for_shutdown(chosen))

    # --- screen 2 ------------------------------------------------------------------------

    def _show_schedule_screen(self, times: Dict[str, str]) -> None:
        self._clear()
        self.entries.clear()
        tk.Label(self.body, text="STEP 2 OF 2", font=FONT_CAPTION, fg=TEXT_SECONDARY, bg=BG_DARK).pack(anchor="w")
        tk.Label(self.body, text="Your nightly schedule", font=FONT_TITLE, fg=TEXT_PRIMARY, bg=BG_DARK).pack(anchor="w", pady=(4, 6))
        tk.Label(
            self.body,
            text="These are the recommended warning times. You can change any of them now or later in Settings.",
            font=FONT_BODY, fg=TEXT_SECONDARY, bg=BG_DARK, wraplength=460, justify=tk.LEFT,
        ).pack(anchor="w", pady=(0, 14))

        grid = tk.Frame(self.body, bg=BG_SURFACE, padx=16, pady=12, highlightbackground=BORDER_COLOR, highlightthickness=1)
        grid.pack(fill=tk.X)
        for row, (field_name, label) in enumerate(ROWS):
            before = DEFAULT_MINUTES_BEFORE_SHUTDOWN[field_name]
            hint = "your chosen time" if before == 0 else f"default: {before} min before"
            tk.Label(grid, text=label, font=FONT_BODY, fg=TEXT_PRIMARY, bg=BG_SURFACE, anchor="w").grid(row=row, column=0, sticky="w", pady=3)
            tk.Label(grid, text=hint, font=FONT_CAPTION, fg=TEXT_MUTED, bg=BG_SURFACE, anchor="w").grid(row=row, column=1, sticky="w", padx=(10, 10))
            entry = tk.Entry(grid, font=FONT_BODY, width=7, justify=tk.CENTER, bg=BG_INPUT, fg=TEXT_PRIMARY,
                             insertbackground=TEXT_PRIMARY, relief=tk.FLAT, highlightthickness=1, highlightbackground=BORDER_COLOR)
            entry.insert(0, times[field_name])
            if field_name == "shutdown_time":
                entry.config(state="readonly", readonlybackground=BG_SURFACE)
            entry.grid(row=row, column=2, sticky="e", pady=3)
            self.entries[field_name] = entry
        grid.columnconfigure(1, weight=1)

        tk.Checkbutton(
            self.body,
            text="Dry-run (practice) mode: show all warnings, but do not turn the PC off. You can change this later in Settings.",
            variable=self.practice_var, font=FONT_CAPTION, fg=TEXT_PRIMARY, bg=BG_DARK,
            activebackground=BG_DARK, activeforeground=TEXT_PRIMARY, selectcolor=BG_SURFACE,
            wraplength=440, justify=tk.LEFT,
        ).pack(anchor="w", pady=(14, 0))

        nav = tk.Frame(self.body, bg=BG_DARK)
        nav.pack(side=tk.BOTTOM, fill=tk.X)
        self._button(nav, "FINISH", self._finish, primary=True).pack(side=tk.RIGHT)
        self._button(nav, "BACK", self._show_time_screen).pack(side=tk.RIGHT, padx=(0, 8))

    def _finish(self) -> None:
        new_dict = self.config_mgr.config.to_dict()
        for field_name, entry in self.entries.items():
            new_dict[field_name] = entry.get().strip()
        new_dict["dry_run"] = self.practice_var.get()
        new_dict["setup_complete"] = True
        try:
            new_config = Config.from_dict(new_dict)
            new_config.validate()
        except ValueError as e:
            messagebox.showerror("Check the times", str(e), parent=self)
            return
        self._complete(new_config)

    def _on_close(self) -> None:
        # Closing keeps the current (default) schedule; it can be changed later in Settings.
        new_dict = self.config_mgr.config.to_dict()
        new_dict["setup_complete"] = True
        self._complete(Config.from_dict(new_dict))

    def _complete(self, config: Config) -> None:
        if self._finished:
            return
        self._finished = True
        self.config_mgr.save(config)
        self.destroy()
        self.on_done(config)
