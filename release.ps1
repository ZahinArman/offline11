# Builds and publishes a ShutCap release.
#   .\release.ps1 2.1.0 "What changed, one line"
# Steps: set version -> run tests -> build ShutCap-Setup.exe -> secret scan -> commit + tag -> push -> GitHub release.
param(
    [Parameter(Mandatory = $true)][ValidatePattern('^\d+\.\d+\.\d+$')][string]$Version,
    [string]$Notes = "ShutCap $Version"
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$repo = "ZahinArman/shutcap"

if (git status --porcelain) { throw "Commit or stash your changes first; releases are built from a clean tree." }
if (git tag -l "v$Version") { throw "v$Version already exists." }
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { throw "GitHub CLI not found. winget install GitHub.cli" }

# 1) Version everywhere it appears (UTF-8 without BOM so non-ASCII text stays intact).
$utf8 = New-Object System.Text.UTF8Encoding $false
function Set-Version($relPath, $pattern, $replacement) {
    $path = Join-Path $PSScriptRoot $relPath
    $text = [IO.File]::ReadAllText($path, $utf8)
    $new = $text -replace $pattern, $replacement
    if ($new -eq $text -and $text -notmatch [regex]::Escape($replacement)) { throw "Version string not found in $relPath" }
    [IO.File]::WriteAllText($path, $new, $utf8)
}
Set-Version "shutcap\__init__.py" '__version__ = "[0-9.]+"' "__version__ = `"$Version`""
Set-Version "install.py" '(?m)^VERSION = "[0-9.]+"' "VERSION = `"$Version`""

# 2) Build environment: a private venv with the packages from requirements.txt (incl. PyInstaller).
$venvPy = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    python -m venv (Join-Path $PSScriptRoot ".venv")
    if ($LASTEXITCODE -ne 0) { throw "Could not create .venv (is Python installed?)." }
}
& $venvPy -m pip install -q --disable-pip-version-check -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "pip install failed." }

# 3) Tests, then the installer.
& $venvPy tests\run_all_tests.py
if ($LASTEXITCODE -ne 0) { git checkout -- shutcap\__init__.py install.py; throw "Tests failed. Nothing was committed or pushed." }
$setup = Join-Path $PSScriptRoot "dist\ShutCap-Setup.exe"
Remove-Item $setup -ErrorAction SilentlyContinue
$env:PY = $venvPy
cmd /c "`"$(Join-Path $PSScriptRoot 'build_exe.bat')`" --no-pause"
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $setup)) { throw "Build failed." }

# 4) Secret scan, then commit + tag.
git add -A
powershell -NoProfile -ExecutionPolicy Bypass -File tools\scan-secrets.ps1
if ($LASTEXITCODE -ne 0) { git reset -q; throw "Secret scan failed. Nothing was committed or pushed." }
if (git status --porcelain) { git commit -q -m "Release v$Version" }
git tag -a "v$Version" -m "ShutCap $Version"

# 5) Push and publish. The asset is always named ShutCap-Setup.exe so the
#    .../releases/latest/download/ShutCap-Setup.exe link on the website never changes.
git push -q origin HEAD --follow-tags
gh release create "v$Version" $setup --repo $repo --title "ShutCap $Version" --notes $Notes --latest
if ($LASTEXITCODE -ne 0) { throw "GitHub release failed (the tag was pushed; rerun: gh release create v$Version dist\ShutCap-Setup.exe)." }
Write-Output "Released v${Version}: https://github.com/$repo/releases/tag/v$Version"
