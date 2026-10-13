@echo off
echo ============================================================
echo Building OFFLINE 11 Suite (App, Installer, Uninstaller)
echo ============================================================

echo [1/3] Building OFFLINE 11 main application...
python -m PyInstaller ^
    --noconsole ^
    --onedir ^
    --name OFFLINE11 ^
    --icon assets\icon.ico ^
    --add-data "assets\icon.png;assets" ^
    --add-data "assets\icon.ico;assets" ^
    --clean ^
    -y ^
    offline11\main.py

echo.
echo [2/3] Building Uninstaller (uninstall.exe)...
python -m PyInstaller ^
    --noconsole ^
    --onefile ^
    --name uninstall ^
    --icon assets\icon.ico ^
    -y ^
    uninstall.py

echo.
echo [3/3] Building Installer (install.exe)...
python -m PyInstaller ^
    --noconsole ^
    --onefile ^
    --name install ^
    --icon assets\icon.ico ^
    -y ^
    install.py

echo.
echo ============================================================
echo Build completed successfully!
echo Artifacts in dist:
echo   - dist\OFFLINE11\OFFLINE11.exe
echo   - dist\install.exe
echo   - dist\uninstall.exe
echo ============================================================
pause
