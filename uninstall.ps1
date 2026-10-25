# Ghostline Clean Windows Uninstaller Script
# Safely terminates processes, removes shortcuts, cleans registry, and manages user data

param(
    [switch]$Silent = $false,
    [switch]$RemoveUserData = $false
)

Write-Host "==========================================================" -ForegroundColor Red
Write-Host "  Ghostline Application Uninstaller" -ForegroundColor Red
Write-Host "==========================================================" -ForegroundColor Red

# 1. Terminate running instances
Write-Host "`n[*] Terminating any running Ghostline processes..." -ForegroundColor Yellow
$proc = Get-Process -Name "Ghostline" -ErrorAction SilentlyContinue
if ($proc) {
    $proc | Stop-Process -Force
    Start-Sleep -Seconds 1
    Write-Host "  [+] Active processes terminated." -ForegroundColor Green
} else {
    Write-Host "  [+] No active process found." -ForegroundColor Gray
}

# 2. Remove Shortcuts
Write-Host "[*] Removing shortcuts..." -ForegroundColor Yellow
$shortcutsToRemove = @(
    (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Ghostline\Ghostline.lnk"),
    (Join-Path ([System.Environment]::GetFolderPath("Desktop")) "Ghostline.lnk")
)

foreach ($lnk in $shortcutsToRemove) {
    if (Test-Path $lnk) {
        Remove-Item -Path $lnk -Force -ErrorAction SilentlyContinue
        Write-Host "  [+] Removed shortcut: $lnk" -ForegroundColor Green
    }
}

$startMenuFolder = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Ghostline"
if (Test-Path $startMenuFolder) {
    Remove-Item -Path $startMenuFolder -Recurse -Force -ErrorAction SilentlyContinue
}

# 3. Clean Windows Registry Entry
Write-Host "[*] Cleaning Windows Settings registration..." -ForegroundColor Yellow
$regKeys = @(
    "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\Ghostline"
)

foreach ($key in $regKeys) {
    if (Test-Path $key) {
        Remove-Item -Path $key -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "  [+] Unregistered from Windows Settings ($key)." -ForegroundColor Green
    }
}

# 4. Handle User Configuration and History Data (%APPDATA%\Ghostline)
$userDataDirs = @(
    (Join-Path $env:APPDATA "Ghostline")
)

foreach ($appDataDir in $userDataDirs) {
    if (Test-Path $appDataDir) {
        if ($RemoveUserData) {
            Remove-Item -Path $appDataDir -Recurse -Force -ErrorAction SilentlyContinue
            Write-Host "  [+] Removed user settings and history data: $appDataDir" -ForegroundColor Green
        } elseif (-not $Silent) {
            $keep = Read-Host "`nDo you want to KEEP your saved questions and settings in $appDataDir? (Y/n)"
            if ($keep -match "^[nN]") {
                Remove-Item -Path $appDataDir -Recurse -Force -ErrorAction SilentlyContinue
                Write-Host "  [+] Removed user data: $appDataDir" -ForegroundColor Green
            } else {
                Write-Host "  [+] User configuration preserved for future re-installation." -ForegroundColor Cyan
            }
        }
    }
}

# 5. Remove Program Files from %LOCALAPPDATA%\Programs\Ghostline
$installDirs = @(
    (Join-Path $env:LOCALAPPDATA "Programs\Ghostline")
)

foreach ($installDir in $installDirs) {
    if (Test-Path $installDir) {
        Write-Host "`n[*] Removing program files from $installDir..." -ForegroundColor Yellow
        $tempBat = Join-Path $env:TEMP "ghostline_cleanup.bat"
        $batContent = @"
@echo off
timeout /t 2 /nobreak >nul
rmdir /s /q "$installDir"
del "%~f0"
"@
        Set-Content -Path $tempBat -Value $batContent
        Start-Process -FilePath "cmd.exe" -ArgumentList "/c `"$tempBat`"" -WindowStyle Hidden
        Write-Host "  [+] Program removal initiated." -ForegroundColor Green
    }
}

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host "  UNINSTALLATION COMPLETE" -ForegroundColor Green
Write-Host "  Ghostline has been cleanly removed from your system." -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
