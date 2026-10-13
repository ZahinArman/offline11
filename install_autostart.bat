@echo off
echo Registering OFFLINE 11 into Windows Startup Registry...
python -c "from offline11.autostart import enable_autostart; success = enable_autostart(); print('Auto-start enabled successfully!' if success else 'Failed to enable auto-start.')"
pause
