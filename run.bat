@echo off
setlocal enabledelayedexpansion
title Ghostline
cd /d "%~dp0"

:: Check if user explicitly requested development mode
set "FORCE_DEV=0"
for %%A in (%*) do (
    if /i "%%A"=="--dev" set "FORCE_DEV=1"
    if /i "%%A"=="-dev" set "FORCE_DEV=1"
    if /i "%%A"=="--source" set "FORCE_DEV=1"
)

:: Check if installed copy exists
set "INSTALLED_EXE=%LOCALAPPDATA%\Programs\Ghostline\Ghostline.exe"

if "!FORCE_DEV!"=="0" (
    if exist "!INSTALLED_EXE!" (
        echo ========================================================
        echo   GHOSTLINE [INSTALLED PRODUCTION BUILD]
        echo   Launching: !INSTALLED_EXE!
        echo   (To launch development source instead, use: run.bat --dev or run_dev.bat)
        echo ========================================================
        start "" "!INSTALLED_EXE!" %*
        exit /b 0
    )
)

echo ========================================================
echo   GHOSTLINE [DEVELOPMENT MODE]
echo   Running from Source Tree: %~dp0
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
    echo ========================================================
    echo   [!] Ghostline Startup Error
    echo   Python runtime was not detected in system PATH or venv.
    echo   Please install Python 3.10+ or run setup.ps1 first.
    echo ========================================================
    pause
    exit /b 1
)

:: 3. Launch Ghostline application with PYTHONPATH set to project root
set "GHOSTLINE_MODE=DEVELOPMENT"
set "PYTHONPATH=%~dp0;%PYTHONPATH%"
set "PYTHONUNBUFFERED=1"

:: Filter out --dev argument before passing to python
set "ARGS=%*"
set "ARGS=!ARGS:--dev=!"
set "ARGS=!ARGS:-dev=!"
set "ARGS=!ARGS:--source=!"

"%PYTHON_EXE%" -m ghostline.app !ARGS!
set "APP_EXIT=%ERRORLEVEL%"

if %APP_EXIT% neq 0 (
    echo.
    echo ========================================================
    echo   [!] Ghostline exited with error code %APP_EXIT%.
    echo   Diagnostic logs are available at:
    echo   %APPDATA%\Ghostline\ghostline.log
    echo ========================================================
    echo.
    pause
    exit /b %APP_EXIT%
)

exit /b 0
