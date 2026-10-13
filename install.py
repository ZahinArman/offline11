"""
Windows Application Installer for OFFLINE 11.
Integrates OFFLINE 11 as a first-class Windows app:
- Installs to %LOCALAPPDATA%\\Programs\\OFFLINE 11 (standard user app location like VS Code/Chrome)
- Creates Start Menu shortcut (makes it searchable via Windows Start Menu)
- Creates Desktop shortcut
- Registers in Windows 'Installed Apps' / Settings
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import winreg
from pathlib import Path

APP_NAME = "OFFLINE 11"
APP_DESCRIPTION = "Strict PC Curfew Utility for Windows"
PUBLISHER = "OFFLINE 11"
VERSION = "1.0.0"


def get_paths():
    import ctypes
    from ctypes import wintypes

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


def register_uninstall(install_dir: Path, target_exe: Path, icon_path: Path):
    """Registers the application in Windows Settings > Installed Apps."""
    key_path = fr"Software\Microsoft\Windows\CurrentVersion\Uninstall\OFFLINE11"
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, APP_NAME)
            winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, VERSION)
            winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, PUBLISHER)
            winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, str(icon_path))
            winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, str(install_dir))
            # Uninstall command
            uninstall_cmd = f'"{sys.executable}" "{install_dir / "uninstall.py"}"'
            winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, uninstall_cmd)
            winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)
    except Exception as e:
        print(f"Warning: Could not register in Windows Uninstall list: {e}")


def install():
    source_dist = Path(__file__).resolve().parent / "dist" / "OFFLINE11"
    icon_src = Path(__file__).resolve().parent / "assets" / "icon.ico"

    if not source_dist.exists() or not (source_dist / "OFFLINE11.exe").exists():
        print("Error: Compiled binary not found in dist/OFFLINE11. Please run build_exe.bat first.")
        sys.exit(1)

    install_dir, start_menu_dir, desktop_dir = get_paths()
    print(f"Installing {APP_NAME} to: {install_dir}")

    # Create destination directory
    install_dir.mkdir(parents=True, exist_ok=True)

    # Copy files
    for item in source_dist.iterdir():
        dest = install_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)

    # Ensure icon is in install dir
    dest_icon = install_dir / "icon.ico"
    if icon_src.exists():
        shutil.copy2(icon_src, dest_icon)

    target_exe = install_dir / "OFFLINE11.exe"

    # Create Start Menu shortcut (makes it searchable in Windows Start menu!)
    start_shortcut = start_menu_dir / f"{APP_NAME}.lnk"
    print(f"Creating Start Menu shortcut: {start_shortcut}")
    create_shortcut(target_exe, start_shortcut, dest_icon, APP_DESCRIPTION)

    # Create Desktop shortcut
    desk_shortcut = desktop_dir / f"{APP_NAME}.lnk"
    print(f"Creating Desktop shortcut: {desk_shortcut}")
    create_shortcut(target_exe, desk_shortcut, dest_icon, APP_DESCRIPTION)

    # Register in Windows Installed Apps
    register_uninstall(install_dir, target_exe, dest_icon)

    print("\n============================================================")
    print(f"[SUCCESS] {APP_NAME} installed as a native Windows App!")
    print("============================================================")
    print("You can now:")
    print("1. Press the Windows Key and type 'OFFLINE 11' to search & open it.")
    print("2. Open it from the shortcut on your Desktop.")
    print("3. Right-click the Start Menu icon and choose 'Pin to taskbar'.")
    print("============================================================")


if __name__ == "__main__":
    install()
