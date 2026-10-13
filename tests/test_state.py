"""
Unit tests for OFFLINE 11 State Management and Session Resolution.
Specifically verifies the Critical Requirement:
- Curfew is enforced at most once per session date.
- Completed shutdown on Day D never re-shuts down at 12:00 AM on Day D+1.
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from offline11.config import Config
from offline11.state import CurfewStatus, SessionRecord, StateManager


class TestStateManager(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_file = Path(self.temp_dir.name) / "test_state.json"
        self.state_mgr = StateManager(state_file=self.state_file)
        self.config = Config()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_session_date_mapping(self) -> None:
        """Verifies session date mapping relative to 10:30 PM warning time."""
        w1_time = time(22, 30)
        local_tz = timezone(timedelta(hours=6))

        # At 10:30 PM on 2026-10-14 -> session date is 2026-10-14
        dt1 = datetime(2026, 10, 14, 22, 30, tzinfo=local_tz)
        self.assertEqual(StateManager.get_session_date_for_time(dt1, w1_time), "2026-10-14")

        # At 11:15 PM on 2026-10-14 -> session date is 2026-10-14
        dt2 = datetime(2026, 10, 14, 23, 15, tzinfo=local_tz)
        self.assertEqual(StateManager.get_session_date_for_time(dt2, w1_time), "2026-10-14")

        # At 12:00 AM (midnight) on 2026-10-15 -> previous session date is 2026-10-14
        dt3 = datetime(2026, 10, 15, 0, 0, tzinfo=local_tz)
        self.assertEqual(StateManager.get_session_date_for_time(dt3, w1_time), "2026-10-14")

        # At 10:00 AM on 2026-10-15 -> daytime before warning 1 -> session date is 2026-10-14
        dt4 = datetime(2026, 10, 15, 10, 0, tzinfo=local_tz)
        self.assertEqual(StateManager.get_session_date_for_time(dt4, w1_time), "2026-10-14")

        # At 10:30 PM on 2026-10-15 -> new session begins -> session date is 2026-10-15
        dt5 = datetime(2026, 10, 15, 22, 30, tzinfo=local_tz)
        self.assertEqual(StateManager.get_session_date_for_time(dt5, w1_time), "2026-10-15")

    def test_critical_acceptance_requirement_no_reshutdown_after_midnight(self) -> None:
        """
        MANDATORY ACCEPTANCE TEST:
        1. At 11:00 PM, curfew dialog appears.
        2. User selects NO EMERGENCY.
        3. At 11:15 PM, computer shuts down.
        4. User turns it back on at 12:00 AM.
        5. Application starts normally without another curfew dialog or shutdown countdown.
        6. User continues using PC normally throughout the day.
        7. At 10:30 PM the following day, the next curfew session begins as usual.
        """
        local_tz = timezone(timedelta(hours=6))

        # Step 1 & 2: Day 1 at 11:00 PM (2026-10-14 23:00)
        t_curfew = datetime(2026, 10, 14, 23, 0, tzinfo=local_tz)
        t_shutdown_sched = datetime(2026, 10, 14, 23, 15, tzinfo=local_tz)
        self.state_mgr.accept_curfew(scheduled_shutdown_dt=t_shutdown_sched, current_dt=t_curfew)

        self.assertEqual(self.state_mgr.get_status(), CurfewStatus.SHUTDOWN_PENDING)
        self.assertTrue(self.state_mgr.record.curfew_accepted)
        self.assertEqual(self.state_mgr.record.session_date, "2026-10-14")

        # Step 3: At 11:15 PM, computer shuts down.
        t_actual_shutdown = datetime(2026, 10, 14, 23, 15, tzinfo=local_tz)
        self.state_mgr.mark_shutdown_completed(current_dt=t_actual_shutdown)

        self.assertEqual(self.state_mgr.get_status(), CurfewStatus.SHUTDOWN_COMPLETED)
        self.assertTrue(self.state_mgr.record.is_resolved())

        # Step 4 & 5: Turn computer back on at 12:00 AM (2026-10-15 00:00:00).
        # A completely fresh StateManager starts up and reads the state file from disk.
        t_reboot = datetime(2026, 10, 15, 0, 0, tzinfo=local_tz)
        fresh_state_mgr = StateManager(state_file=self.state_file)

        status_at_reboot = fresh_state_mgr.sync_for_time(t_reboot, self.config)
        # Must be resolved (SHUTDOWN_COMPLETED or NORMAL with resolved flag)
        self.assertTrue(fresh_state_mgr.record.is_resolved())
        self.assertEqual(status_at_reboot, CurfewStatus.SHUTDOWN_COMPLETED)
        # Verify no shutdown is scheduled or pending
        rem_seconds = fresh_state_mgr.get_remaining_seconds_until_shutdown(t_reboot)
        self.assertIsNone(rem_seconds)

        # Step 6: Continue using PC normally throughout the day (e.g. 10:00 AM, 3:00 PM, 9:00 PM)
        # The session state remains SHUTDOWN_COMPLETED until the next session begins at 10:30 PM
        t_daytime = datetime(2026, 10, 15, 15, 0, tzinfo=local_tz)
        self.assertEqual(fresh_state_mgr.sync_for_time(t_daytime, self.config), CurfewStatus.SHUTDOWN_COMPLETED)
        self.assertTrue(fresh_state_mgr.record.is_resolved())
        self.assertIsNone(fresh_state_mgr.get_remaining_seconds_until_shutdown(t_daytime))

        # Step 7: At 10:30 PM the following day (2026-10-15 22:30:00), the next curfew session begins!
        t_next_session = datetime(2026, 10, 15, 22, 30, tzinfo=local_tz)
        status_next_day = fresh_state_mgr.sync_for_time(t_next_session, self.config)
        self.assertEqual(status_next_day, CurfewStatus.NORMAL)
        # New session date is initialized
        self.assertEqual(fresh_state_mgr.record.session_date, "2026-10-15")
        self.assertFalse(fresh_state_mgr.record.is_resolved())

    def test_emergency_exception_permanently_resolves_session(self) -> None:
        """Verifies emergency exception marks tonight's session as resolved."""
        local_tz = timezone(timedelta(hours=6))
        t_now = datetime(2026, 10, 14, 23, 2, tzinfo=local_tz)

        self.state_mgr.grant_emergency(reason="Medical emergency: reviewing lab results", current_dt=t_now)
        self.assertEqual(self.state_mgr.get_status(), CurfewStatus.EMERGENCY_EXCEPTION)
        self.assertTrue(self.state_mgr.record.is_resolved())
        self.assertEqual(self.state_mgr.record.emergency_reason, "Medical emergency: reviewing lab results")

        # When app restarts at 23:30, it is still in EMERGENCY_EXCEPTION and does not shut down
        t_later = datetime(2026, 10, 14, 23, 30, tzinfo=local_tz)
        fresh_state = StateManager(state_file=self.state_file)
        status = fresh_state.sync_for_time(t_later, self.config)
        self.assertEqual(status, CurfewStatus.EMERGENCY_EXCEPTION)

    def test_app_restart_during_countdown_preserves_remaining_time(self) -> None:
        """Verifies app restart during countdown does not reset the 15-minute timer."""
        local_tz = timezone(timedelta(hours=6))
        t_start = datetime(2026, 10, 14, 23, 0, tzinfo=local_tz)
        t_shutdown = datetime(2026, 10, 14, 23, 15, tzinfo=local_tz)

        self.state_mgr.accept_curfew(scheduled_shutdown_dt=t_shutdown, current_dt=t_start)

        # 8 minutes later, app restarts at 23:08
        t_restart = datetime(2026, 10, 14, 23, 8, tzinfo=local_tz)
        fresh_state = StateManager(state_file=self.state_file)
        fresh_state.sync_for_time(t_restart, self.config)

        rem = fresh_state.get_remaining_seconds_until_shutdown(t_restart)
        self.assertIsNotNone(rem)
        # Should be exactly 7 minutes (420 seconds), NOT 15 minutes!
        self.assertEqual(rem, 7 * 60)


if __name__ == "__main__":
    unittest.main()
