"""
Unit tests for OFFLINE 11 State Management and Session Resolution.
Verifies that each night's curfew is enforced at most once and survives restarts.
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

from offline11.config import Config
from offline11.logger import AuditLogger
from offline11.scheduler import Scheduler
from offline11.shutdown import ShutdownManager
from offline11.state import CurfewStatus, StateManager
from offline11.time_provider import VirtualTimeProvider

TZ = timezone(timedelta(hours=6))


class TestStateManager(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_file = Path(self.temp_dir.name) / "test_state.json"
        self.state_mgr = StateManager(state_file=self.state_file)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _scheduler(self, now: datetime) -> Scheduler:
        return Scheduler(
            config=Config(dry_run=True),
            state_mgr=StateManager(state_file=self.state_file),
            time_provider=VirtualTimeProvider(initial_dt=now),
            audit_logger=AuditLogger(log_path=Path(self.temp_dir.name) / "audit.log"),
            shutdown_mgr=ShutdownManager(dry_run=True),
        )

    def test_session_date_mapping(self) -> None:
        """Verifies session date mapping relative to the First Warning time."""
        w1_time = time(22, 30)
        cases = [
            (datetime(2026, 10, 14, 22, 30, tzinfo=TZ), "2026-10-14"),
            (datetime(2026, 10, 14, 23, 15, tzinfo=TZ), "2026-10-14"),
            (datetime(2026, 10, 15, 0, 0, tzinfo=TZ), "2026-10-14"),
            (datetime(2026, 10, 15, 10, 0, tzinfo=TZ), "2026-10-14"),
            (datetime(2026, 10, 15, 22, 30, tzinfo=TZ), "2026-10-15"),
        ]
        for dt, expected in cases:
            self.assertEqual(StateManager.get_session_date_for_time(dt, w1_time), expected)

    def test_critical_acceptance_requirement_no_reshutdown_after_midnight(self) -> None:
        """
        MANDATORY ACCEPTANCE TEST:
        Curfew -> shutdown -> PC turned back on at 12:00 AM -> nothing happens all day ->
        next night's schedule starts as usual.
        """
        t_shutdown = datetime(2026, 10, 14, 23, 15, tzinfo=TZ)
        self.state_mgr.start_session("2026-10-14", datetime(2026, 10, 14, 22, 30, tzinfo=TZ))
        self.state_mgr.accept_curfew(t_shutdown, datetime(2026, 10, 14, 23, 0, tzinfo=TZ))
        self.state_mgr.mark_shutdown_completed(t_shutdown)
        self.assertTrue(self.state_mgr.record.is_resolved())

        # Reboot at midnight and use the PC all day: no countdown, nothing pending.
        for dt in (datetime(2026, 10, 15, 0, 0, tzinfo=TZ), datetime(2026, 10, 15, 15, 0, tzinfo=TZ)):
            sched = self._scheduler(dt)
            sched.tick()
            self.assertIsNone(sched.state_mgr.get_remaining_seconds_until_shutdown(dt))
            self.assertEqual(sched.tonight_status(dt), CurfewStatus.NORMAL)

        # Next night: a fresh session begins.
        t_next = datetime(2026, 10, 15, 22, 30, tzinfo=TZ)
        sched = self._scheduler(t_next)
        sched.tick()
        self.assertEqual(sched.state_mgr.record.session_date, "2026-10-15")
        self.assertEqual(sched.state_mgr.get_status(), CurfewStatus.WARNING_1)

    def test_emergency_exception_permanently_resolves_session(self) -> None:
        t_now = datetime(2026, 10, 14, 23, 2, tzinfo=TZ)
        self.state_mgr.grant_emergency(reason="Medical emergency", current_dt=t_now)
        self.assertEqual(self.state_mgr.get_status(), CurfewStatus.EMERGENCY_EXCEPTION)
        self.assertTrue(self.state_mgr.record.is_resolved())

        sched = self._scheduler(datetime(2026, 10, 14, 23, 30, tzinfo=TZ))
        sched.tick()
        self.assertEqual(sched.state_mgr.get_status(), CurfewStatus.EMERGENCY_EXCEPTION)

    def test_app_restart_during_countdown_preserves_remaining_time(self) -> None:
        """A quick app restart (PC still on) resumes the countdown instead of resetting it."""
        t_start = datetime(2026, 10, 14, 23, 0, tzinfo=TZ)
        self.state_mgr.start_session("2026-10-14", t_start)
        self.state_mgr.accept_curfew(datetime(2026, 10, 14, 23, 15, tzinfo=TZ), t_start)
        self.state_mgr.heartbeat(datetime(2026, 10, 14, 23, 7, 50, tzinfo=TZ))

        t_restart = datetime(2026, 10, 14, 23, 8, tzinfo=TZ)
        sched = self._scheduler(t_restart)
        sched.tick()
        self.assertEqual(sched.state_mgr.get_status(), CurfewStatus.SHUTDOWN_PENDING)
        self.assertEqual(sched.state_mgr.get_remaining_seconds_until_shutdown(t_restart), 7 * 60)

    def test_old_state_file_without_new_fields_loads(self) -> None:
        self.state_file.write_text('{"session_date": "2026-10-14", "status": "SHUTDOWN_PENDING"}', encoding="utf-8")
        mgr = StateManager(state_file=self.state_file)
        self.assertEqual(mgr.record.fired_events, [])
        self.assertIsNone(mgr.last_seen())


if __name__ == "__main__":
    unittest.main()
