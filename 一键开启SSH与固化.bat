@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0一键开启SSH与固化.ps1"
if %errorlevel% neq 0 (
    echo.
    pause
)
