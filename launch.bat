@echo off
chcp 65001 >nul
cd /d "%~dp0"
start "" "C:\Users\23986\autopilot_venv\Scripts\pythonw.exe" -X utf8 launcher.py
