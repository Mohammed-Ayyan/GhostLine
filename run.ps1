param(
    [switch]$Dev
)

# PowerShell launcher for Ghostline
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

if ($Dev) {
    Write-Host "========================================================" -ForegroundColor Cyan
    Write-Host "  Ghostline Developer Console (Interactive)" -ForegroundColor Cyan
    Write-Host "  Trigger Hotkey: Alt + /   |   Real-time Logging Active" -ForegroundColor Yellow
    Write-Host "========================================================" -ForegroundColor Cyan
    python ghostline\app.py
} else {
    Write-Host "[*] Launching Ghostline in background (Console Hidden)..." -ForegroundColor Cyan
    Start-Process -FilePath "pythonw.exe" -ArgumentList "ghostline\app.py" -WindowStyle Hidden
}
