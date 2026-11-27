"""
Timeline Scheduler module for ShutCap.

Rules (in priority order):
1. Each night's schedule is enforced at most once.
2. Never lock the user out: if the PC is turned on, restarted, or woken from sleep after
   curfew began, tonight is skipped silently. This is detected with a heartbeat saved in the
   state file (boot time is unreliable because of Windows Fast Startup).
3. Alerts are never replayed: fired milestones are persisted, and when several milestones
   are overdue at once (e.g. app started late) only the most recent one is shown.
4. Outside tonight's window nothing happens, and any unfinished session is closed quietly.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Callable, Dict, Optional, Tuple

from shutcap.config import MILESTONES, Config
from shutcap.logger import AuditLogger
from shutcap.shutdown import ShutdownManager
from shutcap.state import CurfewStatus, StateManager
from shutcap.time_provider import TimeProvider

# How late the shutdown may still fire after its scheduled time (covers a slow tick).
SHUTDOWN_TOLERANCE = timedelta(minutes=2)
# If the app was silent longer than this, the PC was off, asleep, or restarted.
RESUME_GAP = timedelta(seconds=60)

MILESTONE_KEYS = [key for key, _, _ in MILESTONES]


class Scheduler:
    """Coordinates the nightly curfew timeline based on the configured schedule."""

    def __init__(
        self,
        config: Config,
        state_mgr: StateManager,
        time_provider: TimeProvider,
        audit_logger: AuditLogger,
        shutdown_mgr: ShutdownManager,
        detect_resume: bool = True,
    ) -> None:
        self.config = config
        self.state_mgr = state_mgr
        self.time_provider = time_provider
        self.audit_logger = audit_logger
        self.shutdown_mgr = shutdown_mgr
        self.detect_resume = detect_resume
        self._last_tick: Optional[datetime] = None

        # UI / Notification callbacks
        self.on_warning_1: Optional[Callable[[], None]] = None
        self.on_warning_2: Optional[Callable[[], None]] = None
        self.on_curfew_start: Optional[Callable[[], None]] = None
        self.on_grace_reminder_1: Optional[Callable[[], None]] = None
        self.on_grace_reminder_2: Optional[Callable[[], None]] = None
        self.on_final_warning: Optional[Callable[[], None]] = None
        self.on_shutdown_executed: Optional[Callable[[bool, str], None]] = None
        self.on_state_change: Optional[Callable[[CurfewStatus], None]] = None

    # --- Schedule geometry ---------------------------------------------------------------

    def session_times(self, session_date: str) -> Dict[str, datetime]:
        """Absolute datetime of every milestone in a session (handles schedules crossing midnight)."""
        start = datetime.combine(
            date.fromisoformat(session_date),
            self.config.get_time_obj("warning_1_time"),
            tzinfo=self.time_provider.now().tzinfo,
        )
        return {key: start + timedelta(minutes=off) for key, _, off in self.config.milestone_offsets()}

    def current_session(self, now: datetime) -> Tuple[str, Dict[str, datetime]]:
        session_date = StateManager.get_session_date_for_time(now, self.config.get_time_obj("warning_1_time"))
        return session_date, self.session_times(session_date)

    def is_in_window(self, now: datetime) -> bool:
        """True between tonight's First Warning and shortly after its Shutdown time."""
        _, times = self.current_session(now)
        return now < times["shutdown"] + SHUTDOWN_TOLERANCE

    def next_curfew_dt(self, now: datetime) -> datetime:
        """The next curfew that will actually apply."""
        session_date, times = self.current_session(now)
        tonight_open = not (self.state_mgr.has_session(session_date) and self.state_mgr.record.is_resolved())
        if now < times["curfew"] and tonight_open:
            return times["curfew"]
        tomorrow = (date.fromisoformat(session_date) + timedelta(days=1)).isoformat()
        return self.session_times(tomorrow)["curfew"]

    def tonight_status(self, now: datetime) -> CurfewStatus:
        """Status to display: tonight's session status inside the window, NORMAL outside it."""
        session_date, _ = self.current_session(now)
        if self.is_in_window(now) and self.state_mgr.has_session(session_date):
            return self.state_mgr.get_status()
        return CurfewStatus.NORMAL

    # --- Main loop -----------------------------------------------------------------------

    def tick(self) -> None:
        """Evaluates the clock against tonight's schedule. Call about once per second."""
        now = self.time_provider.now()
        prev, self._last_tick = self._last_tick, now
        session_date, times = self.current_session(now)
        sm = self.state_mgr

        # Outside tonight's window: close any unfinished session silently and do nothing.
        if now >= times["shutdown"] + SHUTDOWN_TOLERANCE:
            if sm.has_session(session_date) and not sm.record.is_resolved():
                sm.resolve(CurfewStatus.MISSED, now)
                self.audit_logger.log("SESSION_MISSED", "Tonight's window passed without a shutdown (PC was off or asleep).", dt=now)
                self._state_changed(CurfewStatus.MISSED)
            return

        if not sm.has_session(session_date):
            sm.start_session(session_date, now)
        if sm.record.is_resolved():
            return

        # Never lock the user out: if the PC came on (boot or wake) after curfew began, skip tonight.
        if self.detect_resume:
            if prev is None:
                last_seen = sm.last_seen()  # app (re)started: was it alive a moment ago?
                resumed = last_seen is None or now - last_seen > RESUME_GAP
            else:
                resumed = now - prev > RESUME_GAP  # PC slept/hibernated while the app was running
            if resumed and now >= times["curfew"]:
                sm.resolve(CurfewStatus.SKIPPED, now)
                self.audit_logger.log(
                    "SESSION_SKIPPED",
                    "PC was turned on or woke up after curfew began. No enforcement tonight.",
                    dt=now,
                )
                self._state_changed(CurfewStatus.SKIPPED)
                return
        sm.heartbeat(now)

        due = [key for key in MILESTONE_KEYS if now >= times[key]]
        if not due:
            return
        latest = due[-1]
        curfew_started_now = False
        for key in due:
            if sm.has_fired(key):
                continue
            sm.mark_fired(key, now)
            stale = key != latest
            if key in ("warning_1", "warning_2"):
                if not stale:
                    self._fire_warning(key, now)
            elif key == "curfew":
                if "shutdown" not in due:  # never start a countdown that has already expired
                    self._fire_curfew(now, times)
                    curfew_started_now = True
            elif key == "shutdown":
                if sm.get_status() == CurfewStatus.SHUTDOWN_PENDING:
                    self._trigger_shutdown(now)
                elif not sm.record.is_resolved():
                    sm.resolve(CurfewStatus.MISSED, now)
                    self._state_changed(CurfewStatus.MISSED)
            elif not stale and not curfew_started_now and sm.get_status() == CurfewStatus.SHUTDOWN_PENDING:
                self._fire_reminder(key, now, times)

    def _state_changed(self, status: CurfewStatus) -> None:
        if self.on_state_change:
            self.on_state_change(status)

    def _fire_warning(self, key: str, now: datetime) -> None:
        status = CurfewStatus.WARNING_1 if key == "warning_1" else CurfewStatus.WARNING_2
        self.state_mgr.set_status(status, now)
        mins = self.config.minutes_between(key, "curfew")
        self.audit_logger.log(status.value, f"{mins}-minute curfew warning dispatched.", dt=now)
        callback = self.on_warning_1 if key == "warning_1" else self.on_warning_2
        if callback:
            callback()
        self._state_changed(status)

    def _fire_curfew(self, now: datetime, times: Dict[str, datetime]) -> None:
        # Ignoring the dialog does not cancel the shutdown; the countdown starts right away.
        self.state_mgr.accept_curfew(scheduled_shutdown_dt=times["shutdown"], current_dt=now)
        self.audit_logger.log(
            "CURFEW_TRIGGERED",
            "Curfew active: PC TIME IS OVER. Shutdown scheduled for grace period end.",
            {"scheduled_shutdown": times["shutdown"].isoformat()},
            dt=now,
        )
        if self.on_curfew_start:
            self.on_curfew_start()
        self._state_changed(CurfewStatus.SHUTDOWN_PENDING)

    def _fire_reminder(self, key: str, now: datetime, times: Dict[str, datetime]) -> None:
        mins = max(1, round((times["shutdown"] - times[key]).total_seconds() / 60))
        event = {"reminder_1": "SHUTDOWN_REMINDER_1", "reminder_2": "SHUTDOWN_REMINDER_2", "final_warning": "FINAL_WARNING"}[key]
        self.audit_logger.log(event, f"{mins} minute(s) until shutdown.", dt=now)
        callback = {
            "reminder_1": self.on_grace_reminder_1,
            "reminder_2": self.on_grace_reminder_2,
            "final_warning": self.on_final_warning,
        }[key]
        if callback:
            callback()

    def _trigger_shutdown(self, now: datetime) -> None:
        self.state_mgr.mark_shutdown_initiated(now)
        self.audit_logger.log("SHUTDOWN_INITIATED", "Curfew grace period expired. Dispatching shutdown.", dt=now)

        success, msg = self.shutdown_mgr.execute_shutdown(
            comment="ShutCap: Curfew shutdown initiated. Save your work.",
            grace_seconds=self.config.shutdown_grace_seconds,
        )

        if success:
            self.state_mgr.mark_shutdown_completed(now)
            self.audit_logger.log("SHUTDOWN_COMPLETED", f"Shutdown successful: {msg}", dt=now)
            if self.on_shutdown_executed:
                self.on_shutdown_executed(True, msg)
            self._state_changed(CurfewStatus.SHUTDOWN_COMPLETED)
        else:
            self.state_mgr.mark_shutdown_failed(now)
            self.audit_logger.log("SHUTDOWN_FAILED", f"Shutdown failed: {msg}", dt=now)
            if self.on_shutdown_executed:
                self.on_shutdown_executed(False, msg)
            self._state_changed(CurfewStatus.SHUTDOWN_FAILED)

    # --- User actions --------------------------------------------------------------------

    def user_accepts_curfew(self) -> None:
        """User clicked 'NO EMERGENCY'. The countdown is already running; just record it."""
        now = self.time_provider.now()
        self.audit_logger.log("CURFEW_ACCEPTED", "User confirmed NO EMERGENCY. Countdown running.", dt=now)

    def user_declares_emergency(self, reason: str) -> None:
        now = self.time_provider.now()
        self.state_mgr.grant_emergency(reason=reason, current_dt=now)
        self.audit_logger.log("EMERGENCY_GRANTED", f"Emergency exception granted: {reason}", {"reason": reason}, dt=now)
        self.shutdown_mgr.cancel_shutdown()
        self._state_changed(CurfewStatus.EMERGENCY_EXCEPTION)

    def cancel_pending_shutdown(self, reason: str = "User manual abort") -> bool:
        now = self.time_provider.now()
        success, msg = self.shutdown_mgr.cancel_shutdown()
        self.state_mgr.cancel_pending_shutdown(current_dt=now)
        self.audit_logger.log("SHUTDOWN_CANCELLED", f"Pending shutdown cancelled: {reason} ({msg})", {"reason": reason}, dt=now)
        self._state_changed(CurfewStatus.SHUTDOWN_CANCELLED)
        return success

    def rearm_curfew(self) -> None:
        """Resets tonight's session so the schedule applies again."""
        now = self.time_provider.now()
        self.state_mgr.reset_to_normal(now, self.config.get_time_obj("warning_1_time"))
        self.audit_logger.log("CURFEW_REARMED", "Curfew manually re-armed. State reset to NORMAL.", dt=now)
        self._state_changed(CurfewStatus.NORMAL)
