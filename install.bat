@echo off
title Ghostline Installer
echo ========================================================
echo   Launching Ghostline Setup...
echo ========================================================
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer.ps1"
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Installation failed with exit code %ERRORLEVEL%.
    pause
) else (
    echo.
    echo Press any key to exit setup...
    pause >nul
)
