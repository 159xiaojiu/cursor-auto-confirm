# 一键推送到 GitHub（需先运行 gh auth login）
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path .git)) { git init; git branch -M main }
git config user.name "liangbaoying"
git config user.email "liangbaoying4@gmail.com"
if (-not (git remote | Select-String origin)) {
  git remote add origin https://github.com/159xiaojiu/cursor-auto-confirm.git
}
git add -A
git status --short
git commit -m "Sync local project to GitHub" 2>$null
git push -u origin main
