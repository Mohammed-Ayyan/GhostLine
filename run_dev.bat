@echo off
title Ghostline Developer Console
cd /d "%~dp0"
echo ========================================================
echo   Ghostline Developer Mode
echo   Console output, real-time logging, and diagnostics active
echo   Trigger Hotkey: Alt + /
echo ========================================================

:: Synchronize real AppData config with Windows Store Python LocalCache if present
for /d %%D in ("%LOCALAPPDATA%\Packages\PythonSoftwareFoundation.*") do (
    if exist "%%D\LocalCache\Roaming\Ghostline" (
        if exist "%APPDATA%\Ghostline\config.json" (
            copy /y "%APPDATA%\Ghostline\config.json" "%%D\LocalCache\Roaming\Ghostline\config.json" >nul 2>&1
        )
    )
)

python ghostline\app.py
pause
