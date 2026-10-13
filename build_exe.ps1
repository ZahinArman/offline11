# Build OFFLINE 11 Windows Executable using PowerShell and PyInstaller
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Building OFFLINE 11 Standalone Executable" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

python -m PyInstaller `
    --noconsole `
    --onedir `
    --name OFFLINE11 `
    --icon assets\icon.ico `
    --add-data "assets\icon.png;assets" `
    --add-data "assets\icon.ico;assets" `
    --clean `
    -y `
    offline11\main.py

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "[SUCCESS] Executable built in: dist\OFFLINE11\OFFLINE11.exe" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "[ERROR] Build failed with exit code $LASTEXITCODE" -ForegroundColor Red
}
