"""
Single-instance enforcement for ShutCap.
Uses Windows Win32 Mutex to reliably prevent duplicate processes.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from shutcap.config import get_default_data_dir

# Win32 Error Codes
ERROR_ALREADY_EXISTS = 183


class SingleInstance:
    """
    Guarantees only one instance of ShutCap runs at a time.
    Uses a named Win32 Mutex on Windows, falling back to a PID lock file.
    """

    def __init__(self, mutex_name: str = "Local\\ShutCap_App_SingleInstance_Mutex") -> None:
        self.mutex_name = mutex_name
        self.mutex_handle = None
        self.lock_file: Path = get_default_data_dir() / "app.pid"
        self._is_already_running: bool = False

    def check_or_acquire(self) -> bool:
        """
        Attempts to acquire the single-instance lock.
        Returns True if acquired (this is the only running instance).
        Returns False if another instance already holds the lock.
        """
        if sys.platform == "win32":
            kernel32 = ctypes.windll.kernel32
            # CreateMutexW(lpMutexAttributes, bInitialOwner, lpName)
            kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
            kernel32.CreateMutexW.restype = wintypes.HANDLE

            self.mutex_handle = kernel32.CreateMutexW(None, True, self.mutex_name)
            last_error = kernel32.GetLastError()

            if last_error == ERROR_ALREADY_EXISTS:
                self._is_already_running = True
                logging.warning("Another instance of ShutCap is already running (Mutex exists).")
                kernel32.CloseHandle(self.mutex_handle)
                self.mutex_handle = None
                return False

        # Write current PID to lock file
        try:
            self.lock_file.write_text(str(os.getpid()), encoding="utf-8")
        except Exception as e:
            logging.debug(f"Unable to write PID lockfile: {e}")

        self._is_already_running = False
        return True

    def release(self) -> None:
        """Releases the mutex and cleans up PID file."""
        if sys.platform == "win32" and self.mutex_handle:
            try:
                ctypes.windll.kernel32.CloseHandle(self.mutex_handle)
                self.mutex_handle = None
            except Exception:
                pass

        try:
            if self.lock_file.exists():
                self.lock_file.unlink(missing_ok=True)
        except Exception:
            pass

    @property
    def is_already_running(self) -> bool:
        return self._is_already_running


# --- "Show the window" signal between instances -------------------------------------------
# A second launch does not show a pop-up. It signals the running copy, which opens its window.
SHOW_EVENT_NAME = "Local\\ShutCap_App_ShowWindow"


def signal_running_instance() -> bool:
    """Asks the running copy to show its window. Returns True if the signal was sent."""
    if sys.platform != "win32":
        return False
    kernel32 = ctypes.windll.kernel32
    kernel32.OpenEventW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.OpenEventW.restype = wintypes.HANDLE
    handle = kernel32.OpenEventW(0x0002, False, SHOW_EVENT_NAME)  # EVENT_MODIFY_STATE
    if not handle:
        return False
    try:
        return bool(kernel32.SetEvent(handle))
    finally:
        kernel32.CloseHandle(handle)


def listen_for_show(callback) -> None:
    """Runs callback (on a daemon thread) each time another launch asks to show the window."""
    if sys.platform != "win32":
        return
    import threading
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateEventW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CreateEventW.restype = wintypes.HANDLE
    handle = kernel32.CreateEventW(None, False, False, SHOW_EVENT_NAME)  # auto-reset
    if not handle:
        return

    def _wait() -> None:
        while True:
            if kernel32.WaitForSingleObject(handle, 0xFFFFFFFF) == 0:
                try:
                    callback()
                except Exception as e:
                    logging.debug(f"Show-window callback failed: {e}")

    threading.Thread(target=_wait, daemon=True, name="shutcap-show-listener").start()
