@echo off
echo ============================================================
echo Starting OFFLINE 11 in Safe Accelerated Test Mode (Dry Run)
echo ============================================================
echo Timeline compressed into 60 seconds:
echo   +10s: Warning 1 (30m warning)
echo   +20s: Warning 2 (10m warning)
echo   +30s: Curfew Begins (Dialog displayed)
echo   +35s: Grace Reminder 1
echo   +40s: Grace Reminder 2
echo   +45s: Final 1-Minute Warning
echo   +50s: Simulated Dry-Run Shutdown
echo.
echo Real shutdown will NOT be executed.
echo ============================================================
python offline11\main.py --test-mode --debug
pause
