@echo off
setlocal enabledelayedexpansion
title Ghostline - Offline AI Environment Setup

echo ====================================================================
echo        Ghostline v1.0.0 -- Offline AI Environment Setup
echo ====================================================================
echo.
echo Ghostline runs 100%% offline using Ollama and local neural models.
echo This wizard verifies your local environment and installs required models.
echo Zero telemetry -- Zero cloud communication.
echo.

:: Step 1: Detect Ollama
echo [*] Step 1: Checking for local Ollama installation...
where ollama >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo     [OK] Ollama is installed and available on system PATH.
) else (
    if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" (
        echo     [OK] Found Ollama in %LOCALAPPDATA%\Programs\Ollama.
        set "PATH=%LOCALAPPDATA%\Programs\Ollama;%PATH%"
    ) else (
        echo     [!] Ollama was not found on your system.
        echo         Opening https://ollama.com/download/windows to download the official installer.
        start https://ollama.com/download/windows
        echo.
        echo Please complete the Ollama installation, then run this setup script again.
        pause
        exit /b 1
    )
)

echo.
:: Step 2: Verify Ollama service is active
echo [*] Step 2: Testing Ollama local daemon connection...
curl -s --connect-timeout 3 http://127.0.0.1:11434/api/tags >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo     [OK] Ollama daemon is actively running on http://127.0.0.1:11434.
) else (
    echo     [*] Starting Ollama server in background...
    start /B "" ollama serve >nul 2>nul
    timeout /t 3 >nul
    curl -s --connect-timeout 3 http://127.0.0.1:11434/api/tags >nul 2>nul
    if %ERRORLEVEL% EQU 0 (
        echo     [OK] Ollama daemon started successfully.
    ) else (
        echo     [!] Unable to connect to Ollama daemon. Please ensure Ollama is running.
    )
)

echo.
:: Step 3: Check and pull model phi3:mini
echo [*] Step 3: Checking for verified local reasoning model (phi3:mini)...
ollama list 2>nul | findstr /I "phi3:mini" >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo     [OK] Model phi3:mini is already downloaded and ready!
) else (
    echo     [!] Model phi3:mini is not yet installed.
    echo         Size: approx 2.2 GB.
    set /p PULL_CONFIRM="Download phi3:mini for Ghostline now? (Y/N): "
    if /I "!PULL_CONFIRM!"=="Y" (
        echo [*] Pulling phi3:mini model from local Ollama library...
        ollama pull phi3:mini
        if %ERRORLEVEL% EQU 0 (
            echo     [OK] phi3:mini pulled successfully!
        ) else (
            echo     [!] Model download encountered an issue. Check network and try again.
        )
    ) else (
        echo [*] Model download skipped. You can manually run: ollama pull phi3:mini
    )
)

echo.
echo ====================================================================
echo  Setup Completed! You can now launch Ghostline.
echo  Press Alt + / over any screen content to solve questions instantly.
echo ====================================================================
echo.
pause
