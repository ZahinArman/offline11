"""
Windows Shutdown Executor module for OFFLINE 11.
Manages documented Windows shutdown commands, safe cancellations,
and dry-run safety modes.
"""

from __future__ import annotations

import logging
import os
import subprocess
from typing import Optional, Tuple


class ShutdownManager:
    """Handles triggering and cancelling system shutdown via Windows shutdown.exe."""

    def __init__(self, dry_run: bool = True) -> None:
        self.dry_run = dry_run
        self.last_error: Optional[str] = None

    def execute_shutdown(self, comment: str = "OFFLINE 11: Curfew shutdown initiated. Save your work.", grace_seconds: int = 60) -> Tuple[bool, str]:
        """
        Initiates a standard Windows shutdown.
        Uses `shutdown.exe /s /t <seconds> /c "<comment>"`.
        Never uses /f (force) without warning.
        In dry-run mode, logs the command without executing it.
        """
        self.last_error = None
        cmd = [
            "shutdown.exe",
            "/s",
            "/t",
            str(max(0, grace_seconds)),
            "/c",
            comment[:500],
        ]

        if self.dry_run:
            msg = f"[DRY RUN] Would execute command: {' '.join(cmd)}"
            logging.info(msg)
            return True, msg

        try:
            logging.info(f"Executing shutdown command: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.returncode == 0:
                return True, "Shutdown command accepted by Windows."
            else:
                err_msg = result.stderr.strip() or f"Exit code {result.returncode}"
                self.last_error = err_msg
                logging.error(f"Shutdown execution failed: {err_msg}")
                return False, err_msg
        except Exception as e:
            err_msg = str(e)
            self.last_error = err_msg
            logging.error(f"Exception during shutdown execution: {err_msg}")
            return False, err_msg

    def cancel_shutdown(self) -> Tuple[bool, str]:
        """
        Aborts any scheduled Windows shutdown via `shutdown.exe /a`.
        In dry-run mode, logs the cancellation without executing it.
        """
        self.last_error = None
        cmd = ["shutdown.exe", "/a"]

        if self.dry_run:
            msg = "[DRY RUN] Would execute: shutdown.exe /a"
            logging.info(msg)
            return True, msg

        try:
            logging.info("Executing shutdown abort command: shutdown.exe /a")
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            # Exit code 0 means successfully aborted.
            # Exit code 1116 (ERROR_SHUTDOWN_NOT_IN_PROGRESS) also means no shutdown is running.
            if result.returncode == 0 or "1116" in result.stderr:
                return True, "Pending shutdown successfully aborted."
            else:
                err_msg = result.stderr.strip() or f"Exit code {result.returncode}"
                self.last_error = err_msg
                logging.warning(f"Shutdown abort message: {err_msg}")
                return False, err_msg
        except Exception as e:
            err_msg = str(e)
            self.last_error = err_msg
            logging.error(f"Exception during shutdown cancellation: {err_msg}")
            return False, err_msg
