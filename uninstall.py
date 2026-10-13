"""
Standalone Uninstaller for OFFLINE 11.
Completely removes all installed files, shortcuts, registry keys, and local app data.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import logging
import os
import shutil
import subprocess
import sys
import time
import tkinter as tk
from tkinter import messagebox
import winreg
from pathlib import Path

APP_NAME = "OFFLINE 11"


def get_special_paths():
    local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    install_dir = local_app_data / "Programs" / "OFFLINE 11"
    data_dir = local_app_data / "OFFLINE11"

    # Resolve Desktop and Programs directories
    buf_desktop = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
    ctypes.windll.shell32.SHGetFolderPathW(None, 0x0010, None, 0, buf_desktop)
    desk_shortcut = Path(buf_desktop.value) / f"{APP_NAME}.lnk"

    buf_programs = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
    ctypes.windll.shell32.SHGetFolderPathW(None, 0x0002, None, 0, buf_programs)
    start_shortcut = Path(buf_programs.value) / f"{APP_NAME}.lnk"
    uninstall_shortcut = Path(buf_programs.value) / f"Uninstall {APP_NAME}.lnk"

    return install_dir, data_dir, desk_shortcut, start_shortcut, uninstall_shortcut


def kill_running_instances():
    """Terminates any running OFFLINE 11 processes."""
    try:
        subprocess.run(["taskkill", "/F", "/IM", "OFFLINE11.exe"], capture_output=True, check=False)
    except Exception:
        pass


def remove_registry_keys():
    """Removes autostart and uninstall registry entries."""
    # Autostart key
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, APP_NAME)
    except Exception:
        pass

    # Uninstall entry
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall\OFFLINE11")
    except Exception:
        pass


def perform_uninstall(nuke_data: bool = True):
    install_dir, data_dir, desk_shortcut, start_shortcut, uninstall_shortcut = get_special_paths()

    # 1. Kill running instances
    kill_running_instances()
    time.sleep(0.5)

    # 2. Remove shortcuts
    try:
        if desk_shortcut.exists():
            desk_shortcut.unlink(missing_ok=True)
    except Exception:
        pass

    try:
        if start_shortcut.exists():
            start_shortcut.unlink(missing_ok=True)
    except Exception:
        pass

    try:
        if uninstall_shortcut.exists():
            uninstall_shortcut.unlink(missing_ok=True)
    except Exception:
        pass

    # 3. Remove Registry entries
    remove_registry_keys()

    # 4. Remove AppData directory (%LOCALAPPDATA%\OFFLINE11)
    if nuke_data and data_dir.exists():
        try:
            shutil.rmtree(data_dir, ignore_errors=True)
        except Exception:
            pass

    # 5. Remove Program files directory (%LOCALAPPDATA%\Programs\OFFLINE 11)
    # Check if this script/exe is currently running inside install_dir
    current_exe = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve()
    is_inside_install_dir = False
    try:
        current_exe.relative_to(install_dir)
        is_inside_install_dir = True
    except ValueError:
        is_inside_install_dir = False

    if is_inside_install_dir:
        # Schedule self-deletion via detached cmd script
        cmd = f'timeout /t 1 /nobreak > NUL & rmdir /s /q "{install_dir}"'
        subprocess.Popen(f'cmd.exe /c "{cmd}"', shell=True, creationflags=0x00000008)  # DETACHED_PROCESS
    else:
        if install_dir.exists():
            shutil.rmtree(install_dir, ignore_errors=True)


def main():
    # If running with --silent, uninstall immediately without GUI prompts
    if "--silent" in sys.argv:
        perform_uninstall(nuke_data=True)
        sys.exit(0)

    # GUI Prompt
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    confirm = messagebox.askyesno(
        "Uninstall OFFLINE 11",
        "Are you sure you want to completely uninstall OFFLINE 11?\n\n"
        "This will permanently remove:\n"
        "• All program files\n"
        "• Desktop and Start Menu shortcuts\n"
        "• Windows startup registration\n"
        "• All local settings, state files, and logs\n\n"
        "Proceed with uninstallation?",
        icon="warning",
    )

    if not confirm:
        root.destroy()
        sys.exit(0)

    try:
        perform_uninstall(nuke_data=True)
        messagebox.showinfo(
            "Uninstallation Complete",
            "OFFLINE 11 has been completely removed from your computer.",
        )
    except Exception as e:
        messagebox.showerror(
            "Uninstall Error",
            f"An error occurred during uninstallation:\n{e}",
        )
    finally:
        root.destroy()


if __name__ == "__main__":
    main()
