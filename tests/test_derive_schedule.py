"""
Tests for Config.derive_schedule: first-run setup shows 3 times, the other 4 follow from them.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from shutcap.config import Config, ScheduleError  # noqa: E402


class TestDeriveSchedule(unittest.TestCase):
    def test_defaults_match_the_standard_schedule(self):
        full = Config.derive_schedule("22:30", "23:00", "23:15")
        self.assertEqual(full, {
            "warning_1_time": "22:30", "warning_2_time": "22:50", "curfew_time": "23:00",
            "grace_reminder_1_time": "23:05", "grace_reminder_2_time": "23:10",
            "final_warning_time": "23:14", "shutdown_time": "23:15",
        })

    def test_result_always_validates(self):
        cases = [("22:30", "23:00", "23:15"), ("23:50", "00:10", "00:30"), ("21:00", "21:02", "21:06"),
                 ("20:00", "20:05", "20:12"), ("23:59", "00:03", "00:07")]
        for w1, c, o in cases:
            with self.subTest(case=(w1, c, o)):
                cfg = Config.from_dict(Config.derive_schedule(w1, c, o))
                cfg.validate()  # raises if out of order

    def test_short_gaps_are_spread_evenly(self):
        full = Config.derive_schedule("21:00", "21:02", "21:06")
        self.assertEqual(full["warning_2_time"], "21:01")
        self.assertEqual([full[k] for k in ("grace_reminder_1_time", "grace_reminder_2_time", "final_warning_time")],
                         ["21:03", "21:04", "21:05"])

    def test_errors_name_the_curfew_field(self):
        for w1, c, o in [("22:30", "22:31", "23:15"), ("22:30", "23:20", "23:15"), ("22:30", "23:13", "23:15")]:
            with self.subTest(case=(w1, c, o)):
                with self.assertRaises(ScheduleError) as ctx:
                    Config.derive_schedule(w1, c, o)
                self.assertEqual(ctx.exception.field, "curfew_time")


if __name__ == "__main__":
    unittest.main()
