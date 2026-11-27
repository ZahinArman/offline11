"""
Curfew State Machine and Session Persistence.

A "session" is one night's curfew cycle, keyed by the date on which its First Warning fires.
Each session is enforced at most once. Once resolved (shutdown done, emergency, cancelled,
skipped, or missed) nothing else happens until the next night's First Warning.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, time, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from offline11.config import get_default_data_dir


class CurfewStatus(str, Enum):
    NORMAL = "NORMAL"                            # Regular PC usage, awaiting tonight's schedule
    WARNING_1 = "WARNING_1"                      # First warning shown
    WARNING_2 = "WARNING_2"                      # Final warning before curfew shown
    CURFEW_ACTIVE = "CURFEW_ACTIVE"              # (legacy, kept for old state files)
    SHUTDOWN_PENDING = "SHUTDOWN_PENDING"        # Curfew began, grace countdown running
    SHUTDOWN_INITIATED = "SHUTDOWN_INITIATED"    # Windows shutdown command issued
    SHUTDOWN_COMPLETED = "SHUTDOWN_COMPLETED"    # Shutdown issued / tonight is done
    EMERGENCY_EXCEPTION = "EMERGENCY_EXCEPTION"  # Emergency declared / tonight is done
    SHUTDOWN_CANCELLED = "SHUTDOWN_CANCELLED"    # User aborted the countdown / tonight is done
    SHUTDOWN_FAILED = "SHUTDOWN_FAILED"          # Windows refused the shutdown command
    SKIPPED = "SKIPPED"                          # PC was turned on / woke after curfew began: never lock the user out
    MISSED = "MISSED"                            # Tonight's window passed without a shutdown (PC was off/asleep)


RESOLVED_STATUSES = {
    CurfewStatus.SHUTDOWN_COMPLETED.value,
    CurfewStatus.SHUTDOWN_INITIATED.value,
    CurfewStatus.EMERGENCY_EXCEPTION.value,
    CurfewStatus.SHUTDOWN_CANCELLED.value,
    CurfewStatus.SHUTDOWN_FAILED.value,
    CurfewStatus.SKIPPED.value,
    CurfewStatus.MISSED.value,
}


@dataclass
class SessionRecord:
    session_date: str                        # YYYY-MM-DD of the night's First Warning
    status: str = CurfewStatus.NORMAL.value
    curfew_accepted: bool = False
    emergency_reason: Optional[str] = None
    emergency_timestamp: Optional[str] = None
    shutdown_scheduled_for: Optional[str] = None
    shutdown_initiated_at: Optional[str] = None
    last_update: Optional[str] = None
    fired_events: List[str] = field(default_factory=list)  # persisted so restarts never replay alerts
    last_seen: Optional[str] = None          # heartbeat: proves the app (and PC) stayed on

    def is_resolved(self) -> bool:
        """A resolved session never triggers anything again."""
        return self.status in RESOLVED_STATUSES

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SessionRecord:
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)


class StateManager:
    """Persists the current night's session record."""

    def __init__(self, state_file: Optional[Path] = None) -> None:
        if state_file is None:
            self.state_file = get_default_data_dir() / "state.json"
        else:
            self.state_file = Path(state_file)
        self.record: Optional[SessionRecord] = self._load()

    def _load(self) -> Optional[SessionRecord]:
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    return SessionRecord.from_dict(json.load(f))
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
        The session a moment belongs to is the one whose First Warning fired most recently.
        At or after warning_1_time -> today; before it -> yesterday.
        """
        if current_dt.time() >= warning_1_time:
            return current_dt.date().isoformat()
        return (current_dt.date() - timedelta(days=1)).isoformat()

    # --- Session lifecycle -------------------------------------------------------------

    def has_session(self, session_date: str) -> bool:
        return self.record is not None and self.record.session_date == session_date

    def start_session(self, session_date: str, current_dt: datetime) -> None:
        """Creates a fresh record for a new night."""
        self.record = SessionRecord(
            session_date=session_date,
            status=CurfewStatus.NORMAL.value,
            last_update=current_dt.isoformat(),
        )
        self._save()

    def _ensure_record(self, current_dt: datetime, warning_1_time: time = time(22, 30)) -> SessionRecord:
        if self.record is None:
            self.record = SessionRecord(session_date=self.get_session_date_for_time(current_dt, warning_1_time))
        return self.record

    def heartbeat(self, current_dt: datetime, every_seconds: float = 10.0) -> None:
        """Records that the app is alive (throttled), so a later start can tell the PC was off."""
        if self.record is None:
            return
        last = self.last_seen()
        if last is None or (current_dt - last).total_seconds() >= every_seconds or current_dt < last:
            self.record.last_seen = current_dt.isoformat()
            self._save()

    def last_seen(self) -> Optional[datetime]:
        if self.record is None or not self.record.last_seen:
            return None
        try:
            return datetime.fromisoformat(self.record.last_seen)
        except ValueError:
            return None

    def has_fired(self, event_key: str) -> bool:
        return self.record is not None and event_key in self.record.fired_events

    def mark_fired(self, event_key: str, current_dt: datetime) -> None:
        rec = self._ensure_record(current_dt)
        if event_key not in rec.fired_events:
            rec.fired_events.append(event_key)
            rec.last_update = current_dt.isoformat()
            self._save()

    def set_status(self, status: CurfewStatus, current_dt: datetime) -> None:
        rec = self._ensure_record(current_dt)
        rec.status = status.value
        rec.last_update = current_dt.isoformat()
        self._save()

    def resolve(self, status: CurfewStatus, current_dt: datetime) -> None:
        """Closes tonight's session with the given outcome."""
        rec = self._ensure_record(current_dt)
        rec.status = status.value
        rec.shutdown_scheduled_for = None
        rec.last_update = current_dt.isoformat()
        self._save()

    def accept_curfew(self, scheduled_shutdown_dt: datetime, current_dt: datetime, warning_1_time: time = time(22, 30)) -> None:
        """Curfew began: starts the grace countdown to scheduled_shutdown_dt."""
        rec = self._ensure_record(current_dt, warning_1_time)
        rec.status = CurfewStatus.SHUTDOWN_PENDING.value
        rec.curfew_accepted = True
        rec.shutdown_scheduled_for = scheduled_shutdown_dt.isoformat()
        rec.last_update = current_dt.isoformat()
        self._save()

    def grant_emergency(self, reason: str, current_dt: datetime) -> None:
        rec = self._ensure_record(current_dt)
        rec.status = CurfewStatus.EMERGENCY_EXCEPTION.value
        rec.emergency_reason = reason
        rec.emergency_timestamp = current_dt.isoformat()
        rec.shutdown_scheduled_for = None
        rec.last_update = current_dt.isoformat()
        self._save()

    def mark_shutdown_initiated(self, current_dt: datetime) -> None:
        rec = self._ensure_record(current_dt)
        rec.status = CurfewStatus.SHUTDOWN_INITIATED.value
        rec.shutdown_initiated_at = current_dt.isoformat()
        rec.last_update = current_dt.isoformat()
        self._save()

    def mark_shutdown_completed(self, current_dt: datetime) -> None:
        """Tonight is done: turning the PC back on later never triggers another curfew."""
        rec = self._ensure_record(current_dt)
        rec.status = CurfewStatus.SHUTDOWN_COMPLETED.value
        rec.shutdown_initiated_at = current_dt.isoformat()
        rec.shutdown_scheduled_for = None
        rec.last_update = current_dt.isoformat()
        self._save()

    def cancel_pending_shutdown(self, current_dt: datetime) -> None:
        if self.record is not None:
            self.resolve(CurfewStatus.SHUTDOWN_CANCELLED, current_dt)

    def mark_shutdown_failed(self, current_dt: datetime) -> None:
        if self.record is not None:
            self.resolve(CurfewStatus.SHUTDOWN_FAILED, current_dt)

    def reset_to_normal(self, current_dt: datetime, warning_1_time: time = time(22, 30)) -> None:
        """Re-arms tonight's session (clears emergency/cancellation and fired events)."""
        self.start_session(self.get_session_date_for_time(current_dt, warning_1_time), current_dt)

    # --- Queries -----------------------------------------------------------------------

    def get_status(self) -> CurfewStatus:
        if self.record is None:
            return CurfewStatus.NORMAL
        try:
            return CurfewStatus(self.record.status)
        except ValueError:
            return CurfewStatus.NORMAL

    def get_remaining_seconds_until_shutdown(self, current_dt: datetime) -> Optional[float]:
        """Seconds remaining until the scheduled shutdown if one is pending, else None."""
        if self.record and self.record.status == CurfewStatus.SHUTDOWN_PENDING.value and self.record.shutdown_scheduled_for:
            try:
                sched_dt = datetime.fromisoformat(self.record.shutdown_scheduled_for)
                return max(0.0, (sched_dt - current_dt).total_seconds())
            except Exception:
                return None
        return None
