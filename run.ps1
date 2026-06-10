# Launcher for Cursor Auto-Confirm helper.
# Usage:
#   .\run.ps1            run normally
#   .\run.ps1 --once     scan once
#   .\run.ps1 --dry-run  detect without clicking
#   .\run.ps1 --selftest startup self-test
$ErrorActionPreference = "Stop"
$venvPython = "C:\Users\23986\autopilot_venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "venv python not found: $venvPython" -ForegroundColor Red
    Write-Host "Please install dependencies first (see README)." -ForegroundColor Yellow
    exit 1
}
$env:PYTHONIOENCODING = "utf-8"
& $venvPython -X utf8 -m src.main @args
