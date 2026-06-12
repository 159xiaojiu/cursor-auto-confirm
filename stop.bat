@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Stopping all Cursor Auto-Confirm instances...
taskkill /F /IM CursorAutoConfirm.exe >nul 2>&1
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { ($_.Name -eq 'python.exe' -or $_.Name -eq 'pythonw.exe') -and ($_.CommandLine -like '*src.main*' -or $_.CommandLine -like '*launcher.py*') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
if exist autopilot.lock del autopilot.lock >nul 2>&1
if exist app.lock del app.lock >nul 2>&1
echo Done.
ping 127.0.0.1 -n 2 >nul
