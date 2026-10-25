@echo off
setlocal
cd /d "%~dp0"

:: Synchronize real AppData config with Windows Store Python LocalCache if present
for /d %%D in ("%LOCALAPPDATA%\Packages\PythonSoftwareFoundation.*") do (
    if exist "%%D\LocalCache\Roaming\Ghostline" (
        if exist "%APPDATA%\Ghostline\config.json" (
            copy /y "%APPDATA%\Ghostline\config.json" "%%D\LocalCache\Roaming\Ghostline\config.json" >nul 2>&1
        )
    )
)

:: Verify Python runtime is reachable
where pythonw >nul 2>&1
if %ERRORLEVEL% equ 0 (
    start "" pythonw ghostline\app.py %*
    exit /b 0
)

where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
    start "" python ghostline\app.py %*
    exit /b 0
)

echo ========================================================
echo   [!] Ghostline Startup Error
echo   Python runtime was not detected in system PATH.
echo   Please install Python 3.10+ or run setup.ps1 first.
echo ========================================================
pause
exit /b 1
