@echo off
rem Builds dist\ShutCap-Setup.exe.  Usage: build_exe.bat [--no-pause]
rem Set PY to a specific python.exe to build with it (release.ps1 does this); default is "python".
setlocal
cd /d "%~dp0"
if not defined PY set "PY=python"
echo ============================================================
echo Building ShutCap Setup (single self-contained installer)
echo ============================================================

echo [1/3] Building ShutCap application...
"%PY%" -m PyInstaller --noconsole --onedir --name ShutCap --icon assets\icon.ico ^
    --add-data "assets\icon.png;assets" --add-data "assets\icon.ico;assets" ^
    --clean -y shutcap\main.py
if errorlevel 1 goto :fail

echo [2/3] Building uninstaller...
"%PY%" -m PyInstaller --noconsole --onefile --name uninstall --icon assets\icon.ico -y uninstall.py
if errorlevel 1 goto :fail

echo [3/3] Building ShutCap-Setup.exe (bundles the app and uninstaller)...
"%PY%" -m PyInstaller --noconsole --onefile --name ShutCap-Setup --icon assets\icon.ico ^
    --add-data "dist\ShutCap;payload\ShutCap" ^
    --add-data "dist\uninstall.exe;payload" ^
    --add-data "assets\icon.ico;payload" ^
    -y install.py
if errorlevel 1 goto :fail

echo.
echo ============================================================
echo Done. Share this single file:  dist\ShutCap-Setup.exe
echo ============================================================
if not "%~1"=="--no-pause" pause
exit /b 0

:fail
echo.
echo [ERROR] Build failed. See the messages above.
if not "%~1"=="--no-pause" pause
exit /b 1
