"""
Timeline Scheduler module for OFFLINE 11.
Manages daily curfew milestones, deduplication, time jumps, and sleep/wake handling.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from typing import Callable, Dict, List, Optional, Set

from offline11.config import Config
from offline11.logger import AuditLogger
from offline11.shutdown import ShutdownManager
from offline11.state import CurfewStatus, StateManager
from offline11.time_provider import TimeProvider


class Scheduler:
    """Coordinates daily curfew timeline events based on the configured schedule."""

    def __init__(
        self,
        config: Config,
        state_mgr: StateManager,
        time_provider: TimeProvider,
        audit_logger: AuditLogger,
        shutdown_mgr: ShutdownManager,
    ) -> None:
        self.config = config
        self.state_mgr = state_mgr
        self.time_provider = time_provider
        self.audit_logger = audit_logger
        self.shutdown_mgr = shutdown_mgr

        # Event tracking: session_date -> set of event keys
        self._fired_events: Dict[str, Set[str]] = {}

        # UI / Notification callbacks
        self.on_warning_1: Optional[Callable[[], None]] = None
        self.on_warning_2: Optional[Callable[[], None]] = None
        self.on_curfew_start: Optional[Callable[[], None]] = None
        self.on_grace_reminder_1: Optional[Callable[[], None]] = None
        self.on_grace_reminder_2: Optional[Callable[[], None]] = None
        self.on_final_warning: Optional[Callable[[], None]] = None
        self.on_shutdown_executed: Optional[Callable[[bool, str], None]] = None
        self.on_state_change: Optional[Callable[[CurfewStatus], None]] = None

    def get_session_datetime(self, session_date_str: str, time_obj: time) -> datetime:
        """Combines session date and time with local timezone."""
        ref_date = date.fromisoformat(session_date_str)
        local_tz = self.time_provider.now().tzinfo
        return datetime.combine(ref_date, time_obj, tzinfo=local_tz)

    def _has_fired(self, session_date: str, event_key: str) -> bool:
        return event_key in self._fired_events.get(session_date, set())

    def _mark_fired(self, session_date: str, event_key: str) -> None:
        if session_date not in self._fired_events:
            self._fired_events[session_date] = set()
        self._fired_events[session_date].add(event_key)

    def tick(self) -> None:
        """
        Main scheduler evaluation tick.
        Must be called periodically (e.g. every 1 second).
        Evaluates current wall clock against the timeline.
        """
        now = self.time_provider.now()
        w1_time = self.config.get_time_obj("warning_1_time")
        current_session_date = StateManager.get_session_date_for_time(now, w1_time)

        # Synchronize state manager with current time
        status = self.state_mgr.sync_for_time(now, self.config)

        # If current session is already resolved (shutdown completed or emergency exception)
        if self.state_mgr.record and self.state_mgr.record.session_date == current_session_date and self.state_mgr.record.is_resolved():
            # Nothing to fire for a resolved session. User can use PC freely.
            return

        # If it's daytime before warning 1 time, no curfew events should trigger
        if now.time() < w1_time:
            return

        # We are in the active session for current_session_date!
        t_w1 = self.get_session_datetime(current_session_date, self.config.get_time_obj("warning_1_time"))
        t_w2 = self.get_session_datetime(current_session_date, self.config.get_time_obj("warning_2_time"))
        t_curfew = self.get_session_datetime(current_session_date, self.config.get_time_obj("curfew_time"))
        t_r1 = self.get_session_datetime(current_session_date, self.config.get_time_obj("grace_reminder_1_time"))
        t_r2 = self.get_session_datetime(current_session_date, self.config.get_time_obj("grace_reminder_2_time"))
        t_final = self.get_session_datetime(current_session_date, self.config.get_time_obj("final_warning_time"))
        t_shutdown = self.get_session_datetime(current_session_date, self.config.get_time_obj("shutdown_time"))

        # 1. First warning (10:30 PM)
        if now >= t_w1 and not self._has_fired(current_session_date, "warning_1"):
            self._mark_fired(current_session_date, "warning_1")
            self.state_mgr.set_status(CurfewStatus.WARNING_1, now)
            self.audit_logger.log("WARNING_1", "30-minute curfew warning dispatched.", dt=now)
            if self.on_warning_1:
                self.on_warning_1()
            if self.on_state_change:
                self.on_state_change(CurfewStatus.WARNING_1)

        # 2. Final warning (10:50 PM)
        if now >= t_w2 and not self._has_fired(current_session_date, "warning_2"):
            self._mark_fired(current_session_date, "warning_2")
            self.state_mgr.set_status(CurfewStatus.WARNING_2, now)
            self.audit_logger.log("WARNING_2", "10-minute curfew warning dispatched.", dt=now)
            if self.on_warning_2:
                self.on_warning_2()
            if self.on_state_change:
                self.on_state_change(CurfewStatus.WARNING_2)

        # 3. Curfew Begins (11:00 PM)
        if now >= t_curfew and not self._has_fired(current_session_date, "curfew"):
            self._mark_fired(current_session_date, "curfew")
            # Curfew begins: prompt dialog and schedule pending shutdown for 11:15 PM
            # If user ignores dialog, shutdown still proceeds at 11:15 PM
            self.state_mgr.accept_curfew(scheduled_shutdown_dt=t_shutdown, current_dt=now)
            self.audit_logger.log(
                "CURFEW_TRIGGERED",
                "Curfew active: PC TIME IS OVER. Shutdown scheduled for grace period end.",
                {"scheduled_shutdown": t_shutdown.isoformat()},
                dt=now,
            )
            if self.on_curfew_start:
                self.on_curfew_start()
            if self.on_state_change:
                self.on_state_change(CurfewStatus.SHUTDOWN_PENDING)

        # 4. Grace reminder 1 (11:05 PM)
        if now >= t_r1 and not self._has_fired(current_session_date, "reminder_1"):
            self._mark_fired(current_session_date, "reminder_1")
            if self.state_mgr.get_status() == CurfewStatus.SHUTDOWN_PENDING:
                self.audit_logger.log("SHUTDOWN_REMINDER_1", "10 minutes until shutdown.", dt=now)
                if self.on_grace_reminder_1:
                    self.on_grace_reminder_1()

        # 5. Grace reminder 2 (11:10 PM)
        if now >= t_r2 and not self._has_fired(current_session_date, "reminder_2"):
            self._mark_fired(current_session_date, "reminder_2")
            if self.state_mgr.get_status() == CurfewStatus.SHUTDOWN_PENDING:
                self.audit_logger.log("SHUTDOWN_REMINDER_2", "5 minutes until shutdown.", dt=now)
                if self.on_grace_reminder_2:
                    self.on_grace_reminder_2()

        # 6. Final warning (11:14 PM)
        if now >= t_final and not self._has_fired(current_session_date, "final_warning"):
            self._mark_fired(current_session_date, "final_warning")
            if self.state_mgr.get_status() == CurfewStatus.SHUTDOWN_PENDING:
                self.audit_logger.log("FINAL_WARNING", "1 minute until shutdown.", dt=now)
                if self.on_final_warning:
                    self.on_final_warning()

        # 7. Shutdown Execution (11:15 PM)
        if now >= t_shutdown and not self._has_fired(current_session_date, "shutdown"):
            self._mark_fired(current_session_date, "shutdown")
            if self.state_mgr.get_status() == CurfewStatus.SHUTDOWN_PENDING:
                self._trigger_shutdown(now)

    def _trigger_shutdown(self, now: datetime) -> None:
        """Executes the scheduled shutdown."""
        self.state_mgr.mark_shutdown_initiated(now)
        self.audit_logger.log("SHUTDOWN_INITIATED", "Curfew grace period expired. Dispatching shutdown.", dt=now)

        success, msg = self.shutdown_mgr.execute_shutdown(
            comment="OFFLINE 11: Curfew shutdown initiated. Save your work.",
            grace_seconds=self.config.shutdown_grace_seconds,
        )

        if success:
            self.state_mgr.mark_shutdown_completed(now)
            self.audit_logger.log("SHUTDOWN_COMPLETED", f"Shutdown successful: {msg}", dt=now)
            if self.on_shutdown_executed:
                self.on_shutdown_executed(True, msg)
            if self.on_state_change:
                self.on_state_change(CurfewStatus.SHUTDOWN_COMPLETED)
        else:
            self.state_mgr.mark_shutdown_failed(now)
            self.audit_logger.log("SHUTDOWN_FAILED", f"Shutdown failed: {msg}", dt=now)
            if self.on_shutdown_executed:
                self.on_shutdown_executed(False, msg)
            if self.on_state_change:
                self.on_state_change(CurfewStatus.SHUTDOWN_FAILED)

    def user_accepts_curfew(self) -> None:
        """User clicks 'NO EMERGENCY' on the curfew dialog."""
        now = self.time_provider.now()
        w1_time = self.config.get_time_obj("warning_1_time")
        session_date = StateManager.get_session_date_for_time(now, w1_time)
        t_shutdown = self.get_session_datetime(session_date, self.config.get_time_obj("shutdown_time"))

        self.state_mgr.accept_curfew(scheduled_shutdown_dt=t_shutdown, current_dt=now)
        self.audit_logger.log("CURFEW_ACCEPTED", "User confirmed NO EMERGENCY. Countdown running.", dt=now)
        if self.on_state_change:
            self.on_state_change(CurfewStatus.SHUTDOWN_PENDING)

    def user_declares_emergency(self, reason: str) -> None:
        """User confirms an emergency exception."""
        now = self.time_provider.now()
        self.state_mgr.grant_emergency(reason=reason, current_dt=now)
        self.audit_logger.log("EMERGENCY_GRANTED", f"Emergency exception granted: {reason}", {"reason": reason}, dt=now)

        # Cancel any scheduled shutdown
        self.shutdown_mgr.cancel_shutdown()

        if self.on_state_change:
            self.on_state_change(CurfewStatus.EMERGENCY_EXCEPTION)

    def cancel_pending_shutdown(self, reason: str = "User manual abort") -> bool:
        """Manually cancels a pending shutdown before the deadline."""
        now = self.time_provider.now()
        success, msg = self.shutdown_mgr.cancel_shutdown()
        self.state_mgr.cancel_pending_shutdown(current_dt=now)
        self.audit_logger.log("SHUTDOWN_CANCELLED", f"Pending shutdown cancelled: {reason} ({msg})", {"reason": reason}, dt=now)
        if self.on_state_change:
            self.on_state_change(CurfewStatus.SHUTDOWN_CANCELLED)
        return success

    def rearm_curfew(self) -> None:
        """Resets the state back to NORMAL and clears fired events, re-arming curfew for tonight."""
        now = self.time_provider.now()
        w1_time = self.config.get_time_obj("warning_1_time")
        session_date = StateManager.get_session_date_for_time(now, w1_time)
        self.state_mgr.reset_to_normal(now, w1_time)
        if session_date in self._fired_events:
            self._fired_events[session_date].clear()
        self.audit_logger.log("CURFEW_REARMED", "Curfew manually re-armed. State reset to NORMAL.", dt=now)
        if self.on_state_change:
            self.on_state_change(CurfewStatus.NORMAL)
