@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHON=C:\Users\23986\autopilot_venv\Scripts\python.exe

echo [1/5] Generate icons...
"%PYTHON%" -X utf8 -c "from src.icon_assets import export_icons; export_icons('assets'); print('icons ok')"
if errorlevel 1 goto :fail

echo [2/5] Install PyInstaller...
"%PYTHON%" -m pip install pyinstaller -q
if errorlevel 1 goto :fail

echo [3/5] Build release (may take several minutes)...
"%PYTHON%" -m PyInstaller --noconfirm --clean CursorAutoConfirm.spec
if errorlevel 1 goto :fail

set DIST=dist\CursorAutoConfirm
set RELEASE=release\Cursor自动确认助手

echo [4/5] Assemble shareable folder...
if exist "%RELEASE%" rmdir /s /q "%RELEASE%"
mkdir "%RELEASE%"
xcopy /E /I /Y "%DIST%\*" "%RELEASE%\"
copy /Y config.yaml "%RELEASE%\config.yaml"
copy /Y "release\使用说明.txt" "%RELEASE%\使用说明.txt"
copy /Y "release\创建桌面快捷方式.bat" "%RELEASE%\创建桌面快捷方式.bat"
copy /Y "release\启动.bat" "%RELEASE%\启动.bat"

echo [5/5] Create zip...
if not exist release mkdir release
powershell -NoProfile -Command "Compress-Archive -Path '%RELEASE%' -DestinationPath 'release\Cursor自动确认助手_Win64.zip' -Force"
echo.
echo ========================================
echo  Build OK!
echo  Folder: %RELEASE%
echo  Zip:    release\Cursor自动确认助手_Win64.zip
echo  Share the zip with others. They unzip and double-click 启动.bat
echo ========================================
ping 127.0.0.1 -n 4 >nul
exit /b 0

:fail
echo Build FAILED.
pause
exit /b 1
