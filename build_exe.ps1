# Builds a single self-contained OFFLINE11-Setup.exe with PyInstaller.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Invoke-Step($title, [string[]]$pyinstallerArgs) {
    Write-Host "`n$title" -ForegroundColor Yellow
    python -m PyInstaller @pyinstallerArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Host "`n[ERROR] Build failed with exit code $LASTEXITCODE" -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

Invoke-Step "[1/3] Building OFFLINE 11 application..." @(
    "--noconsole", "--onedir", "--name", "OFFLINE11", "--icon", "assets\icon.ico",
    "--add-data", "assets\icon.png;assets", "--add-data", "assets\icon.ico;assets",
    "--clean", "-y", "offline11\main.py")

Invoke-Step "[2/3] Building uninstaller..." @(
    "--noconsole", "--onefile", "--name", "uninstall", "--icon", "assets\icon.ico", "-y", "uninstall.py")

Invoke-Step "[3/3] Building OFFLINE11-Setup.exe (bundles the app and uninstaller)..." @(
    "--noconsole", "--onefile", "--name", "OFFLINE11-Setup", "--icon", "assets\icon.ico",
    "--add-data", "dist\OFFLINE11;payload\OFFLINE11",
    "--add-data", "dist\uninstall.exe;payload",
    "--add-data", "assets\icon.ico;payload",
    "-y", "install.py")

Write-Host "`n[SUCCESS] Share this single file: dist\OFFLINE11-Setup.exe" -ForegroundColor Green
