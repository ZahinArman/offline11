"""
Settings Dialog for OFFLINE 11.
Allows configuring schedule milestones, dry-run mode, autostart, and push notifications.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from offline11.autostart import disable_autostart, enable_autostart, is_autostart_enabled
from offline11.config import Config, ConfigManager
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


class SettingsDialog(tk.Toplevel):
    """Settings configuration dialog."""

    def __init__(
        self,
        parent: tk.Tk,
        config_mgr: ConfigManager,
        on_save_callback: Callable[[Config], None],
    ) -> None:
        super().__init__(parent)
        self.config_mgr = config_mgr
        self.config = config_mgr.config
        self.on_save_callback = on_save_callback

        self.title("SETTINGS — OFFLINE 11")
        self.configure(bg=BG_DARK)
        self.geometry("540x580")
        self.resizable(False, False)

        self._build_ui()
        self._load_values()
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
        title_lbl = tk.Label(
            container,
            text="UTILITY SETTINGS",
            font=FONT_TITLE,
            fg=TEXT_PRIMARY,
            bg=BG_DARK,
        )
        title_lbl.pack(anchor="w", pady=(0, 16))

        # Schedule Section
        sched_frame = tk.LabelFrame(
            container,
            text=" Daily Curfew Schedule (HH:MM 24-Hour) ",
            font=FONT_BODY_BOLD,
            fg=TEXT_SECONDARY,
            bg=BG_DARK,
            padx=16,
            pady=12,
            highlightbackground=BORDER_COLOR,
            highlightthickness=1,
        )
        sched_frame.pack(fill=tk.X, pady=(0, 16))

        self.entries = {}
        fields = [
            ("First Warning (Default 22:30):", "warning_1_time"),
            ("Final Warning (Default 22:50):", "warning_2_time"),
            ("Curfew Begins (Default 23:00):", "curfew_time"),
            ("Grace Reminder 1 (Default 23:05):", "grace_reminder_1_time"),
            ("Grace Reminder 2 (Default 23:10):", "grace_reminder_2_time"),
            ("Final 1-Min Warning (Default 23:14):", "final_warning_time"),
            ("Shutdown Time (Default 23:15):", "shutdown_time"),
        ]

        for i, (label_text, field_name) in enumerate(fields):
            lbl = tk.Label(
                sched_frame,
                text=label_text,
                font=FONT_BODY,
                fg=TEXT_PRIMARY,
                bg=BG_DARK,
                anchor="w",
            )
            lbl.grid(row=i, column=0, sticky="w", pady=3)

            entry = tk.Entry(
                sched_frame,
                font=FONT_BODY,
                bg=BG_INPUT,
                fg=TEXT_PRIMARY,
                insertbackground=TEXT_PRIMARY,
                width=10,
                relief=tk.FLAT,
                highlightthickness=1,
                highlightbackground=BORDER_COLOR,
            )
            entry.grid(row=i, column=1, sticky="e", pady=3, padx=(10, 0))
            self.entries[field_name] = entry

        # Enforcement & Options Section
        opt_frame = tk.LabelFrame(
            container,
            text=" Enforcement & System Options ",
            font=FONT_BODY_BOLD,
            fg=TEXT_SECONDARY,
            bg=BG_DARK,
            padx=16,
            pady=12,
            highlightbackground=BORDER_COLOR,
            highlightthickness=1,
        )
        opt_frame.pack(fill=tk.X, pady=(0, 16))

        # Dry Run
        self.dry_run_var = tk.BooleanVar()
        self.dry_run_check = tk.Checkbutton(
            opt_frame,
            text="Dry-Run Mode (Simulate shutdowns safely without turning off PC)",
            variable=self.dry_run_var,
            bg=BG_DARK,
            fg=TEXT_PRIMARY,
            activebackground=BG_DARK,
            activeforeground=TEXT_PRIMARY,
            selectcolor=BG_SURFACE,
            font=FONT_BODY,
        )
        self.dry_run_check.pack(anchor="w", pady=2)

        # Autostart
        self.autostart_var = tk.BooleanVar()
        self.autostart_check = tk.Checkbutton(
            opt_frame,
            text="Start OFFLINE 11 automatically when Windows boots",
            variable=self.autostart_var,
            bg=BG_DARK,
            fg=TEXT_PRIMARY,
            activebackground=BG_DARK,
            activeforeground=TEXT_PRIMARY,
            selectcolor=BG_SURFACE,
            font=FONT_BODY,
        )
        self.autostart_check.pack(anchor="w", pady=2)

        # Sound
        self.sound_var = tk.BooleanVar()
        self.sound_check = tk.Checkbutton(
            opt_frame,
            text="Play audio chimes on warnings and curfew",
            variable=self.sound_var,
            bg=BG_DARK,
            fg=TEXT_PRIMARY,
            activebackground=BG_DARK,
            activeforeground=TEXT_PRIMARY,
            selectcolor=BG_SURFACE,
            font=FONT_BODY,
        )
        self.sound_check.pack(anchor="w", pady=2)

        # Android Push via ntfy
        push_row = tk.Frame(opt_frame, bg=BG_DARK)
        push_row.pack(fill=tk.X, pady=(6, 2))

        self.ntfy_var = tk.BooleanVar()
        self.ntfy_check = tk.Checkbutton(
            push_row,
            text="Android Push (ntfy.sh topic):",
            variable=self.ntfy_var,
            bg=BG_DARK,
            fg=TEXT_PRIMARY,
            activebackground=BG_DARK,
            activeforeground=TEXT_PRIMARY,
            selectcolor=BG_SURFACE,
            font=FONT_BODY,
        )
        self.ntfy_check.pack(side=tk.LEFT)

        self.ntfy_topic_entry = tk.Entry(
            push_row,
            font=FONT_BODY,
            bg=BG_INPUT,
            fg=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY,
            width=20,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
        )
        self.ntfy_topic_entry.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(8, 0))

        # Bottom Buttons
        btn_row = tk.Frame(container, bg=BG_DARK)
        btn_row.pack(fill=tk.X, side=tk.BOTTOM)

        save_btn = tk.Button(
            btn_row,
            text="SAVE SETTINGS",
            font=FONT_BODY_BOLD,
            bg=BG_BUTTON,
            fg=TEXT_PRIMARY,
            activebackground=BG_BUTTON_HOVER,
            activeforeground=TEXT_PRIMARY,
            relief=tk.FLAT,
            padx=20,
            pady=8,
            command=self._save_settings,
        )
        save_btn.pack(side=tk.LEFT, padx=(0, 8))

        cancel_btn = tk.Button(
            btn_row,
            text="CANCEL",
            font=FONT_BODY,
            bg=BG_BUTTON,
            fg=TEXT_SECONDARY,
            activebackground=BG_BUTTON_HOVER,
            activeforeground=TEXT_PRIMARY,
            relief=tk.FLAT,
            padx=16,
            pady=8,
            command=self.destroy,
        )
        cancel_btn.pack(side=tk.LEFT)

    def _load_values(self) -> None:
        for field, entry in self.entries.items():
            entry.delete(0, tk.END)
            entry.insert(0, getattr(self.config, field))

        self.dry_run_var.set(self.config.dry_run)
        self.autostart_var.set(is_autostart_enabled())
        self.sound_var.set(self.config.sound_enabled)
        self.ntfy_var.set(self.config.ntfy_enabled)
        self.ntfy_topic_entry.delete(0, tk.END)
        self.ntfy_topic_entry.insert(0, self.config.ntfy_topic)

    def _save_settings(self) -> None:
        # Build updated config
        new_dict = self.config.to_dict()
        for field, entry in self.entries.items():
            new_dict[field] = entry.get().strip()

        new_dict["dry_run"] = self.dry_run_var.get()
        new_dict["sound_enabled"] = self.sound_var.get()
        new_dict["ntfy_enabled"] = self.ntfy_var.get()
        new_dict["ntfy_topic"] = self.ntfy_topic_entry.get().strip()
        new_dict["autostart"] = self.autostart_var.get()

        try:
            updated_config = Config.from_dict(new_dict)
            updated_config.validate()
        except ValueError as e:
            messagebox.showerror("Invalid Schedule", str(e), parent=self)
            return

        # Check if dry-run is being turned off
        if self.config.dry_run and not updated_config.dry_run:
            warn = messagebox.askyesno(
                "Warning: Live Shutdown Enforcement",
                "You are disabling Dry-Run mode.\n\n"
                "OFFLINE 11 will now issue REAL shutdown commands at curfew.\n"
                "Are you sure you want to proceed with live enforcement?",
                parent=self,
            )
            if not warn:
                return

        # Update Windows autostart registry
        if self.autostart_var.get():
            enable_autostart()
        else:
            disable_autostart()

        # Save to file
        self.config_mgr.save(updated_config)
        self.on_save_callback(updated_config)
        messagebox.showinfo("Settings Saved", "Schedule and settings saved successfully.", parent=self)
        self.destroy()
