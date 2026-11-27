"""
Windows installer for OFFLINE 11 (built into a single self-contained OFFLINE11-Setup.exe).

One confirmation, then:
- installs to %LOCALAPPDATA%\\Programs\\OFFLINE 11 (per-user, no admin rights needed)
- creates Start Menu + Desktop shortcuts and an "Uninstall OFFLINE 11" Start Menu entry
- registers in Windows Settings > Apps > Installed apps
- starts OFFLINE 11 automatically at login (can be turned off in Settings)
- launches the app

Re-running the setup upgrades/repairs an existing installation in place.
Your settings and history in %LOCALAPPDATA%\\OFFLINE11 are kept across upgrades.
"""

from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import sys
import time
import tkinter as tk
import winreg
from ctypes import wintypes
from pathlib import Path
from tkinter import messagebox
from typing import Optional

APP_NAME = "OFFLINE 11"
APP_EXE = "OFFLINE11.exe"
APP_DESCRIPTION = "Strict PC Curfew Utility for Windows"
PUBLISHER = "OFFLINE 11"
VERSION = "1.1.0"
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\OFFLINE11"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
SILENT = "--silent" in sys.argv


# --- UI helpers ------------------------------------------------------------------------

def _root() -> tk.Tk:
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    return root


def show_message(title: str, message: str, is_error: bool = False) -> None:
    print(f"[{'ERROR' if is_error else 'INFO'}] {title}: {message}")
    if SILENT:
        return
    try:
        root = _root()
        (messagebox.showerror if is_error else messagebox.showinfo)(title, message, parent=root)
        root.destroy()
    except Exception:
        pass


def ask_yes_no(title: str, message: str) -> bool:
    if SILENT:
        return True
    root = _root()
    try:
        return messagebox.askyesno(title, message, parent=root)
    finally:
        root.destroy()


# --- Paths -----------------------------------------------------------------------------

def _shell_folder(csidl: int) -> Path:
    buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
    ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, buf)
    return Path(buf.value)


def get_paths() -> tuple[Path, Path, Path]:
    local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    install_dir = local_app_data / "Programs" / APP_NAME
    start_menu_dir = _shell_folder(0x0002)  # CSIDL_PROGRAMS
    desktop_dir = _shell_folder(0x0010)     # CSIDL_DESKTOPDIRECTORY
    return install_dir, start_menu_dir, desktop_dir


def find_payload() -> tuple[Optional[Path], Optional[Path], Optional[Path]]:
    """
    Locates the app folder, uninstaller and icon.
    The frozen setup carries them inside itself (payload/); running from source uses dist/.
    """
    if getattr(sys, "frozen", False):
        bases = [Path(getattr(sys, "_MEIPASS", "")) / "payload", Path(sys.executable).resolve().parent]
    else:
        here = Path(__file__).resolve().parent
        bases = [here / "dist", here]

    app_dir = uninstaller = icon = None
    for base in bases:
        if app_dir is None and (base / "OFFLINE11" / APP_EXE).exists():
            app_dir = base / "OFFLINE11"
        if uninstaller is None and (base / "uninstall.exe").exists():
            uninstaller = base / "uninstall.exe"
        for candidate in (base / "icon.ico", base / "assets" / "icon.ico"):
            if icon is None and candidate.exists():
                icon = candidate
    if icon is None and not getattr(sys, "frozen", False):
        candidate = Path(__file__).resolve().parent / "assets" / "icon.ico"
        icon = candidate if candidate.exists() else None
    return app_dir, uninstaller, icon


# --- Steps -----------------------------------------------------------------------------

def stop_running_app() -> None:
    subprocess.run(["taskkill", "/F", "/IM", APP_EXE], capture_output=True, check=False, creationflags=NO_WINDOW)
    time.sleep(1.0)


def _retry(action, attempts: int = 10) -> None:
    for attempt in range(attempts):
        try:
            action()
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(0.5)


def copy_program_files(app_dir: Path, uninstaller: Optional[Path], icon: Optional[Path], install_dir: Path) -> None:
    # Clean install: remove old program files so upgrades never leave stale files behind.
    if install_dir.exists():
        _retry(lambda: shutil.rmtree(install_dir))
    install_dir.mkdir(parents=True, exist_ok=True)
    _retry(lambda: shutil.copytree(app_dir, install_dir, dirs_exist_ok=True))
    if uninstaller is not None:
        _retry(lambda: shutil.copy2(uninstaller, install_dir / "uninstall.exe"))
    if icon is not None:
        _retry(lambda: shutil.copy2(icon, install_dir / "icon.ico"))


