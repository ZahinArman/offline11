"""
Main application dashboard for OFFLINE 11.
Minimal dark monochrome interface displaying curfew state, schedule countdown,
and controls for settings, audit log, and emergency cancellation.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import messagebox
from typing import Callable, Optional

from offline11.config import Config, ConfigManager
from offline11.logger import AuditLogger
from offline11.scheduler import Scheduler
from offline11.state import CurfewStatus, StateManager
from offline11.time_provider import TimeProvider
from offline11.notifications import NotificationManager
from offline11.ui.audit_dialog import AuditDialog
from offline11.ui.curfew_dialog import CurfewDialog
from offline11.ui.countdown_widget import CountdownWidget
from offline11.ui.emergency_dialog import EmergencyDialog
from offline11.ui.settings_dialog import SettingsDialog
from offline11.ui.warning_dialog import WarningDialog
from offline11.ui.theme import (
    BG_BUTTON,
    BG_BUTTON_HOVER,
    BG_CRITICAL,
    BG_DARK,
    BG_INPUT,
    BG_SURFACE,
    BORDER_COLOR,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_CAPTION,
    FONT_HEADING,
    FONT_MONO,
    FONT_MONO_LARGE,
    FONT_SUBTITLE,
    FONT_TITLE,
    TEXT_ACCENT,
    TEXT_DANGER,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class MainWindow(tk.Tk):
    """Main window dashboard for OFFLINE 11."""

    def __init__(
        self,
        config_mgr: ConfigManager,
        state_mgr: StateManager,
        scheduler: Scheduler,
        audit_logger: AuditLogger,
        time_provider: TimeProvider,
        notifications: Optional[NotificationManager] = None,
        on_hide_to_tray: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__()
        self.config_mgr = config_mgr
        self.state_mgr = state_mgr
        self.scheduler = scheduler
        self.audit_logger = audit_logger
        self.time_provider = time_provider
        self.notifications = notifications
        self.on_hide_to_tray = on_hide_to_tray

        self.title("OFFLINE 11 — Strict PC Curfew")
        self.configure(bg=BG_DARK)
        self.geometry("520x560")
        self.minsize(480, 520)

        # Dialog instances
        self.curfew_dialog: Optional[CurfewDialog] = None
        self.countdown_widget: Optional[CountdownWidget] = None
        self.warning_dialog: Optional[WarningDialog] = None

        # Intercept window close to minimize to tray instead of quitting
        self.protocol("WM_DELETE_WINDOW", self.hide_to_tray)

        self._build_ui()
        self._center_window()
        self._update_display()

        # Connect scheduler callbacks
        self.scheduler.on_warning_1 = self._on_warning_1_event
        self.scheduler.on_warning_2 = self._on_warning_2_event
        self.scheduler.on_curfew_start = self._on_curfew_event
        self.scheduler.on_grace_reminder_1 = self._on_grace_reminder_1
        self.scheduler.on_grace_reminder_2 = self._on_grace_reminder_2
        self.scheduler.on_final_warning = self._on_final_warning
        self.scheduler.on_shutdown_executed = self._on_shutdown_executed
        self.scheduler.on_state_change = self._on_state_changed

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

        # Top Header Row
        header_row = tk.Frame(container, bg=BG_DARK)
        header_row.pack(fill=tk.X, pady=(0, 16))

        title_box = tk.Frame(header_row, bg=BG_DARK)
        title_box.pack(side=tk.LEFT)

        app_title = tk.Label(
            title_box,
            text="OFFLINE 11",
            font=FONT_TITLE,
            fg=TEXT_PRIMARY,
            bg=BG_DARK,
        )
        app_title.pack(anchor="w")

        app_sub = tk.Label(
            title_box,
            text="STRICT PC CURFEW UTILITY",
            font=FONT_CAPTION,
            fg=TEXT_SECONDARY,
            bg=BG_DARK,
        )
        app_sub.pack(anchor="w")

        self.mode_badge = tk.Label(
            header_row,
            text="[ DRY RUN ]" if self.config_mgr.config.dry_run else "[ LIVE ENFORCEMENT ]",
            font=FONT_BODY_BOLD,
            fg=TEXT_ACCENT if self.config_mgr.config.dry_run else TEXT_DANGER,
            bg=BG_SURFACE,
            padx=10,
            pady=4,
            relief=tk.FLAT,
            highlightbackground=BORDER_COLOR,
            highlightthickness=1,
        )
        self.mode_badge.pack(side=tk.RIGHT)

        # Status Card
        self.status_card = tk.Frame(
            container,
            bg=BG_SURFACE,
            padx=18,
            pady=16,
            highlightbackground=BORDER_COLOR,
            highlightthickness=1,
        )
        self.status_card.pack(fill=tk.X, pady=(0, 16))

        card_header = tk.Frame(self.status_card, bg=BG_SURFACE)
        card_header.pack(fill=tk.X, pady=(0, 8))

        status_lbl = tk.Label(
            card_header,
            text="SYSTEM STATUS",
            font=FONT_CAPTION,
            fg=TEXT_SECONDARY,
            bg=BG_SURFACE,
        )
        status_lbl.pack(side=tk.LEFT)

        self.status_badge = tk.Label(
            card_header,
            text="NORMAL",
            font=FONT_BODY_BOLD,
            fg=TEXT_PRIMARY,
            bg=BG_BUTTON,
            padx=8,
            pady=2,
        )
        self.status_badge.pack(side=tk.RIGHT)

        # Countdown / Next Event Big Display
        self.event_timer_lbl = tk.Label(
            self.status_card,
            text="--:--:--",
            font=FONT_MONO_LARGE,
            fg=TEXT_PRIMARY,
            bg=BG_SURFACE,
            anchor="w",
        )
        self.event_timer_lbl.pack(fill=tk.X, pady=(4, 2))

        self.event_desc_lbl = tk.Label(
            self.status_card,
            text="Calculating schedule...",
            font=FONT_BODY,
            fg=TEXT_SECONDARY,
            bg=BG_SURFACE,
            anchor="w",
        )
        self.event_desc_lbl.pack(fill=tk.X, pady=(0, 8))

        # Schedule Details Grid inside card
        sched_grid = tk.Frame(self.status_card, bg=BG_SURFACE)
        sched_grid.pack(fill=tk.X, pady=(8, 0))

        tk.Label(sched_grid, text="First Warning:", font=FONT_CAPTION, fg=TEXT_MUTED, bg=BG_SURFACE).grid(row=0, column=0, sticky="w")
        self.lbl_w1 = tk.Label(sched_grid, text=self.config_mgr.config.warning_1_time, font=FONT_CAPTION, fg=TEXT_PRIMARY, bg=BG_SURFACE)
        self.lbl_w1.grid(row=0, column=1, sticky="w", padx=(6, 16))

        tk.Label(sched_grid, text="Curfew Begins:", font=FONT_CAPTION, fg=TEXT_MUTED, bg=BG_SURFACE).grid(row=0, column=2, sticky="w")
        self.lbl_curfew = tk.Label(sched_grid, text=self.config_mgr.config.curfew_time, font=FONT_CAPTION, fg=TEXT_PRIMARY, bg=BG_SURFACE)
        self.lbl_curfew.grid(row=0, column=3, sticky="w", padx=(6, 16))

        tk.Label(sched_grid, text="Shutdown Time:", font=FONT_CAPTION, fg=TEXT_MUTED, bg=BG_SURFACE).grid(row=0, column=4, sticky="w")
        self.lbl_shutdown = tk.Label(sched_grid, text=self.config_mgr.config.shutdown_time, font=FONT_CAPTION, fg=TEXT_PRIMARY, bg=BG_SURFACE)
        self.lbl_shutdown.grid(row=0, column=5, sticky="w", padx=(6, 0))

        # Cancel Pending Shutdown Banner / Button (Dynamic)
        self.cancel_frame = tk.Frame(container, bg=BG_DARK)
        self.cancel_frame.pack(fill=tk.X, pady=(0, 16))

        self.cancel_btn = tk.Button(
            self.cancel_frame,
            text="ABORT PENDING SHUTDOWN (EMERGENCY CANCEL)",
            font=FONT_BODY_BOLD,
            bg=BG_SURFACE,
            fg=TEXT_DANGER,
            activebackground=BG_BUTTON_HOVER,
            activeforeground=TEXT_PRIMARY,
            relief=tk.FLAT,
            highlightbackground=BORDER_COLOR,
            highlightthickness=1,
            pady=10,
            command=self._on_abort_clicked,
        )
        # Hidden by default until SHUTDOWN_PENDING
        self.cancel_btn.pack(fill=tk.X)
        self.cancel_frame.pack_forget()

        # Re-arm Curfew Banner / Button (Visible when emergency or cancelled)
        self.rearm_frame = tk.Frame(container, bg=BG_DARK)
        self.rearm_frame.pack(fill=tk.X, pady=(0, 16))

        self.rearm_btn = tk.Button(
            self.rearm_frame,
            text="RE-ARM CURFEW (RESET TO NORMAL)",
            font=FONT_BODY_BOLD,
            bg=BG_SURFACE,
            fg=TEXT_PRIMARY,
            activebackground=BG_BUTTON_HOVER,
            activeforeground=TEXT_PRIMARY,
            relief=tk.FLAT,
            highlightbackground=BORDER_COLOR,
            highlightthickness=1,
            pady=10,
            command=self._on_rearm_clicked,
        )
        self.rearm_btn.pack(fill=tk.X)
        self.rearm_frame.pack_forget()

        # Action Buttons Grid (2 rows for clean layout)
        btn_grid = tk.Frame(container, bg=BG_DARK)
        btn_grid.pack(fill=tk.X, pady=(0, 16))

        # Row 1: Primary Controls
        row1 = tk.Frame(btn_grid, bg=BG_DARK)
        row1.pack(fill=tk.X, pady=(0, 6))

        settings_btn = tk.Button(
            row1,
            text="SETTINGS",
            font=FONT_BODY_BOLD,
            bg=BG_BUTTON,
            fg=TEXT_PRIMARY,
            activebackground=BG_BUTTON_HOVER,
            activeforeground=TEXT_PRIMARY,
            relief=tk.FLAT,
            padx=14,
            pady=8,
            command=self._open_settings,
        )
        settings_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 4))

        audit_btn = tk.Button(
            row1,
            text="AUDIT LOG",
            font=FONT_BODY_BOLD,
            bg=BG_BUTTON,
            fg=TEXT_PRIMARY,
            activebackground=BG_BUTTON_HOVER,
            activeforeground=TEXT_PRIMARY,
            relief=tk.FLAT,
            padx=14,
            pady=8,
            command=self._open_audit,
        )
        audit_btn.pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=(4, 0))

        # Row 2: Safe Test Buttons
        row2 = tk.Frame(btn_grid, bg=BG_DARK)
        row2.pack(fill=tk.X)

        test_warn_btn = tk.Button(
            row2,
            text="TEST WARNING (POPUP & SOUND)",
            font=FONT_BODY,
            bg=BG_BUTTON,
            fg=TEXT_PRIMARY,
            activebackground=BG_BUTTON_HOVER,
            activeforeground=TEXT_PRIMARY,
            relief=tk.FLAT,
            padx=8,
            pady=8,
            command=self._trigger_test_warning,
        )
        test_warn_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 4))

        test_curfew_btn = tk.Button(
            row2,
            text="TEST CURFEW (CURFEW MODAL)",
            font=FONT_BODY,
            bg=BG_BUTTON,
            fg=TEXT_PRIMARY,
            activebackground=BG_BUTTON_HOVER,
            activeforeground=TEXT_PRIMARY,
            relief=tk.FLAT,
            padx=8,
            pady=8,
            command=self._trigger_test_curfew,
        )
        test_curfew_btn.pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=(4, 0))

        # Bottom Bar: Hide to tray
        bottom_row = tk.Frame(container, bg=BG_DARK)
        bottom_row.pack(fill=tk.X, side=tk.BOTTOM)

        tray_btn = tk.Button(
            bottom_row,
            text="MINIMIZE TO SYSTEM TRAY",
            font=FONT_BODY,
            bg=BG_SURFACE,
            fg=TEXT_SECONDARY,
            activebackground=BG_BUTTON_HOVER,
            activeforeground=TEXT_PRIMARY,
            relief=tk.FLAT,
            pady=6,
            command=self.hide_to_tray,
        )
        tray_btn.pack(fill=tk.X)

    def _open_settings(self) -> None:
        SettingsDialog(
            self,
            self.config_mgr,
            on_save_callback=self._on_settings_saved,
            on_test_warning=self._trigger_test_warning,
        )

    def _on_settings_saved(self, new_config: Config) -> None:
        self.lbl_w1.config(text=new_config.warning_1_time)
        self.lbl_curfew.config(text=new_config.curfew_time)
        self.lbl_shutdown.config(text=new_config.shutdown_time)
        self.mode_badge.config(
            text="[ DRY RUN ]" if new_config.dry_run else "[ LIVE ENFORCEMENT ]",
            fg=TEXT_ACCENT if new_config.dry_run else TEXT_DANGER,
        )
        self.scheduler.shutdown_mgr.dry_run = new_config.dry_run
        if self.notifications:
            self.notifications.update_config(new_config)

    def _open_audit(self) -> None:
        AuditDialog(self, self.audit_logger)

    def _trigger_test_warning(self) -> None:
        """Triggers a sample warning popup, sound alert, and notification for testing."""
        if self.notifications:
            self.notifications.notify(
                title="OFFLINE 11: 30-Minute Warning (Test)",
                message="Sample 30-minute curfew warning. Finish what you are doing and start winding down.",
                sound_type="warning",
            )
        self._show_warning_dialog(
            tag_text="Test Warning",
            title="30 MINUTES REMAINING (TEST)",
            message="This is a test curfew warning.\nAt scheduled warning times, this popup window will appear on top of all applications, accompanied by audio chimes and system notifications.",
            level="warning",
            auto_close_seconds=20,
        )

    def _trigger_test_curfew(self) -> None:
        """Triggers the curfew dialog immediately for safe testing."""
        if not self.config_mgr.config.dry_run:
            confirm = messagebox.askyesno(
                "Test Curfew in Live Mode?",
                "Live enforcement is currently enabled.\n"
                "We recommend enabling Dry-Run mode before testing.\n\n"
                "Do you still wish to test curfew dialog right now?",
                parent=self,
            )
            if not confirm:
                return

        self._show_curfew_dialog()

    def _show_curfew_dialog(self) -> None:
        if self.curfew_dialog is None or not self.curfew_dialog.winfo_exists():
            self.curfew_dialog = CurfewDialog(
                parent=self,
                on_no_emergency=self._handle_no_emergency_curfew,
                on_genuine_emergency=self._handle_emergency_curfew,
            )

    def _handle_no_emergency_curfew(self) -> None:
        self.scheduler.user_accepts_curfew()
        self._show_countdown_widget()

    def _handle_emergency_curfew(self) -> None:
        EmergencyDialog(
            parent=self,
            on_confirm=self._handle_emergency_confirmed,
        )

    def _handle_emergency_confirmed(self, reason: str) -> None:
        if self.curfew_dialog and self.curfew_dialog.winfo_exists():
            self.curfew_dialog.destroy()
            self.curfew_dialog = None
        if self.countdown_widget and self.countdown_widget.winfo_exists():
            self.countdown_widget.destroy()
            self.countdown_widget = None
        self.scheduler.user_declares_emergency(reason)
        messagebox.showinfo(
            "Emergency Exception Granted",
            f"Curfew shutdown cancelled for tonight.\nReason recorded: {reason}",
            parent=self,
        )

    def _show_countdown_widget(self) -> None:
        if self.countdown_widget is None or not self.countdown_widget.winfo_exists():
            self.countdown_widget = CountdownWidget(
                parent=self,
                on_emergency_click=self._handle_emergency_curfew,
                is_dry_run=self.config_mgr.config.dry_run,
            )

    def _on_abort_clicked(self) -> None:
        confirm = messagebox.askyesno(
            "Confirm Shutdown Cancellation",
            "Are you sure you want to manually cancel the pending shutdown?\n\n"
            "This action will be permanently recorded in the audit log.",
            parent=self,
        )
        if confirm:
            self.scheduler.cancel_pending_shutdown(reason="User clicked Abort button in GUI")
            if self.countdown_widget and self.countdown_widget.winfo_exists():
                self.countdown_widget.destroy()
                self.countdown_widget = None
            messagebox.showinfo("Shutdown Aborted", "The pending shutdown has been cancelled.", parent=self)

    def _on_rearm_clicked(self) -> None:
        confirm = messagebox.askyesno(
            "Re-Arm Curfew",
            "Do you want to re-arm tonight's curfew?\n\n"
            "This will clear any emergency exception or cancellation and reset the status to NORMAL.",
            parent=self,
        )
        if confirm:
            self.scheduler.rearm_curfew()
            self._update_display()
            messagebox.showinfo("Curfew Re-Armed", "Curfew has been re-armed for tonight.", parent=self)

    def _show_warning_dialog(
        self,
        tag_text: str,
        title: str,
        message: str,
        level: str = "warning",
        auto_close_seconds: int = 30,
    ) -> None:
        if self.warning_dialog and self.warning_dialog.winfo_exists():
            try:
                self.warning_dialog.destroy()
            except Exception:
                pass
        self.warning_dialog = WarningDialog(
            parent=self,
            tag_text=tag_text,
            title=title,
            message=message,
            level=level,
            auto_close_seconds=auto_close_seconds,
            on_open_dashboard=self.show_from_tray,
        )

    # Scheduler Event Callbacks
    def _on_warning_1_event(self) -> None:
        if self.notifications:
            self.notifications.notify(
                title="OFFLINE 11: 30-Minute Warning",
                message="30 minutes until PC curfew. Finish what you're doing and start winding down.",
                sound_type="warning",
                push_priority="default",
                push_tags="clock",
            )
        curfew_t = self.config_mgr.config.curfew_time
        self._show_warning_dialog(
            tag_text="30-Minute Warning",
            title="30 MINUTES REMAINING",
            message=f"Curfew begins in 30 minutes (at {curfew_t}).\nFinish your current task and start winding down.",
            level="warning",
            auto_close_seconds=30,
        )

    def _on_warning_2_event(self) -> None:
        if self.notifications:
            self.notifications.notify(
                title="OFFLINE 11: 10-Minute Warning",
                message="10 minutes until PC curfew. Save your work and close everything.",
                sound_type="urgent",
                push_priority="high",
                push_tags="warning",
            )
        curfew_t = self.config_mgr.config.curfew_time
        self._show_warning_dialog(
            tag_text="Final Curfew Warning",
            title="10 MINUTES REMAINING",
            message=f"Curfew begins in 10 minutes (at {curfew_t})!\nSave all open work and close applications now.",
            level="urgent",
            auto_close_seconds=30,
        )

    def _on_curfew_event(self) -> None:
        if self.warning_dialog and self.warning_dialog.winfo_exists():
            try:
                self.warning_dialog.destroy()
                self.warning_dialog = None
            except Exception:
                pass
        if self.notifications:
            self.notifications.notify(
                title="OFFLINE 11: PC Curfew Active",
                message="PC TIME IS OVER. Is there a genuine emergency?",
                sound_type="urgent",
                long_duration=True,
                push_priority="urgent",
                push_tags="stop_sign",
            )
        self._show_curfew_dialog()

    def _on_grace_reminder_1(self) -> None:
        if self.notifications:
            self.notifications.notify(
                title="OFFLINE 11: 10 Minutes Until Shutdown",
                message="10 minutes until PC shutdown. Save all open files.",
                sound_type="warning",
                push_priority="high",
                push_tags="warning",
            )
        self._show_warning_dialog(
            tag_text="Grace Period Reminder",
            title="10 MINUTES UNTIL SHUTDOWN",
            message="10 minutes remaining until system power-off.\nPlease save all open files and documents immediately.",
            level="urgent",
            auto_close_seconds=20,
        )

    def _on_grace_reminder_2(self) -> None:
        if self.notifications:
            self.notifications.notify(
                title="OFFLINE 11: 5 Minutes Until Shutdown",
                message="5 minutes until PC shutdown. Close all open applications.",
                sound_type="urgent",
                push_priority="urgent",
                push_tags="hourglass",
            )
        self._show_warning_dialog(
            tag_text="Urgent Shutdown Reminder",
            title="5 MINUTES UNTIL SHUTDOWN",
            message="5 minutes remaining! Close all open applications now to prevent data loss.",
            level="urgent",
            auto_close_seconds=20,
        )

    def _on_final_warning(self) -> None:
        if self.notifications:
            self.notifications.notify(
                title="OFFLINE 11: Final 1-Minute Warning",
                message="PC shutdown will initiate in 1 minute. Prepare for power off.",
                sound_type="urgent",
                push_priority="max",
                push_tags="skull",
            )
        self._show_warning_dialog(
            tag_text="CRITICAL WARNING",
            title="1 MINUTE UNTIL SHUTDOWN",
            message="System shutdown will begin in 60 seconds!\nAll open applications will be closed.",
            level="critical",
            auto_close_seconds=30,
        )

    def _on_shutdown_executed(self, success: bool, msg: str) -> None:
        if self.countdown_widget and self.countdown_widget.winfo_exists():
            self.countdown_widget.destroy()
            self.countdown_widget = None
        if self.warning_dialog and self.warning_dialog.winfo_exists():
            self.warning_dialog.destroy()
            self.warning_dialog = None

        if self.notifications:
            if success:
                self.notifications.notify(
                    title="OFFLINE 11: System Shutdown Initiated",
                    message="Curfew shutdown command accepted by Windows.",
                    sound_type="urgent",
                    push_priority="max",
                    push_tags="skull",
                )
            else:
                self.notifications.notify(
                    title="OFFLINE 11: SHUTDOWN FAILED",
                    message=f"Windows shutdown was blocked or failed: {msg}",
                    sound_type="urgent",
                    push_priority="max",
                    push_tags="warning",
                )

        if not success:
            messagebox.showerror(
                "SHUTDOWN EXECUTION FAILED",
                f"Windows was unable to initiate shutdown:\n{msg}\n\n"
                "Please close your applications and shut down manually.",
                parent=self,
            )

    def _on_state_changed(self, new_status: CurfewStatus) -> None:
        self._update_display()

    def _update_display(self) -> None:
        status = self.state_mgr.get_status()
        self.status_badge.config(text=status.value)

        # Style status badge and action banners
        if status == CurfewStatus.NORMAL:
            self.status_badge.config(bg=BG_BUTTON, fg=TEXT_PRIMARY)
            self.cancel_frame.pack_forget()
            self.rearm_frame.pack_forget()
        elif status == CurfewStatus.SHUTDOWN_PENDING:
            self.status_badge.config(bg=BG_CRITICAL, fg=TEXT_PRIMARY)
            self.cancel_frame.pack(fill=tk.X, pady=(0, 16))
            self.rearm_frame.pack_forget()
        elif status in (CurfewStatus.EMERGENCY_EXCEPTION, CurfewStatus.SHUTDOWN_CANCELLED):
            self.status_badge.config(bg="#1E3A8A", fg=TEXT_PRIMARY)
            self.cancel_frame.pack_forget()
            self.rearm_frame.pack(fill=tk.X, pady=(0, 16))
        elif status == CurfewStatus.SHUTDOWN_COMPLETED:
            self.status_badge.config(bg="#064E3B", fg=TEXT_PRIMARY)
            self.cancel_frame.pack_forget()
            self.rearm_frame.pack_forget()
        elif status == CurfewStatus.SHUTDOWN_FAILED:
            self.status_badge.config(bg=TEXT_DANGER, fg=TEXT_PRIMARY)
            self.cancel_frame.pack_forget()
            self.rearm_frame.pack_forget()
        else:
            self.status_badge.config(bg=BG_BUTTON, fg=TEXT_PRIMARY)
            self.cancel_frame.pack_forget()
            self.rearm_frame.pack_forget()

        # Update Timer / Countdown
        now = self.time_provider.now()
        rem_seconds = self.state_mgr.get_remaining_seconds_until_shutdown(now)
        if rem_seconds is not None and status == CurfewStatus.SHUTDOWN_PENDING:
            mins = int(rem_seconds) // 60
            secs = int(rem_seconds) % 60
            self.event_timer_lbl.config(text=f"{mins:02d}:{secs:02d}", fg=TEXT_DANGER)
            self.event_desc_lbl.config(text="Shutdown countdown active. Save all work!")
            if self.countdown_widget and self.countdown_widget.winfo_exists():
                self.countdown_widget.update_remaining(rem_seconds)
            else:
                self._show_countdown_widget()
        else:
            # Show time to curfew
            w1_time = self.config_mgr.config.get_time_obj("warning_1_time")
            session_date = StateManager.get_session_date_for_time(now, w1_time)

            if self.state_mgr.record and self.state_mgr.record.session_date == session_date and self.state_mgr.record.is_resolved():
                self.event_timer_lbl.config(text="RESOLVED", fg=TEXT_ACCENT)
                self.event_desc_lbl.config(text="Curfew completed for this session. Normal usage allowed.")
            else:
                curfew_time = self.config_mgr.config.get_time_obj("curfew_time")
                curfew_dt = datetime.combine(now.date(), curfew_time, tzinfo=now.tzinfo)
                if now > curfew_dt:
                    curfew_dt += timedelta(days=1)
                diff = (curfew_dt - now).total_seconds()
                hours = int(diff) // 3600
                mins = (int(diff) % 3600) // 60
                secs = int(diff) % 60
                self.event_timer_lbl.config(text=f"{hours:02d}:{mins:02d}:{secs:02d}", fg=TEXT_PRIMARY)
                self.event_desc_lbl.config(text=f"Time until curfew ({self.config_mgr.config.curfew_time})")

    def hide_to_tray(self) -> None:
        """Hides the main window to the system tray."""
        self.withdraw()
        if self.on_hide_to_tray:
            self.on_hide_to_tray()

    def show_from_tray(self) -> None:
        """Restores the main window from the system tray."""
        self.deiconify()
        self.lift()
        self.focus_force()
