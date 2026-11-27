"""
Windows installer for ShutCap (built into a single self-contained ShutCap-Setup.exe).

One confirmation, then:
- installs to %LOCALAPPDATA%\\Programs\\ShutCap (per-user, no admin rights needed)
- creates Start Menu + Desktop shortcuts and an "Uninstall ShutCap" Start Menu entry
- registers in Windows Settings > Apps > Installed apps
- starts ShutCap automatically at login (can be turned off in Settings)
- launches the app

Re-running the setup upgrades/repairs an existing installation in place.
Your settings and history in %LOCALAPPDATA%\\ShutCap are kept across upgrades.
"""

from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import sys
import time
import webbrowser
import winreg
from ctypes import wintypes
from pathlib import Path
from typing import Optional

APP_NAME = "ShutCap"
APP_EXE = "ShutCap.exe"
APP_DESCRIPTION = "Turns your PC off at the time you choose"
PUBLISHER = "ShutCap"
VERSION = "2.0.0"
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\ShutCap"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
SILENT = "--silent" in sys.argv


RELEASES_URL = "https://github.com/ZahinArman/shutcap/releases/latest"


def log(message: str) -> None:
    print(f"[ShutCap Setup] {message}")


# --- Paths -----------------------------------------------------------------------------

def _shell_folder(csidl: int) -> Path:
    buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
    ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, buf)
    return Path(buf.value)


def default_install_dir() -> Path:
    local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return local_app_data / "Programs" / APP_NAME


def existing_install_dir() -> Optional[Path]:
    """The folder of an installed copy (from Settings > Apps), if there is one."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as key:
            location = Path(winreg.QueryValueEx(key, "InstallLocation")[0])
        if (location / APP_EXE).exists():
            return location
    except OSError:
        pass
    default = default_install_dir()
    return default if (default / APP_EXE).exists() else None


def target_for(picked: Path) -> Path:
    """ShutCap always goes into its own folder, so it never mixes with (or deletes) other files."""
    return picked if picked.name.lower() == APP_NAME.lower() else picked / APP_NAME


def check_folder(install_dir: Path) -> Optional[str]:
    """Returns a short error for the UI, or None if the folder can be used."""
    if install_dir.exists():
        if not install_dir.is_dir():
            return "Choose a folder, not a file."
        if any(install_dir.iterdir()) and not (install_dir / APP_EXE).exists():
            return "This folder has other files in it. Choose a different folder."
    probe_parent = install_dir if install_dir.exists() else next((p for p in install_dir.parents if p.exists()), None)
    if probe_parent is None:
        return "This drive is not available."
    try:
        probe = probe_parent / f".shutcap_write_test_{os.getpid()}"
        probe.write_text("x", encoding="ascii")
        probe.unlink()
    except OSError:
        return "You cannot save files in this folder. Choose a different folder."
    return None


def get_shell_dirs() -> tuple[Path, Path]:
    return _shell_folder(0x0002), _shell_folder(0x0010)  # CSIDL_PROGRAMS, CSIDL_DESKTOPDIRECTORY


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
        if app_dir is None and (base / "ShutCap" / APP_EXE).exists():
            app_dir = base / "ShutCap"
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
    # Only an existing ShutCap folder is ever deleted (check_folder refuses folders with other files).
    if install_dir.exists() and (install_dir / APP_EXE).exists():
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


def do_install(app_dir: Path, uninstaller: Optional[Path], icon: Optional[Path],
               install_dir: Path, autostart: bool, launch: bool = True) -> None:
    error = check_folder(install_dir)
    if error:
        raise ValueError(error)
    start_menu_dir, desktop_dir = get_shell_dirs()
    stop_running_app()
    copy_program_files(app_dir, uninstaller, icon, install_dir)

    app_exe = install_dir / APP_EXE
    icon_dest = install_dir / "icon.ico"
    create_shortcut(app_exe, start_menu_dir / f"{APP_NAME}.lnk", icon_dest, APP_DESCRIPTION)
    create_shortcut(app_exe, desktop_dir / f"{APP_NAME}.lnk", icon_dest, APP_DESCRIPTION)
    if (install_dir / "uninstall.exe").exists():
        create_shortcut(install_dir / "uninstall.exe", start_menu_dir / f"Uninstall {APP_NAME}.lnk", icon_dest, f"Uninstall {APP_NAME}")
    register_app(install_dir)
    if autostart:
        enable_autostart(app_exe)
    else:
        disable_autostart()
    if launch:
        launch_app(app_exe)


def disable_autostart() -> None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, APP_NAME)
    except OSError:
        pass


def install() -> None:
    app_dir, uninstaller, icon = find_payload()
    existing = existing_install_dir()

    if SILENT:
        if app_dir is None:
            log("The program files were not found inside this setup.")
            sys.exit(1)
        target = existing or default_install_dir()
        do_install(app_dir, uninstaller, icon, target, autostart=True)
        log(f"Installed to {target}")
        return

    from shutcap.ui.setup_window import SetupApi, run_setup_window

    state = {"stage": "install", "folder": str(existing or default_install_dir()),
             "upgrade": existing is not None, "version": VERSION, "error": ""}
    if app_dir is None:
        state.update(stage="failed", error="This setup file is damaged. Download it again.", action="Open download page")
    else:
        state["error"] = check_folder(Path(state["folder"])) or ""

    def worker(autostart: bool) -> dict:
        target = Path(api.status()["folder"])
        error = check_folder(target)
        if error:
            return {"stage": "install", "error": error}
        do_install(app_dir, uninstaller, icon, target, autostart=autostart)
        return {"stage": "done"}

    def choose(picked: str) -> dict:
        target = target_for(Path(picked))
        return {"folder": str(target), "error": check_folder(target) or ""}

    api = SetupApi("install", state, worker, choose_folder=choose,
                   failed_action=lambda: webbrowser.open(RELEASES_URL))
    run_setup_window(api, f"{APP_NAME} Setup")


if __name__ == "__main__":
    try:
        install()
    except SystemExit:
        raise
    except Exception as e:
        log(f"Failed to install {APP_NAME}: {e}")
        sys.exit(1)
