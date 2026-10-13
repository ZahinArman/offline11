@echo off
echo ============================================================
echo Building OFFLINE 11 Windows Standalone Executable
echo ============================================================

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
echo Build completed. Executable is located in dist\OFFLINE11\OFFLINE11.exe
pause
