"""
Unit tests for OFFLINE 11 Timeline Scheduler.
Verifies the normal warning sequence, ignored curfew dialog, emergency exception,
deduplication, and sleep/wake time jumps using VirtualTimeProvider.
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


class TestScheduler(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_file = Path(self.temp_dir.name) / "test_state.json"
        self.audit_file = Path(self.temp_dir.name) / "test_audit.log"

        self.config = Config(dry_run=True)
        self.state_mgr = StateManager(state_file=self.state_file)
        self.audit_logger = AuditLogger(log_path=self.audit_file)
        self.shutdown_mgr = ShutdownManager(dry_run=True)

        self.local_tz = timezone(timedelta(hours=6))
        # Start at 22:00 (10:00 PM) on 2026-10-14
        self.initial_dt = datetime(2026, 10, 14, 22, 0, tzinfo=self.local_tz)
        self.time_provider = VirtualTimeProvider(initial_dt=self.initial_dt)

        self.scheduler = Scheduler(
            config=self.config,
            state_mgr=self.state_mgr,
            time_provider=self.time_provider,
            audit_logger=self.audit_logger,
            shutdown_mgr=self.shutdown_mgr,
        )

        self.events_received = []
        self.scheduler.on_warning_1 = lambda: self.events_received.append("warning_1")
        self.scheduler.on_warning_2 = lambda: self.events_received.append("warning_2")
        self.scheduler.on_curfew_start = lambda: self.events_received.append("curfew")
        self.scheduler.on_grace_reminder_1 = lambda: self.events_received.append("reminder_1")
        self.scheduler.on_grace_reminder_2 = lambda: self.events_received.append("reminder_2")
        self.scheduler.on_final_warning = lambda: self.events_received.append("final_warning")
        self.scheduler.on_shutdown_executed = lambda s, m: self.events_received.append("shutdown")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_normal_warning_sequence_and_shutdown(self) -> None:
        """Verifies full normal timeline progression from 10:00 PM to 11:15 PM."""
        # 22:00 - Nothing yet
        self.scheduler.tick()
        self.assertEqual(len(self.events_received), 0)

        # Advance to 22:30 (10:30 PM: Warning 1)
        self.time_provider.set_time(datetime(2026, 10, 14, 22, 30, tzinfo=self.local_tz))
        self.scheduler.tick()
        self.assertIn("warning_1", self.events_received)
        self.assertEqual(self.state_mgr.get_status(), CurfewStatus.WARNING_1)

        # Advance to 22:50 (10:50 PM: Warning 2)
        self.time_provider.set_time(datetime(2026, 10, 14, 22, 50, tzinfo=self.local_tz))
        self.scheduler.tick()
        self.assertIn("warning_2", self.events_received)
        self.assertEqual(self.state_mgr.get_status(), CurfewStatus.WARNING_2)

        # Advance to 23:00 (11:00 PM: Curfew begins)
        self.time_provider.set_time(datetime(2026, 10, 14, 23, 0, tzinfo=self.local_tz))
        self.scheduler.tick()
        self.assertIn("curfew", self.events_received)
        self.assertEqual(self.state_mgr.get_status(), CurfewStatus.SHUTDOWN_PENDING)

        # User clicks NO EMERGENCY to accept curfew
        self.scheduler.user_accepts_curfew()
        self.assertEqual(self.state_mgr.get_status(), CurfewStatus.SHUTDOWN_PENDING)

        # Advance to 23:05 (11:05 PM: Grace reminder 1)
        self.time_provider.set_time(datetime(2026, 10, 14, 23, 5, tzinfo=self.local_tz))
        self.scheduler.tick()
        self.assertIn("reminder_1", self.events_received)

        # Advance to 23:10 (11:10 PM: Grace reminder 2)
        self.time_provider.set_time(datetime(2026, 10, 14, 23, 10, tzinfo=self.local_tz))
        self.scheduler.tick()
        self.assertIn("reminder_2", self.events_received)

        # Advance to 23:14 (11:14 PM: Final warning)
        self.time_provider.set_time(datetime(2026, 10, 14, 23, 14, tzinfo=self.local_tz))
        self.scheduler.tick()
        self.assertIn("final_warning", self.events_received)

        # Advance to 23:15 (11:15 PM: Shutdown executed)
        self.time_provider.set_time(datetime(2026, 10, 14, 23, 15, tzinfo=self.local_tz))
        self.scheduler.tick()
        self.assertIn("shutdown", self.events_received)
        self.assertEqual(self.state_mgr.get_status(), CurfewStatus.SHUTDOWN_COMPLETED)
        self.assertTrue(self.state_mgr.record.is_resolved())

    def test_ignored_curfew_dialog_still_shuts_down_at_11_15(self) -> None:
        """
        Requirement: "Do not automatically grant an emergency exception just because the dialog is ignored."
        If the user walks away or ignores the dialog at 11:00 PM, shutdown must still occur at 11:15 PM.
        """
        # Jump directly to 23:00 (11:00 PM: Curfew begins)
        self.time_provider.set_time(datetime(2026, 10, 14, 23, 0, tzinfo=self.local_tz))
        self.scheduler.tick()
        self.assertIn("curfew", self.events_received)
        # Note: user does NOT call user_accepts_curfew() or user_declares_emergency()!
        # State should already be SHUTDOWN_PENDING
        self.assertEqual(self.state_mgr.get_status(), CurfewStatus.SHUTDOWN_PENDING)

        # Fast forward past grace reminders to 23:15 (11:15 PM)
        self.time_provider.set_time(datetime(2026, 10, 14, 23, 15, tzinfo=self.local_tz))
        self.scheduler.tick()
        self.assertIn("shutdown", self.events_received)
        self.assertEqual(self.state_mgr.get_status(), CurfewStatus.SHUTDOWN_COMPLETED)

    def test_emergency_exception_cancels_shutdown(self) -> None:
        """Verifies that declaring an emergency exception cancels the pending shutdown."""
        # Start curfew at 23:00
        self.time_provider.set_time(datetime(2026, 10, 14, 23, 0, tzinfo=self.local_tz))
        self.scheduler.tick()
        self.assertEqual(self.state_mgr.get_status(), CurfewStatus.SHUTDOWN_PENDING)

        # User declares genuine emergency at 23:02
        self.time_provider.set_time(datetime(2026, 10, 14, 23, 2, tzinfo=self.local_tz))
        self.scheduler.user_declares_emergency("Server outage at work requires urgent fix")
        self.assertEqual(self.state_mgr.get_status(), CurfewStatus.EMERGENCY_EXCEPTION)
        self.assertTrue(self.state_mgr.record.is_resolved())

        # Advance to 23:15 (Shutdown time)
        self.time_provider.set_time(datetime(2026, 10, 14, 23, 15, tzinfo=self.local_tz))
        self.scheduler.tick()

        # Shutdown must NOT have been triggered!
        self.assertNotIn("shutdown", self.events_received)
        self.assertEqual(self.state_mgr.get_status(), CurfewStatus.EMERGENCY_EXCEPTION)

    def test_manual_cancellation_of_pending_shutdown(self) -> None:
        """Verifies manual abort button behavior during countdown."""
        self.time_provider.set_time(datetime(2026, 10, 14, 23, 0, tzinfo=self.local_tz))
        self.scheduler.tick()
        self.assertEqual(self.state_mgr.get_status(), CurfewStatus.SHUTDOWN_PENDING)

        # Manual cancellation
        self.scheduler.cancel_pending_shutdown("User clicked abort in GUI")
        self.assertEqual(self.state_mgr.get_status(), CurfewStatus.SHUTDOWN_CANCELLED)

        # Advance to 23:15
        self.time_provider.set_time(datetime(2026, 10, 14, 23, 15, tzinfo=self.local_tz))
        self.scheduler.tick()
        self.assertNotIn("shutdown", self.events_received)

    def test_event_deduplication(self) -> None:
        """Verifies events are not fired multiple times when tick is called frequently."""
        self.time_provider.set_time(datetime(2026, 10, 14, 22, 30, tzinfo=self.local_tz))
        for _ in range(10):
            self.scheduler.tick()
        self.assertEqual(self.events_received.count("warning_1"), 1)

    def test_sleep_and_wake_time_jump(self) -> None:
        """
        Verifies system waking from sleep:
        PC was sleeping from 22:15 to 23:08. On wake, it should handle missed curfew
        and enter SHUTDOWN_PENDING for 23:15.
        """
        # Sleep jumped to 23:08
        self.time_provider.set_time(datetime(2026, 10, 14, 23, 8, tzinfo=self.local_tz))
        self.scheduler.tick()

        # Curfew should have triggered
        self.assertIn("curfew", self.events_received)
        self.assertEqual(self.state_mgr.get_status(), CurfewStatus.SHUTDOWN_PENDING)


if __name__ == "__main__":
    unittest.main()
