@echo off
setlocal enabledelayedexpansion
title Ghostline [DEV MODE]
cd /d "%~dp0"
echo ========================================================
echo   GHOSTLINE [DEVELOPMENT MODE] (v1.0.1)
echo   Running directly from Development Source Tree
echo   Source Directory: %~dp0
echo   Console output, real-time logging, and diagnostics active
echo   Trigger Hotkey: Alt + /
echo ========================================================

:: 1. Synchronize real AppData config with Windows Store Python LocalCache if present
for /d %%D in ("%LOCALAPPDATA%\Packages\PythonSoftwareFoundation.*") do (
    if exist "%%D\LocalCache\Roaming\Ghostline" (
        if exist "%APPDATA%\Ghostline\config.json" (
            copy /y "%APPDATA%\Ghostline\config.json" "%%D\LocalCache\Roaming\Ghostline\config.json" >nul 2>&1
        )
    )
)

:: 2. Resolve Python interpreter (check local venvs first, then system path)
set "PYTHON_EXE="
if exist "%~dp0venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0venv\Scripts\python.exe"
) else if exist "%~dp0.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
) else (
    where python >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        set "PYTHON_EXE=python"
    )
)

if not defined PYTHON_EXE (
    echo [!] Python runtime not found in system PATH or local venv.
    pause
    exit /b 1
)

set "GHOSTLINE_MODE=DEVELOPMENT"
set "PYTHONPATH=%~dp0;%PYTHONPATH%"
set "PYTHONUNBUFFERED=1"

"%PYTHON_EXE%" -m ghostline.app %*
set "APP_EXIT=%ERRORLEVEL%"

if %APP_EXIT% neq 0 (
    echo.
    echo ========================================================
    echo   [!] Ghostline exited with error code %APP_EXIT%.
    echo   Diagnostic logs: %APPDATA%\Ghostline\ghostline.log
    echo ========================================================
    echo.
    pause
    exit /b %APP_EXIT%
)

exit /b 0
