@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "EXE=%~dp0CursorAutoConfirm.exe"
set "ICON=%~dp0assets\app.ico"
set "LINK=%USERPROFILE%\Desktop\Cursor自动确认.lnk"

if not exist "%EXE%" (
    echo CursorAutoConfirm.exe not found in this folder.
    pause
    exit /b 1
)

powershell -NoProfile -Command ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%LINK%');" ^
  "$s.TargetPath='%EXE%';" ^
  "$s.WorkingDirectory='%~dp0';" ^
  "$s.IconLocation='%ICON%,0';" ^
  "$s.Description='Cursor 自动确认助手';" ^
  "$s.Save()"

echo.
echo Desktop shortcut created:
echo   %LINK%
echo.
echo Double-click it to open the app (Start / Stop buttons in taskbar window).
ping 127.0.0.1 -n 4 >nul
