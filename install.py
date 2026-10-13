"""
Windows Application Installer for OFFLINE 11.
Integrates OFFLINE 11 as a first-class Windows app:
- Installs to %LOCALAPPDATA%\\Programs\\OFFLINE 11 (standard user app location like VS Code/Chrome)
- Creates Start Menu shortcut (makes it searchable via Windows Start Menu)
- Creates Desktop shortcut
- Bundles 1-click uninstaller (uninstall.exe) and registers in Windows 'Installed Apps' / Settings
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
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
APP_DESCRIPTION = "Strict PC Curfew Utility for Windows"
PUBLISHER = "OFFLINE 11"
VERSION = "1.0.0"


def show_ui_message(title: str, message: str, is_error: bool = False):
    """Displays a graphical message box and prints to stdout."""
    print(f"[{'ERROR' if is_error else 'INFO'}] {title}: {message}")
    if "--silent" in sys.argv:
        return
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        if is_error:
            messagebox.showerror(title, message)
        else:
            messagebox.showinfo(title, message)
        root.destroy()
    except Exception:
        pass


def get_paths():
    local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    install_dir = local_app_data / "Programs" / "OFFLINE 11"

    # CSIDL_DESKTOPDIRECTORY = 0x0010, CSIDL_PROGRAMS = 0x0002
    buf_desktop = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
    ctypes.windll.shell32.SHGetFolderPathW(None, 0x0010, None, 0, buf_desktop)
    desktop_dir = Path(buf_desktop.value)

    buf_programs = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
    ctypes.windll.shell32.SHGetFolderPathW(None, 0x0002, None, 0, buf_programs)
    start_menu_dir = Path(buf_programs.value)

    return install_dir, start_menu_dir, desktop_dir


def kill_running_instances():
    """Terminates any running OFFLINE 11 processes before overwriting files."""
    try:
        subprocess.run(["taskkill", "/F", "/IM", "OFFLINE11.exe"], capture_output=True, check=False)
    except Exception:
        pass
    time.sleep(1.0)


def create_shortcut(target_exe: Path, shortcut_path: Path, icon_path: Path, description: str):
    """Creates a Windows shortcut (.lnk) using PowerShell and WScript.Shell."""
    ps_cmd = f"""
    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut('{shortcut_path}')
    $Shortcut.TargetPath = '{target_exe}'
    $Shortcut.WorkingDirectory = '{target_exe.parent}'
    $Shortcut.IconLocation = '{icon_path}'
    $Shortcut.Description = '{description}'
    $Shortcut.Save()
    """
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd], check=True)


def register_uninstall(install_dir: Path, icon_path: Path, uninstall_exe: Path | None):
    """Registers the application in Windows Settings > Installed Apps."""
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\OFFLINE11"
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, APP_NAME)
            winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, VERSION)
            winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, PUBLISHER)
            winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, str(icon_path))
            winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, str(install_dir))
            
            if uninstall_exe and uninstall_exe.exists():
                winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, f'"{uninstall_exe}"')
                winreg.SetValueEx(key, "QuietUninstallString", 0, winreg.REG_SZ, f'"{uninstall_exe}" --silent')
            else:
                uninstall_py = install_dir / "uninstall.py"
                winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, f'"{sys.executable}" "{uninstall_py}"')

            winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)
    except Exception as e:
        print(f"Warning: Could not register in Windows Uninstall list: {e}")


def install():
    base_dir = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent

    # Locate source distribution directory
    source_dist = None
    if (base_dir / "OFFLINE11").is_dir() and (base_dir / "OFFLINE11" / "OFFLINE11.exe").exists():
        source_dist = base_dir / "OFFLINE11"
    elif (base_dir / "dist" / "OFFLINE11").is_dir() and (base_dir / "dist" / "OFFLINE11" / "OFFLINE11.exe").exists():
        source_dist = base_dir / "dist" / "OFFLINE11"
    elif (base_dir / "OFFLINE11.exe").exists():
        source_dist = base_dir

    if not source_dist or not (source_dist / "OFFLINE11.exe").exists():
        show_ui_message(
            "Installation Error",
            f"Could not find OFFLINE11 program files in:\n{base_dir}\n\nPlease ensure 'install.exe' is in the same folder as 'OFFLINE11'.",
            is_error=True,
        )
        sys.exit(1)

    # Locate icon
    icon_src = None
    for p in [
        base_dir / "assets" / "icon.ico",
        base_dir / "icon.ico",
        source_dist / "assets" / "icon.ico",
        source_dist / "icon.ico",
    ]:
        if p.exists():
            icon_src = p
            break

    # Locate uninstaller binary or script
    uninstall_src = None
    for p in [
        base_dir / "uninstall.exe",
        base_dir / "dist" / "uninstall.exe",
        base_dir / "uninstall.py",
    ]:
        if p.exists():
            uninstall_src = p
            break

    install_dir, start_menu_dir, desktop_dir = get_paths()

    # Kill any active instances to avoid locked file errors
    kill_running_instances()

    # Create destination directory
    install_dir.mkdir(parents=True, exist_ok=True)

    def safe_copy(src_item: Path, dst_item: Path):
        for attempt in range(5):
            try:
                if src_item.is_dir():
                    shutil.copytree(src_item, dst_item, dirs_exist_ok=True)
                else:
                    shutil.copy2(src_item, dst_item)
                return
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.5)

    # Copy program files
    for item in source_dist.iterdir():
        # Do not recursively copy install.exe/uninstall.exe if running from install_dir
        if item.name.lower() in ["install.exe", "install.py"]:
            continue
        dest = install_dir / item.name
        safe_copy(item, dest)

    # Copy icon
    dest_icon = install_dir / "icon.ico"
    if icon_src and icon_src.exists():
        safe_copy(icon_src, dest_icon)

    # Copy uninstaller
    dest_uninstall = None
    if uninstall_src and uninstall_src.exists():
        dest_uninstall = install_dir / uninstall_src.name
        safe_copy(uninstall_src, dest_uninstall)

    target_exe = install_dir / "OFFLINE11.exe"

    # Create Start Menu shortcut
    start_shortcut = start_menu_dir / f"{APP_NAME}.lnk"
    create_shortcut(target_exe, start_shortcut, dest_icon, APP_DESCRIPTION)

    # Create Start Menu Uninstall shortcut
    if dest_uninstall and dest_uninstall.exists():
        start_uninstall_shortcut = start_menu_dir / f"Uninstall {APP_NAME}.lnk"
        create_shortcut(dest_uninstall, start_uninstall_shortcut, dest_icon, f"Uninstall {APP_NAME}")

    # Create Desktop shortcut
    desk_shortcut = desktop_dir / f"{APP_NAME}.lnk"
    create_shortcut(target_exe, desk_shortcut, dest_icon, APP_DESCRIPTION)

    # Register in Windows Installed Apps
    register_uninstall(install_dir, dest_icon, dest_uninstall)

    show_ui_message(
        "OFFLINE 11 Setup",
        f"{APP_NAME} has been successfully installed!\n\n"
        "• Searchable via Windows Start Menu (type 'OFFLINE 11')\n"
        "• Shortcut added to your Desktop\n"
        "• Manage or Uninstall anytime from Windows Settings > Installed Apps",
    )


if __name__ == "__main__":
    try:
        install()
    except Exception as e:
        show_ui_message("Installation Error", f"Failed to install OFFLINE 11:\n{e}", is_error=True)
        sys.exit(1)
