"""
Uninstaller for OFFLINE 11.
Removes shortcuts, program files, and registry entries.
"""

from __future__ import annotations

import os
import shutil
import sys
import winreg
from pathlib import Path


def uninstall():
    import ctypes
    from ctypes import wintypes

    local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    install_dir = local_app_data / "Programs" / "OFFLINE 11"

    buf_desktop = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
    ctypes.windll.shell32.SHGetFolderPathW(None, 0x0010, None, 0, buf_desktop)
    desk_shortcut = Path(buf_desktop.value) / "OFFLINE 11.lnk"

    buf_programs = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
    ctypes.windll.shell32.SHGetFolderPathW(None, 0x0002, None, 0, buf_programs)
    start_shortcut = Path(buf_programs.value) / "OFFLINE 11.lnk"

    # Remove shortcuts
    if start_shortcut.exists():
        start_shortcut.unlink(missing_ok=True)
    if desk_shortcut.exists():
        desk_shortcut.unlink(missing_ok=True)

    # Remove registry entries
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall\OFFLINE11")
    except Exception:
        pass

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, "OFFLINE 11")
    except Exception:
        pass

    # Remove program directory
    if install_dir.exists():
        shutil.rmtree(install_dir, ignore_errors=True)

    print("OFFLINE 11 has been successfully uninstalled.")


if __name__ == "__main__":
    uninstall()
