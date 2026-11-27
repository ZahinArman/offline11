"""
Behaviour tests for the "gentle nudge, never lock out" rules:
- turning the PC back on (or waking it) after curfew began never re-enforces
- no stale popups the next morning
- restarts never replay alerts
- schedules may cross midnight and settings changes apply immediately
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from offline11.config import Config
from offline11.logger import AuditLogger
from offline11.scheduler import Scheduler
from offline11.shutdown import ShutdownManager
from offline11.state import CurfewStatus, StateManager
from offline11.time_provider import VirtualTimeProvider

TZ = timezone(timedelta(hours=6))


def dt(day: int, hour: int, minute: int, second: int = 0) -> datetime:
    return datetime(2026, 11, day, hour, minute, second, tzinfo=TZ)


class NightSim:
    """Runs the scheduler like the app does (one tick per simulated second) against one state file."""

    def __init__(self, folder: Path, config: Config | None = None) -> None:
        self.folder = folder
        self.config = config or Config(dry_run=True)
        self.clock = VirtualTimeProvider(initial_dt=dt(27, 20, 0))
        self.events: list[str] = []
        self.start_app()

    def start_app(self) -> None:
        """(Re)starts the app process: fresh scheduler, state loaded from disk."""
        self.sched = Scheduler(
            config=self.config,
            state_mgr=StateManager(self.folder / "state.json"),
            time_provider=self.clock,
            audit_logger=AuditLogger(self.folder / "audit.log"),
            shutdown_mgr=ShutdownManager(dry_run=True),
        )
        for name in ("warning_1", "warning_2", "curfew_start", "grace_reminder_1", "grace_reminder_2", "final_warning"):
            setattr(self.sched, f"on_{name}", lambda n=name: self.events.append(n))
        self.sched.on_shutdown_executed = lambda ok, msg: self.events.append("SHUTDOWN")

    def run_until(self, end: datetime, step: int = 1) -> None:
        while self.clock.now() < end:
            self.sched.tick()
            self.clock.advance(step)
        self.sched.tick()

    @property
    def status(self) -> CurfewStatus:
        return self.sched.state_mgr.get_status()


class TestNoLockout(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.sim = NightSim(Path(self.tmp.name))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_full_night_fires_each_alert_once_then_shuts_down(self) -> None:
        self.sim.run_until(dt(27, 23, 16), step=5)
        self.assertEqual(
            self.sim.events,
            ["warning_1", "warning_2", "curfew_start", "grace_reminder_1", "grace_reminder_2", "final_warning", "SHUTDOWN"],
        )
        self.assertEqual(self.sim.status, CurfewStatus.SHUTDOWN_COMPLETED)

    def test_pc_turned_off_during_grace_no_popup_next_morning(self) -> None:
        """The original annoyance: a stuck 00:00 countdown every morning."""
        self.sim.run_until(dt(27, 23, 8), step=5)
        self.assertEqual(self.sim.status, CurfewStatus.SHUTDOWN_PENDING)
        # User shuts the PC down themselves. Next morning:
        self.sim.clock.set_time(dt(28, 9, 0))
        self.sim.events.clear()
        self.sim.start_app()
        self.sim.run_until(dt(28, 9, 1))
        self.assertEqual(self.sim.events, [])
        self.assertIsNone(self.sim.sched.state_mgr.get_remaining_seconds_until_shutdown(self.sim.clock.now()))
        self.assertEqual(self.sim.sched.tonight_status(self.sim.clock.now()), CurfewStatus.NORMAL)

    def test_pc_turned_back_on_during_grace_is_not_locked_out(self) -> None:
        self.sim.run_until(dt(27, 23, 5), step=5)
        self.sim.clock.set_time(dt(27, 23, 9))  # off at 23:05, back on at 23:09
        self.sim.events.clear()
        self.sim.start_app()
        self.sim.run_until(dt(27, 23, 30), step=5)
        self.assertEqual(self.sim.events, [])
        self.assertEqual(self.sim.status, CurfewStatus.SKIPPED)

    def test_pc_first_turned_on_after_curfew_is_left_alone(self) -> None:
        self.sim.clock.set_time(dt(27, 23, 40))
        self.sim.start_app()
        self.sim.run_until(dt(27, 23, 50))
        self.assertEqual(self.sim.events, [])

    def test_wake_from_sleep_after_curfew_is_left_alone(self) -> None:
        self.sim.run_until(dt(27, 22, 55), step=5)
        self.sim.clock.set_time(dt(27, 23, 10))  # slept 22:55 -> 23:10 with the app running
        self.sim.events.clear()
        self.sim.run_until(dt(27, 23, 30), step=5)
        self.assertEqual(self.sim.events, [])
        self.assertEqual(self.sim.status, CurfewStatus.SKIPPED)

    def test_quick_app_restart_resumes_without_replaying_alerts(self) -> None:
        self.sim.run_until(dt(27, 23, 10, 30), step=5)
        self.sim.events.clear()
        self.sim.start_app()  # app restarted, PC stayed on
        self.sim.run_until(dt(27, 23, 16), step=5)
        self.assertEqual(self.sim.events, ["final_warning", "SHUTDOWN"])

    def test_app_started_late_shows_only_latest_warning(self) -> None:
        self.sim.clock.set_time(dt(27, 22, 52))
        self.sim.start_app()
        self.sim.run_until(dt(27, 22, 53))
        self.assertEqual(self.sim.events, ["warning_2"])

    def test_abort_survives_app_restart(self) -> None:
        self.sim.run_until(dt(27, 23, 5), step=5)
        self.sim.sched.cancel_pending_shutdown()
        self.sim.events.clear()
        self.sim.start_app()
        self.sim.run_until(dt(27, 23, 20), step=5)
        self.assertEqual(self.sim.events, [])
        self.assertEqual(self.sim.status, CurfewStatus.SHUTDOWN_CANCELLED)

    def test_settings_change_applies_without_restart(self) -> None:
        self.sim.run_until(dt(27, 20, 10))
        self.sim.sched.config = Config(
            dry_run=True,
            warning_1_time="20:30", warning_2_time="20:50", curfew_time="21:00",
            grace_reminder_1_time="21:05", grace_reminder_2_time="21:10",
            final_warning_time="21:14", shutdown_time="21:15",
        )
        self.sim.run_until(dt(27, 21, 16), step=5)
        self.assertIn("SHUTDOWN", self.sim.events)


class TestMidnightSchedule(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.config = Config(
            dry_run=True,
            warning_1_time="23:30", warning_2_time="23:50", curfew_time="00:00",
            grace_reminder_1_time="00:05", grace_reminder_2_time="00:10",
            final_warning_time="00:14", shutdown_time="00:15",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_midnight_schedule_is_valid(self) -> None:
        self.config.validate()
        self.assertEqual(self.config.minutes_between("curfew", "shutdown"), 15)

    def test_out_of_order_schedule_is_rejected(self) -> None:
        bad = Config(curfew_time="22:40")  # before Warning 2 (22:50)
        with self.assertRaises(ValueError):
            bad.validate()

    def test_midnight_schedule_runs_once(self) -> None:
        sim = NightSim(Path(self.tmp.name), self.config)
        sim.clock.set_time(dt(27, 23, 0))
        sim.run_until(dt(28, 0, 20), step=5)
        self.assertEqual(sim.events[0], "warning_1")
        self.assertEqual(sim.events[-1], "SHUTDOWN")
        self.assertEqual(sim.events.count("curfew_start"), 1)
        # Back on at 00:30 and all next day: nothing.
        sim.events.clear()
        sim.clock.set_time(dt(28, 0, 30))
        sim.start_app()
        sim.run_until(dt(28, 0, 31))
        sim.clock.set_time(dt(28, 15, 0))
        sim.run_until(dt(28, 15, 1))
        self.assertEqual(sim.events, [])


if __name__ == "__main__":
    unittest.main()
