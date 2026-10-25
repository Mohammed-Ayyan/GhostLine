# Ghostline Windows Application Installer
# Installs standalone Ghostline to %LOCALAPPDATA%\Programs\Ghostline
# Registers shortcuts and Windows Add/Remove Programs uninstaller

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Ghostline Setup & Installer v1.0.0" -ForegroundColor Cyan
Write-Host "  100% Offline AI Desktop Assistant" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$installDir = Join-Path $env:LOCALAPPDATA "Programs\Ghostline"

$sourceDir = Join-Path $PSScriptRoot "dist\Ghostline"

if (-not (Test-Path $sourceDir)) {
    Write-Error "Build output not found at $sourceDir. Please run PyInstaller first."
    exit 1
}

# 1. Terminate running instances before overwrite
Write-Host "`n[*] Checking for active Ghostline instances..." -ForegroundColor Yellow
$activeProcesses = Get-Process -Name "Ghostline" -ErrorAction SilentlyContinue
if ($activeProcesses) {
    Write-Host "  [*] Closing running processes..." -ForegroundColor Yellow
    $activeProcesses | Stop-Process -Force
    Start-Sleep -Seconds 1
}

# 2. Deploy application files
Write-Host "[*] Installing to $installDir..." -ForegroundColor Yellow
if (-not (Test-Path $installDir)) {
    New-Item -ItemType Directory -Path $installDir -Force | Out-Null
}

Copy-Item -Path "$sourceDir\*" -Destination $installDir -Recurse -Force

foreach ($icoName in @("ghostline.ico")) {
    $icoSrc = Join-Path $PSScriptRoot $icoName
    if (Test-Path $icoSrc) {
        Copy-Item -Path $icoSrc -Destination (Join-Path $installDir $icoName) -Force
    }
}

# Copy uninstaller script to installation directory
$uninstallerScript = Join-Path $PSScriptRoot "uninstall.ps1"
if (Test-Path $uninstallerScript) {
    Copy-Item -Path $uninstallerScript -Destination $installDir -Force
}

Write-Host "  [+] Application files copied successfully." -ForegroundColor Green

# 3. Create Start Menu and Desktop Shortcuts
Write-Host "[*] Creating shortcuts..." -ForegroundColor Yellow
$exePath = Join-Path $installDir "Ghostline.exe"
$iconPath = Join-Path $installDir "ghostline.ico"

$wshShell = New-Object -ComObject WScript.Shell

# Start Menu Shortcut
$startMenuDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Ghostline"
if (-not (Test-Path $startMenuDir)) {
    New-Item -ItemType Directory -Path $startMenuDir -Force | Out-Null
}
$startMenuLnk = Join-Path $startMenuDir "Ghostline.lnk"
$shortcut = $wshShell.CreateShortcut($startMenuLnk)
$shortcut.TargetPath = $exePath
$shortcut.WorkingDirectory = $installDir
$shortcut.Description = "Ghostline — 100% Offline AI Assistant"
if (Test-Path $iconPath) {
    $shortcut.IconLocation = "$iconPath,0"
}
$shortcut.Save()
Write-Host "  [+] Start Menu shortcut created: $startMenuLnk" -ForegroundColor Green

# Desktop Shortcut
$desktopDir = [System.Environment]::GetFolderPath("Desktop")
$desktopLnk = Join-Path $desktopDir "Ghostline.lnk"
$shortcutDesk = $wshShell.CreateShortcut($desktopLnk)
$shortcutDesk.TargetPath = $exePath
$shortcutDesk.WorkingDirectory = $installDir
$shortcutDesk.Description = "Ghostline — 100% Offline AI Assistant"
if (Test-Path $iconPath) {
    $shortcutDesk.IconLocation = "$iconPath,0"
}
$shortcutDesk.Save()
Write-Host "  [+] Desktop shortcut created: $desktopLnk" -ForegroundColor Green

# 4. Register in Windows Settings / Control Panel (Add/Remove Programs)
Write-Host "[*] Registering uninstaller with Windows Settings..." -ForegroundColor Yellow
$regKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\Ghostline"
if (-not (Test-Path $regKey)) {
    New-Item -Path $regKey -Force | Out-Null
}

$uninstallCmd = "powershell.exe -ExecutionPolicy Bypass -NoProfile -File `"$installDir\uninstall.ps1`""

Set-ItemProperty -Path $regKey -Name "DisplayName" -Value "Ghostline"
Set-ItemProperty -Path $regKey -Name "DisplayVersion" -Value "1.0.0"
Set-ItemProperty -Path $regKey -Name "Publisher" -Value "Ghostline Open Source Project"
Set-ItemProperty -Path $regKey -Name "InstallLocation" -Value $installDir
Set-ItemProperty -Path $regKey -Name "DisplayIcon" -Value "$exePath,0"
Set-ItemProperty -Path $regKey -Name "UninstallString" -Value $uninstallCmd
Set-ItemProperty -Path $regKey -Name "NoModify" -Value 1 -Type DWord
Set-ItemProperty -Path $regKey -Name "NoRepair" -Value 1 -Type DWord

$totalSizeKB = [math]::Round((Get-ChildItem -Path $installDir -Recurse | Measure-Object -Property Length -Sum).Sum / 1KB)
Set-ItemProperty -Path $regKey -Name "EstimatedSize" -Value $totalSizeKB -Type DWord

Write-Host "  [+] Windows Uninstaller registered cleanly." -ForegroundColor Green

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host "  INSTALLATION SUCCESSFUL!" -ForegroundColor Green
Write-Host "  You can launch Ghostline from:" -ForegroundColor Cyan
Write-Host "  • Desktop Shortcut: Ghostline" -ForegroundColor Cyan
Write-Host "  • Start Menu -> Ghostline" -ForegroundColor Cyan
Write-Host "  • $exePath" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Green
