# Fails (exit 1) if anything that looks like a key, token, email or personal path is in the repo:
# the files git tracks or is about to commit, AND every past commit. Runs before every release.
#   powershell -ExecutionPolicy Bypass -File tools\scan-secrets.ps1
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$bad = $false

# 1) gitleaks, if installed (winget install Gitleaks.Gitleaks): the thorough scan of all history.
$gl = Get-Command gitleaks -ErrorAction SilentlyContinue
if ($gl) {
    $ErrorActionPreference = "Continue" # gitleaks logs to stderr; only its exit code matters
    & $gl.Source git --no-banner --redact --log-level warn . 2>&1 | ForEach-Object { "$_" }
    if ($LASTEXITCODE -ne 0) { $bad = $true }
    $ErrorActionPreference = "Stop"
} else {
    Write-Output "gitleaks not found; running the built-in patterns only."
}

# 2) Built-in patterns, on tracked + about-to-be-committed files and on full history.
$patterns = @(
    'gh[pousr]_[A-Za-z0-9]{30,}',          # GitHub tokens
    'github_pat_[A-Za-z0-9_]{30,}',        # GitHub fine-grained tokens
    'sk-[A-Za-z0-9_-]{20,}',               # OpenAI / Anthropic style API keys
    'AKIA[0-9A-Z]{16}',                    # AWS access key IDs
    '-----BEGIN [A-Z ]*PRIVATE KEY-----',  # private keys
    'C:\\Users\\[A-Za-z]+'                 # personal Windows paths
)
# Email addresses in files (commit trailers like noreply@ are fine).
$emailPattern = '(?<![\w.+-])(?!noreply@)[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z.]{2,}'
$files = git ls-files --cached --others --exclude-standard
foreach ($f in $files) {
    if (-not (Test-Path -LiteralPath $f -PathType Leaf)) { continue }
    if ($f -match '\.(png|jpg|jpeg|gif|ico|exe|webp|mp4)$') { continue }
    $text = Get-Content -Raw -LiteralPath $f
    if ($null -eq $text) { continue }
    foreach ($p in $patterns) {
        foreach ($m in [regex]::Matches($text, $p)) {
            $v = $m.Value; $show = $v.Substring(0, [Math]::Min(6, $v.Length)) + "..."
            Write-Output "FOUND in ${f}: $show  (pattern: $p)"
            $bad = $true
        }
    }
    foreach ($m in [regex]::Matches($text, $emailPattern)) {
        Write-Output "FOUND email in ${f}: $($m.Value.Substring(0, 3))..."
        $bad = $true
    }
}
# --format= drops the "commit <hash>" lines.
$history = (git log -p --all --no-color --format= 2>$null) -join "`n"
foreach ($p in $patterns) {
    if ([regex]::IsMatch($history, $p)) {
        Write-Output "FOUND in git history (pattern: $p). Run: git log -p --all -G '<pattern>'"
        $bad = $true
    }
}

if ($bad) { Write-Output "Secret scan FAILED. Nothing was pushed."; exit 1 }
Write-Output "Secret scan passed."
