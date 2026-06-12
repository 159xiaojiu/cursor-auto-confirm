@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0push_github.ps1"
echo.
pause
