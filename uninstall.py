"""
Uninstaller for OFFLINE 11.
Removes everything the app created: program files, shortcuts (incl. taskbar pin),
registry entries, settings/state/logs, and test-mode temp folders.
"""

from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import sys
import tempfile
import time
import tkinter as tk
import winreg
from ctypes import wintypes
from pathlib import Path
from tkinter import messagebox

APP_NAME = "OFFLINE 11"
APP_EXE = "OFFLINE11.exe"
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\OFFLINE11"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000


def _shell_folder(csidl: int) -> Path:
    buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
    ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, buf)
    return Path(buf.value)


def get_targets() -> tuple[Path, Path, list[Path]]:
    local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    install_dir = local_app_data / "Programs" / APP_NAME
    data_dir = local_app_data / "OFFLINE11"
    programs = _shell_folder(0x0002)   # CSIDL_PROGRAMS
    desktop = _shell_folder(0x0010)    # CSIDL_DESKTOPDIRECTORY
    appdata = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    shortcuts = [
        desktop / f"{APP_NAME}.lnk",
        programs / f"{APP_NAME}.lnk",
        programs / f"Uninstall {APP_NAME}.lnk",
        appdata / "Microsoft" / "Internet Explorer" / "Quick Launch" / "User Pinned" / "TaskBar" / f"{APP_NAME}.lnk",
    ]
    return install_dir, data_dir, shortcuts


def stop_running_app() -> None:
    subprocess.run(["taskkill", "/F", "/IM", APP_EXE], capture_output=True, check=False, creationflags=NO_WINDOW)
    time.sleep(1.0)


def remove_registry_entries() -> None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, APP_NAME)
    except OSError:
        pass
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY)
    except OSError:
        pass


def remove_dir(path: Path) -> None:
    for _ in range(10):
        if not path.exists():
            return
        shutil.rmtree(path, ignore_errors=True)
        time.sleep(0.3)


def schedule_delete_after_exit(install_dir: Path) -> None:
    """
    The uninstaller can't delete its own folder while it is running (Settings > Apps runs it
    from the install folder). A tiny detached script waits for this process to exit, removes
    the folder, then deletes itself.
    """
    # Paths are passed as arguments (not written into the script) so non-ASCII user names work.
    # The retry loop also covers PyInstaller's launcher process, which exits just after this one.
    script = Path(tempfile.gettempdir()) / f"offline11_cleanup_{os.getpid()}.cmd"
    # System tools are called by full path (a user's PATH may contain other "find" programs),
    # and "ping" is used as the delay because it works without a console.
    script.write_text(
        "@echo off\r\n"
        'set "SYS=%SystemRoot%\\System32"\r\n'
        "set /a n=0\r\n"
        ":wait\r\n"
        "set /a n+=1\r\n"
        'if %n% GTR 60 goto remove\r\n'
        '"%SYS%\\tasklist.exe" /FI "PID eq %~2" /NH 2>NUL | "%SYS%\\find.exe" " %~2 " >NUL && ("%SYS%\\PING.EXE" -n 2 127.0.0.1 >NUL & goto wait)\r\n'
        ":remove\r\n"
        "for /L %%i in (1,1,30) do (\r\n"
        '  if exist "%~1" (rmdir /s /q "%~1" 2>NUL & "%SYS%\\PING.EXE" -n 2 127.0.0.1 >NUL)\r\n'
        ")\r\n"
        '(goto) 2>NUL & del "%~f0"\r\n',
        encoding="ascii",
    )
    args = [os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "cmd.exe"),
            "/c", str(script), str(install_dir), str(os.getpid())]
    # Break away from any job object so the helper survives this process exiting.
    for flags in (NO_WINDOW | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB, NO_WINDOW | CREATE_NEW_PROCESS_GROUP):
        try:
            subprocess.Popen(args, creationflags=flags, close_fds=True, cwd=tempfile.gettempdir())
            return
        except OSError:
            continue


def perform_uninstall() -> None:
    install_dir, data_dir, shortcuts = get_targets()

    stop_running_app()

    for shortcut in shortcuts:
        try:
            shortcut.unlink(missing_ok=True)
        except OSError:
            pass

    remove_registry_entries()

    # Settings, state, audit and app logs.
    remove_dir(data_dir)
    # Fallback data location used when %LOCALAPPDATA% is not set.
    remove_dir(Path.home() / ".offline11")
    # Throwaway folders created by test mode / --accelerated.
    for leftover in Path(tempfile.gettempdir()).glob("offline11_sim_*"):
        remove_dir(leftover)

    # Program files.
    running_from = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve()
    if install_dir in running_from.parents:
        schedule_delete_after_exit(install_dir)
    else:
        remove_dir(install_dir)


def main() -> None:
    if "--silent" in sys.argv:
        perform_uninstall()
        sys.exit(0)

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        if not messagebox.askyesno(
            f"Uninstall {APP_NAME}",
            f"Remove {APP_NAME} completely from this computer?\n\n"
            "This removes the app, its shortcuts, its startup entry, and all of its settings and logs.",
            icon="warning",
            parent=root,
        ):
            return
        perform_uninstall()
        messagebox.showinfo(f"Uninstall {APP_NAME}", f"{APP_NAME} has been removed from your computer.", parent=root)
    except Exception as e:
        messagebox.showerror(f"Uninstall {APP_NAME}", f"Something went wrong while uninstalling:\n{e}", parent=root)
    finally:
        root.destroy()


if __name__ == "__main__":
    main()
