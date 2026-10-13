"""
Curfew State Machine and Session Persistence.
Strictly ensures curfew is enforced at most once per calendar day session.
A completed shutdown or granted emergency exception permanently resolves the session.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

from offline11.config import Config, get_default_data_dir


class CurfewStatus(str, Enum):
    NORMAL = "NORMAL"                            # Regular PC usage, awaiting scheduled curfew
    WARNING_1 = "WARNING_1"                      # 10:30 PM warning triggered
    WARNING_2 = "WARNING_2"                      # 10:50 PM final warning triggered
    CURFEW_ACTIVE = "CURFEW_ACTIVE"              # 11:00 PM curfew dialog active
    SHUTDOWN_PENDING = "SHUTDOWN_PENDING"        # 11:00-11:15 PM countdown active
    SHUTDOWN_INITIATED = "SHUTDOWN_INITIATED"    # Windows shutdown command issued
    SHUTDOWN_COMPLETED = "SHUTDOWN_COMPLETED"    # Shutdown completed / session permanently resolved
    EMERGENCY_EXCEPTION = "EMERGENCY_EXCEPTION"  # Emergency granted / session permanently resolved
    SHUTDOWN_CANCELLED = "SHUTDOWN_CANCELLED"    # User manually aborted shutdown
    SHUTDOWN_FAILED = "SHUTDOWN_FAILED"          # Windows shutdown command failed


@dataclass
class SessionRecord:
    session_date: str                        # YYYY-MM-DD of the day the curfew began (at 10:30/11:00 PM)
    status: str = CurfewStatus.NORMAL.value
    curfew_accepted: bool = False
    emergency_reason: Optional[str] = None
    emergency_timestamp: Optional[str] = None
    shutdown_scheduled_for: Optional[str] = None
    shutdown_initiated_at: Optional[str] = None
    last_update: Optional[str] = None

    def is_resolved(self) -> bool:
        """A session is permanently resolved once shutdown has completed or emergency exception was granted."""
        return self.status in (
            CurfewStatus.SHUTDOWN_COMPLETED.value,
            CurfewStatus.SHUTDOWN_INITIATED.value,
            CurfewStatus.EMERGENCY_EXCEPTION.value,
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SessionRecord:
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)


class StateManager:
    """
    Manages persistent curfew state and transitions.
    Tracks sessions strictly by reference date so reboots after curfew never trigger duplicate shutdowns.
    """

    def __init__(self, state_file: Optional[Path] = None) -> None:
        if state_file is None:
            self.state_file = get_default_data_dir() / "state.json"
        else:
            self.state_file = Path(state_file)
        self.record: Optional[SessionRecord] = self._load()

    def _load(self) -> Optional[SessionRecord]:
        """Loads session record from disk."""
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return SessionRecord.from_dict(data)
            except Exception:
                return None
        return None

    def _save(self) -> None:
        """Atomically saves the session record to disk."""
        if self.record is None:
            return
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        temp_file = self.state_file.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(self.record.to_dict(), f, indent=4)
        temp_file.replace(self.state_file)

    @staticmethod
    def get_session_date_for_time(current_dt: datetime, warning_1_time: time) -> str:
        """
        Determines the reference session date for a given datetime.
        If current_dt is on or after warning_1_time (e.g. 22:30), the session date is today.
        If current_dt is before warning_1_time (e.g. 00:00 to 22:29), the previous session date was yesterday.
        """
        if current_dt.time() >= warning_1_time:
            return current_dt.date().isoformat()
        else:
            yesterday = current_dt.date() - timedelta(days=1)
            return yesterday.isoformat()

    def sync_for_time(self, current_dt: datetime, config: Config) -> CurfewStatus:
        """
        Synchronizes state for the current time.
        Respects completed shutdowns and emergency exceptions so no duplicate curfew occurs.
        """
        w1_time = config.get_time_obj("warning_1_time")
        active_session_date = self.get_session_date_for_time(current_dt, w1_time)

        # Check if we have an existing record for active_session_date
        if self.record and self.record.session_date == active_session_date:
            # If it's already resolved (completed shutdown or emergency exception)
            if self.record.is_resolved():
                # Stays resolved! PC usage is normal or resolved.
                return CurfewStatus(self.record.status)

            # If it was SHUTDOWN_PENDING, check if the deadline has passed
            if self.record.status == CurfewStatus.SHUTDOWN_PENDING.value:
                if self.record.shutdown_scheduled_for:
                    sched_dt = datetime.fromisoformat(self.record.shutdown_scheduled_for)
                    # If current time is past scheduled shutdown time and it wasn't marked complete,
                    # keep pending or execute shutdown
                    return CurfewStatus.SHUTDOWN_PENDING

            return CurfewStatus(self.record.status)

        # If current time is before warning_1_time, today's session has not started yet.
        # Check if yesterday's session was resolved.
        if current_dt.time() < w1_time:
            # We are in the daytime before tonight's curfew (e.g. 12:00 AM to 10:29 PM).
            # The PC is in normal usage.
            if self.record and self.record.session_date == active_session_date and self.record.is_resolved():
                return CurfewStatus.NORMAL
            return CurfewStatus.NORMAL

        # If we reach here, current_dt.time() >= warning_1_time and no record exists for today.
        # Initialize a new session for active_session_date
        self.record = SessionRecord(
            session_date=active_session_date,
            status=CurfewStatus.NORMAL.value,
            last_update=current_dt.isoformat(),
        )
        self._save()
        return CurfewStatus.NORMAL

    def set_status(self, status: CurfewStatus, current_dt: datetime) -> None:
        """Updates and persists the current status."""
        if self.record is None:
            w1_time = time(22, 30)
            session_date = self.get_session_date_for_time(current_dt, w1_time)
            self.record = SessionRecord(session_date=session_date)

        self.record.status = status.value
        self.record.last_update = current_dt.isoformat()
        self._save()

    def accept_curfew(self, scheduled_shutdown_dt: datetime, current_dt: datetime, warning_1_time: time = time(22, 30)) -> None:
        """Records curfew acceptance and schedules shutdown."""
        if self.record is None:
            self.record = SessionRecord(session_date=self.get_session_date_for_time(current_dt, warning_1_time))

        self.record.status = CurfewStatus.SHUTDOWN_PENDING.value
        self.record.curfew_accepted = True
        self.record.shutdown_scheduled_for = scheduled_shutdown_dt.isoformat()
        self.record.last_update = current_dt.isoformat()
        self._save()

    def grant_emergency(self, reason: str, current_dt: datetime) -> None:
        """
        Grants emergency exception, cancelling shutdown for tonight.
        Permanently resolves tonight's session.
        """
        if self.record is None:
            w1_time = time(22, 30)
            self.record = SessionRecord(session_date=self.get_session_date_for_time(current_dt, w1_time))

        self.record.status = CurfewStatus.EMERGENCY_EXCEPTION.value
        self.record.emergency_reason = reason
        self.record.emergency_timestamp = current_dt.isoformat()
        self.record.last_update = current_dt.isoformat()
        self._save()

    def mark_shutdown_initiated(self, current_dt: datetime) -> None:
        """Records that the shutdown command has been dispatched to Windows."""
        if self.record is None:
            w1_time = time(22, 30)
            self.record = SessionRecord(session_date=self.get_session_date_for_time(current_dt, w1_time))

        self.record.status = CurfewStatus.SHUTDOWN_INITIATED.value
        self.record.shutdown_initiated_at = current_dt.isoformat()
        self.record.last_update = current_dt.isoformat()
        self._save()

    def mark_shutdown_completed(self, current_dt: datetime) -> None:
        """
        Marks shutdown successfully completed.
        This permanently resolves this curfew session so that reboots later that night or at 12:00 AM
        will never trigger another curfew.
        """
        if self.record is None:
            w1_time = time(22, 30)
            self.record = SessionRecord(session_date=self.get_session_date_for_time(current_dt, w1_time))

        self.record.status = CurfewStatus.SHUTDOWN_COMPLETED.value
        self.record.shutdown_initiated_at = current_dt.isoformat()
        self.record.last_update = current_dt.isoformat()
        self._save()

    def cancel_pending_shutdown(self, current_dt: datetime) -> None:
        """Manually aborts pending shutdown."""
        if self.record is not None:
            self.record.status = CurfewStatus.SHUTDOWN_CANCELLED.value
            self.record.shutdown_scheduled_for = None
            self.record.last_update = current_dt.isoformat()
            self._save()

    def mark_shutdown_failed(self, current_dt: datetime) -> None:
        """Records that shutdown execution failed."""
        if self.record is not None:
            self.record.status = CurfewStatus.SHUTDOWN_FAILED.value
            self.record.last_update = current_dt.isoformat()
            self._save()

    def reset_to_normal(self, current_dt: datetime, warning_1_time: time = time(22, 30)) -> None:
        """Resets the current session back to NORMAL, clearing any emergency exception or cancellation."""
        session_date = self.get_session_date_for_time(current_dt, warning_1_time)
        self.record = SessionRecord(
            session_date=session_date,
            status=CurfewStatus.NORMAL.value,
            last_update=current_dt.isoformat(),
        )
        self._save()

    def get_status(self) -> CurfewStatus:
        """Returns the current status enum."""
        if self.record is None:
            return CurfewStatus.NORMAL
        try:
            return CurfewStatus(self.record.status)
        except ValueError:
            return CurfewStatus.NORMAL

    def get_remaining_seconds_until_shutdown(self, current_dt: datetime) -> Optional[float]:
        """Returns seconds remaining until scheduled shutdown if pending, or None."""
        if self.record and self.record.status == CurfewStatus.SHUTDOWN_PENDING.value:
            if self.record.shutdown_scheduled_for:
                try:
                    sched_dt = datetime.fromisoformat(self.record.shutdown_scheduled_for)
                    diff = (sched_dt - current_dt).total_seconds()
                    return max(0.0, diff)
                except Exception:
                    return None
        return None
