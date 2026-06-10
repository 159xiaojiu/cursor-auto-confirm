@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8

echo Cleaning up any old instances...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { ($_.Name -eq 'python.exe' -or $_.Name -eq 'pythonw.exe') -and $_.CommandLine -like '*src.main*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
if exist autopilot.lock del autopilot.lock >nul 2>&1
ping 127.0.0.1 -n 2 >nul

echo Starting Cursor Auto-Confirm helper (background, no window)...
start "" "C:\Users\23986\autopilot_venv\Scripts\pythonw.exe" -X utf8 -m src.main
echo Started. It now auto-clicks Accept / Run / Continue in Cursor.
echo   Pause/Resume: Ctrl+Alt+A    Quit: Ctrl+Alt+Q (or run stop.bat)
echo   Log: logs\autopilot.log
ping 127.0.0.1 -n 3 >nul
