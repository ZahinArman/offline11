"""
Audit trail viewer dialog for OFFLINE 11.
Displays timestamps, curfew decisions, warnings, emergency exceptions, and shutdowns.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import List

from offline11.logger import AuditEntry, AuditLogger
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
    FONT_MONO,
    FONT_TITLE,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class AuditDialog(tk.Toplevel):
    """Viewer window for the curfew audit log."""

    def __init__(self, parent: tk.Tk, audit_logger: AuditLogger) -> None:
        super().__init__(parent)
        self.audit_logger = audit_logger

        self.title("AUDIT LOG — OFFLINE 11")
        self.configure(bg=BG_DARK)
        self.geometry("740x500")
        self.minsize(600, 380)

        self._build_ui()
        self._load_entries()
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
        container = tk.Frame(self, bg=BG_DARK, padx=20, pady=16)
        container.pack(fill=tk.BOTH, expand=True)

        # Header
        header = tk.Frame(container, bg=BG_DARK)
        header.pack(fill=tk.X, pady=(0, 12))

        title = tk.Label(
            header,
            text="CURFEW AUDIT TRAIL",
            font=FONT_TITLE,
            fg=TEXT_PRIMARY,
            bg=BG_DARK,
        )
        title.pack(side=tk.LEFT)

        subtitle = tk.Label(
            header,
            text="Local log of curfew events & emergency exceptions",
            font=FONT_CAPTION,
            fg=TEXT_SECONDARY,
            bg=BG_DARK,
        )
        subtitle.pack(side=tk.LEFT, padx=(12, 0), pady=(4, 0))

        # Log Text Box with Scrollbar
        list_frame = tk.Frame(
            container,
            bg=BG_INPUT,
            highlightbackground=BORDER_COLOR,
            highlightthickness=1,
        )
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 16))

        self.scrollbar = tk.Scrollbar(list_frame)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.text_area = tk.Text(
            list_frame,
            bg=BG_INPUT,
            fg=TEXT_PRIMARY,
            font=FONT_MONO,
            wrap=tk.WORD,
            yscrollcommand=self.scrollbar.set,
            relief=tk.FLAT,
            padx=10,
            pady=10,
        )
        self.text_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.config(command=self.text_area.yview)

        # Bottom Buttons
        btn_row = tk.Frame(container, bg=BG_DARK)
        btn_row.pack(fill=tk.X)

        refresh_btn = tk.Button(
            btn_row,
            text="REFRESH",
            font=FONT_BODY,
            bg=BG_BUTTON,
            fg=TEXT_PRIMARY,
            activebackground=BG_BUTTON_HOVER,
            activeforeground=TEXT_PRIMARY,
            relief=tk.FLAT,
            padx=12,
            pady=6,
            command=self._load_entries,
        )
        refresh_btn.pack(side=tk.LEFT, padx=(0, 8))

        export_btn = tk.Button(
            btn_row,
            text="EXPORT LOG...",
            font=FONT_BODY,
            bg=BG_BUTTON,
            fg=TEXT_PRIMARY,
            activebackground=BG_BUTTON_HOVER,
            activeforeground=TEXT_PRIMARY,
            relief=tk.FLAT,
            padx=12,
            pady=6,
            command=self._export_log,
        )
        export_btn.pack(side=tk.LEFT, padx=(0, 8))

        clear_btn = tk.Button(
            btn_row,
            text="CLEAR LOG",
            font=FONT_BODY,
            bg=BG_BUTTON,
            fg="#EF4444",
            activebackground=BG_BUTTON_HOVER,
            activeforeground="#EF4444",
            relief=tk.FLAT,
            padx=12,
            pady=6,
            command=self._clear_log,
        )
        clear_btn.pack(side=tk.LEFT)

        close_btn = tk.Button(
            btn_row,
            text="CLOSE",
            font=FONT_BODY,
            bg=BG_BUTTON,
            fg=TEXT_PRIMARY,
            activebackground=BG_BUTTON_HOVER,
            activeforeground=TEXT_PRIMARY,
            relief=tk.FLAT,
            padx=16,
            pady=6,
            command=self.destroy,
        )
        close_btn.pack(side=tk.RIGHT)

    def _load_entries(self) -> None:
        self.text_area.config(state=tk.NORMAL)
        self.text_area.delete("1.0", tk.END)

        entries = self.audit_logger.get_entries()
        if not entries:
            self.text_area.insert(tk.END, "No audit events recorded yet.\n")
        else:
            for entry in entries:
                self.text_area.insert(tk.END, entry.to_line() + "\n")

        self.text_area.see(tk.END)
        self.text_area.config(state=tk.DISABLED)

    def _export_log(self) -> None:
        file_path = filedialog.asksaveasfilename(
            parent=self,
            title="Export OFFLINE 11 Audit Log",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("Log files", "*.log"), ("All files", "*.*")],
        )
        if file_path:
            try:
                entries = self.audit_logger.get_entries()
                with open(file_path, "w", encoding="utf-8") as f:
                    for entry in entries:
                        f.write(entry.to_line() + "\n")
                messagebox.showinfo("Export Successful", f"Audit log exported to:\n{file_path}", parent=self)
            except Exception as e:
                messagebox.showerror("Export Failed", f"Error saving file: {e}", parent=self)

    def _clear_log(self) -> None:
        confirm = messagebox.askyesno(
            "Clear Audit Log",
            "Are you sure you want to clear the audit log?\n\nAll recorded entries will be deleted.",
            parent=self,
        )
        if confirm:
            self.audit_logger.clear()
            self._load_entries()
            messagebox.showinfo("Log Cleared", "The audit log has been cleared.", parent=self)
