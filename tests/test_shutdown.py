"""
Unit tests for OFFLINE 11 Windows Shutdown Manager.
Verifies dry-run safety, command generation, and cancellation.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from offline11.shutdown import ShutdownManager


class TestShutdownManager(unittest.TestCase):
    def test_dry_run_mode_never_executes_system_shutdown(self) -> None:
        """Verifies that dry-run mode simulates shutdown without running subprocess."""
        mgr = ShutdownManager(dry_run=True)
        with patch("subprocess.run") as mock_run:
            success, msg = mgr.execute_shutdown(comment="Test shutdown", grace_seconds=60)
            self.assertTrue(success)
            self.assertIn("[DRY RUN]", msg)
            mock_run.assert_not_called()

    def test_dry_run_cancellation(self) -> None:
        """Verifies dry-run cancellation does not call subprocess."""
        mgr = ShutdownManager(dry_run=True)
        with patch("subprocess.run") as mock_run:
            success, msg = mgr.cancel_shutdown()
            self.assertTrue(success)
            self.assertIn("[DRY RUN]", msg)
            mock_run.assert_not_called()

    def test_live_execution_command_arguments(self) -> None:
        """Verifies correct Windows shutdown.exe argument syntax."""
        mgr = ShutdownManager(dry_run=False)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            success, msg = mgr.execute_shutdown(comment="OFFLINE 11: Curfew shutdown", grace_seconds=60)
            self.assertTrue(success)
            mock_run.assert_called_once_with(
                ["shutdown.exe", "/s", "/t", "60", "/c", "OFFLINE 11: Curfew shutdown"],
                capture_output=True,
                text=True,
                check=False,
            )

    def test_live_cancellation_command_arguments(self) -> None:
        """Verifies correct shutdown /a argument syntax."""
        mgr = ShutdownManager(dry_run=False)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            success, msg = mgr.cancel_shutdown()
            self.assertTrue(success)
            mock_run.assert_called_once_with(
                ["shutdown.exe", "/a"],
                capture_output=True,
                text=True,
                check=False,
            )

    def test_failed_shutdown_reported_clearly(self) -> None:
        """Verifies clear error reporting if Windows shutdown command fails."""
        mgr = ShutdownManager(dry_run=False)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1190, stdout="", stderr="A system shutdown has already been scheduled.")
            success, msg = mgr.execute_shutdown()
            self.assertFalse(success)
            self.assertIn("A system shutdown has already been scheduled", msg)


if __name__ == "__main__":
    unittest.main()
