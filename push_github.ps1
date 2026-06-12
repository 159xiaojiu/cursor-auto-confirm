# Push current project to GitHub
$ErrorActionPreference = 'Continue'
Set-Location $PSScriptRoot

if (-not (Test-Path .git)) {
    Write-Host '[FAIL] This folder is not a Git project.'
    exit 1
}

$status = git status --porcelain 2>$null
if (-not $status) {
    Write-Host '[SKIP] No changes to save.'
    exit 0
}

git add -A
$stamp = Get-Date -Format 'yyyy-MM-dd HH:mm'
git commit -m "Save checkpoint $stamp" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host '[FAIL] Commit failed.'
    exit 1
}

$hash = git rev-parse --short HEAD
git push 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Saved and pushed: $hash"
} else {
    Write-Host "[LOCAL] Saved locally: $hash (push failed)"
}
