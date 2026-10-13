# Build OFFLINE 11 Windows Executable Suite using PowerShell and PyInstaller
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Building OFFLINE 11 Suite (App, Installer, Uninstaller)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

Write-Host "`n[1/3] Building OFFLINE 11 main application..." -ForegroundColor Yellow
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

Write-Host "`n[2/3] Building Uninstaller (uninstall.exe)..." -ForegroundColor Yellow
python -m PyInstaller `
    --noconsole `
    --onefile `
    --name uninstall `
    --icon assets\icon.ico `
    -y `
    uninstall.py

Write-Host "`n[3/3] Building Installer (install.exe)..." -ForegroundColor Yellow
python -m PyInstaller `
    --noconsole `
    --onefile `
    --name install `
    --icon assets\icon.ico `
    -y `
    install.py

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n============================================================" -ForegroundColor Green
    Write-Host "[SUCCESS] OFFLINE 11 suite built successfully!" -ForegroundColor Green
    Write-Host "Artifacts in dist:" -ForegroundColor Green
    Write-Host "  - dist\OFFLINE11\OFFLINE11.exe" -ForegroundColor Green
    Write-Host "  - dist\install.exe" -ForegroundColor Green
    Write-Host "  - dist\uninstall.exe" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
} else {
    Write-Host "`n[ERROR] Build failed with exit code $LASTEXITCODE" -ForegroundColor Red
}
