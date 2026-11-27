@echo off
setlocal
cd /d "%~dp0"
echo ============================================================
echo Building OFFLINE 11 Setup (single self-contained installer)
echo ============================================================

echo [1/3] Building OFFLINE 11 application...
python -m PyInstaller --noconsole --onedir --name OFFLINE11 --icon assets\icon.ico ^
    --add-data "assets\icon.png;assets" --add-data "assets\icon.ico;assets" ^
    --clean -y offline11\main.py
if errorlevel 1 goto :fail

echo [2/3] Building uninstaller...
python -m PyInstaller --noconsole --onefile --name uninstall --icon assets\icon.ico -y uninstall.py
if errorlevel 1 goto :fail

echo [3/3] Building OFFLINE11-Setup.exe (bundles the app and uninstaller)...
python -m PyInstaller --noconsole --onefile --name OFFLINE11-Setup --icon assets\icon.ico ^
    --add-data "dist\OFFLINE11;payload\OFFLINE11" ^
    --add-data "dist\uninstall.exe;payload" ^
    --add-data "assets\icon.ico;payload" ^
    -y install.py
if errorlevel 1 goto :fail

echo.
echo ============================================================
echo Done. Share this single file:  dist\OFFLINE11-Setup.exe
echo ============================================================
pause
exit /b 0

:fail
echo.
echo [ERROR] Build failed. See the messages above.
pause
exit /b 1
