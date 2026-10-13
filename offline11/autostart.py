"""
Windows Auto-Startup Manager for OFFLINE 11.
Manages HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run registry entry.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Optional

if sys.platform == "win32":
    import winreg
else:
    winreg = None

REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_REG_NAME = "OFFLINE 11"


def get_default_command() -> str:
    """Returns the command to start OFFLINE 11 at user login."""
    # Check if frozen executable (PyInstaller)
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'

    # Otherwise Python script invocation
    # Use pythonw.exe if available to avoid opening a terminal window
    python_exe = sys.executable
    if "python.exe" in python_exe.lower():
        pythonw_candidate = Path(python_exe).with_name("pythonw.exe")
        if pythonw_candidate.exists():
            python_exe = str(pythonw_candidate)

    main_script = Path(__file__).parent / "main.py"
    return f'"{python_exe}" "{main_script.resolve()}"'


def is_autostart_enabled() -> bool:
    """Checks whether the application is registered in Windows startup registry."""
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_READ) as key:
            val, _ = winreg.QueryValueEx(key, APP_REG_NAME)
            return bool(val)
    except FileNotFoundError:
        return False
    except Exception as e:
        logging.error(f"Error checking autostart registry: {e}")
        return False


def enable_autostart(command: Optional[str] = None) -> bool:
    """Adds OFFLINE 11 to Windows startup registry."""
    if winreg is None:
        logging.warning("winreg not available on this platform.")
        return False
    if command is None:
        command = get_default_command()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, APP_REG_NAME, 0, winreg.REG_SZ, command)
        logging.info(f"Autostart enabled in registry: {command}")
        return True
    except Exception as e:
        logging.error(f"Failed to enable autostart: {e}")
        return False


def disable_autostart() -> bool:
    """Removes OFFLINE 11 from Windows startup registry."""
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, APP_REG_NAME)
        logging.info("Autostart disabled in registry.")
        return True
    except FileNotFoundError:
        return True  # Already not registered
    except Exception as e:
        logging.error(f"Failed to disable autostart: {e}")
        return False
