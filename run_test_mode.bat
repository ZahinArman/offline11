@echo off
echo ============================================================
echo ShutCap test mode (dry run)
echo ============================================================
echo Your schedule plays on a fast clock in about 60 seconds.
echo All warnings show. The PC does NOT turn off.
echo Test mode does not change your real schedule or tonight's state.
echo ============================================================
python shutcap\main.py --test-mode --debug
pause