def create_shortcut(target: Path, shortcut_path: Path, icon: Path, description: str) -> None:
    """Creates a .lnk shortcut via WScript.Shell (paths passed as data, not spliced into code)."""
    shortcut_path.parent.mkdir(parents=True, exist_ok=True)
    script = (
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:O11_LNK);"
        "$s.TargetPath = $env:O11_TARGET;"
        "$s.WorkingDirectory = $env:O11_WORKDIR;"
        "$s.IconLocation = $env:O11_ICON;"
        "$s.Description = $env:O11_DESC;"
        "$s.Save()"
    )
    env = dict(os.environ)
    env.update(
        O11_LNK=str(shortcut_path),
        O11_TARGET=str(target),
        O11_WORKDIR=str(target.parent),
        O11_ICON=str(icon if icon.exists() else target),
        O11_DESC=description,
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
        env=env, check=True, capture_output=True, creationflags=NO_WINDOW,
    )


def _dir_size_kb(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) // 1024


def register_app(install_dir: Path) -> None:
    """Adds the app to Settings > Apps > Installed apps."""
    uninstall_exe = install_dir / "uninstall.exe"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as key:
        values = {
            "DisplayName": APP_NAME,
            "DisplayVersion": VERSION,
            "Publisher": PUBLISHER,
            "DisplayIcon": str(install_dir / "icon.ico"),
            "InstallLocation": str(install_dir),
            "UninstallString": f'"{uninstall_exe}"',
            "QuietUninstallString": f'"{uninstall_exe}" --silent',
        }
        for name, value in values.items():
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
        winreg.SetValueEx(key, "EstimatedSize", 0, winreg.REG_DWORD, _dir_size_kb(install_dir))
        winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)


def enable_autostart(app_exe: Path) -> None:
    """Start quietly in the tray at login (also fixes any entry pointing at an old location)."""
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, f'"{app_exe}" --minimized')


def launch_app(app_exe: Path) -> None:
    # A PyInstaller setup must not leak its own runtime environment into another PyInstaller app.
    env = {k: v for k, v in os.environ.items() if not k.startswith("_PYI") and k != "_MEIPASS2"}
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    subprocess.Popen([str(app_exe)], cwd=str(app_exe.parent), env=env, close_fds=True)


def install() -> None:
    app_dir, uninstaller, icon = find_payload()
    if app_dir is None:
        show_message(
            "Installation Error",
            "The OFFLINE 11 program files were not found inside this setup.\n"
            "Please download OFFLINE11-Setup.exe again from the Releases page.",
            is_error=True,
        )
        sys.exit(1)

    install_dir, start_menu_dir, desktop_dir = get_paths()
    upgrading = (install_dir / APP_EXE).exists()
    if not ask_yes_no(
        f"{APP_NAME} Setup",
        (f"Update {APP_NAME} to version {VERSION}?" if upgrading else f"Install {APP_NAME} {VERSION}?")
        + f"\n\nLocation: {install_dir}\n\n"
        "It will start automatically when you sign in to Windows (you can turn this off in Settings).",
    ):
        sys.exit(0)

    stop_running_app()
    copy_program_files(app_dir, uninstaller, icon, install_dir)

    app_exe = install_dir / APP_EXE
    icon_dest = install_dir / "icon.ico"
    create_shortcut(app_exe, start_menu_dir / f"{APP_NAME}.lnk", icon_dest, APP_DESCRIPTION)
    create_shortcut(app_exe, desktop_dir / f"{APP_NAME}.lnk", icon_dest, APP_DESCRIPTION)
    if (install_dir / "uninstall.exe").exists():
        create_shortcut(install_dir / "uninstall.exe", start_menu_dir / f"Uninstall {APP_NAME}.lnk", icon_dest, f"Uninstall {APP_NAME}")
    register_app(install_dir)
    enable_autostart(app_exe)
    launch_app(app_exe)

    show_message(
        f"{APP_NAME} Setup",
        f"{APP_NAME} is installed and running (look for its icon near the clock).\n\n"
        "• It starts in safe Dry-Run mode: untick Dry-Run in Settings to enable real shutdowns\n"
        "• Find it in the Start Menu or on your Desktop\n"
        "• Uninstall anytime from Settings > Apps > Installed apps",
    )


if __name__ == "__main__":
    try:
        install()
    except SystemExit:
        raise
    except Exception as e:
        show_message("Installation Error", f"Failed to install {APP_NAME}:\n{e}", is_error=True)
        sys.exit(1)
