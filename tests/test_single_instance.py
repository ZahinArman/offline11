"""
Unit tests for OFFLINE 11 Single-Instance Enforcement.
Verifies duplicate processes are prevented.
"""

from __future__ import annotations

import unittest
from offline11.single_instance import SingleInstance


class TestSingleInstance(unittest.TestCase):
    def test_single_instance_acquisition_and_duplicate_rejection(self) -> None:
        """Verifies that only one instance can acquire the named mutex."""
        mutex_name = "Local\\OFFLINE11_Test_Mutex_123"
        inst1 = SingleInstance(mutex_name=mutex_name)
        acquired1 = inst1.check_or_acquire()
        self.assertTrue(acquired1)
        self.assertFalse(inst1.is_already_running)

        # Second instance should detect existing mutex and fail acquisition
        inst2 = SingleInstance(mutex_name=mutex_name)
        acquired2 = inst2.check_or_acquire()
        self.assertFalse(acquired2)
        self.assertTrue(inst2.is_already_running)

        # Release first instance
        inst1.release()

        # Third instance should now be able to acquire
        inst3 = SingleInstance(mutex_name=mutex_name)
        acquired3 = inst3.check_or_acquire()
        self.assertTrue(acquired3)
        inst3.release()


if __name__ == "__main__":
    unittest.main()
