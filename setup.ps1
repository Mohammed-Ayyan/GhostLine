# Ghostline Automated Setup & Environment Verification Script
# Target: Windows 11 PC (NVIDIA RTX 4050 6GB VRAM, 16GB RAM)

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Ghostline Automated Setup & Verification" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Verify Python Installation
Write-Host "`n[1/5] Checking Python runtime..." -ForegroundColor Yellow
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Error "Python 3.10+ is required but was not found in PATH."
    exit 1
}
$pyVer = python --version
Write-Host "  [+] Found $pyVer at $($python.Source)" -ForegroundColor Green

# 2. Verify / Install Dependencies
Write-Host "`n[2/5] Verifying Python package dependencies..." -ForegroundColor Yellow
$reqPath = Join-Path $PSScriptRoot "requirements.txt"
python -m pip install -r $reqPath --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Failed to install some dependencies. Ensure pip is updated."
} else {
    Write-Host "  [+] Dependencies verified (Pillow, OpenCV, PyWin32, Pydantic, Requests, Pystray)." -ForegroundColor Green
}

# 3. Verify Ollama & Local Model Availability
Write-Host "`n[3/5] Verifying local Ollama service & models..." -ForegroundColor Yellow
$ollama = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollama) {
    Write-Warning "Ollama CLI was not found in PATH. Install Ollama from https://ollama.com."
} else {
    Write-Host "  [+] Found Ollama CLI at $($ollama.Source)" -ForegroundColor Green
    try {
        $tags = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 3 -ErrorAction Stop
        $modelNames = $tags.models.name
        Write-Host "  [+] Ollama daemon is running." -ForegroundColor Green
        Write-Host "  [+] Available local models: $($modelNames -join ', ')" -ForegroundColor Cyan
        
        if ($modelNames -notcontains "phi3:mini" -and $modelNames -notmatch "phi3") {
            Write-Host "  [*] Pulling phi3:mini for high-accuracy reasoning..." -ForegroundColor Yellow
            ollama pull phi3:mini
        }
    } catch {
        Write-Warning "Ollama service is not currently running. Please start Ollama before launching Ghostline."
    }
}

# 4. Verify Windows OCR Engine Binary
Write-Host "`n[4/5] Verifying Windows native OCR engine binary..." -ForegroundColor Yellow
$ocrBin = Join-Path $PSScriptRoot "bin\win_ocr.exe"
if (Test-Path $ocrBin) {
    Write-Host "  [+] Windows Native OCR binary is present ($ocrBin)." -ForegroundColor Green
} else {
    Write-Host "  [*] Compiling native Windows OCR wrapper using csc.exe..." -ForegroundColor Yellow
    $csc = "$env:windir\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
    $framework = "$env:windir\Microsoft.NET\Framework64\v4.0.30319"
    $src = Join-Path $PSScriptRoot "bin\src\WinOcr.cs"
    $winmdCandidates = @(
        "$env:windir\System32\WinMetadata\Windows.winmd",
        "${env:ProgramFiles(x86)}\Windows Kits\10\UnionMetadata\Windows.winmd",
        "$env:windir\Lenovo\ImController\PluginHost\Windows.winmd"
    )
    $winmd = $winmdCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    New-Item -ItemType Directory -Path (Split-Path $ocrBin) -Force | Out-Null
    if ($winmd -and (Test-Path $csc) -and (Test-Path $src)) {
        & $csc /target:exe /out:$ocrBin /r:"$framework\System.Runtime.dll" /r:"$framework\System.Runtime.WindowsRuntime.dll" /r:"$framework\System.Threading.Tasks.dll" /r:$winmd $src
    }
    if (Test-Path $ocrBin) {
        Write-Host "  [+] Compiled $ocrBin successfully." -ForegroundColor Green
    } else {
        Write-Error "Failed to compile win_ocr.exe."
        exit 1
    }
}

# 5. Run Verification Regression Test Suite
Write-Host "`n[5/5] Running automated offline verification suite..." -ForegroundColor Yellow
$testRunner = Join-Path $PSScriptRoot "tests\run_all_tests.py"
python $testRunner

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n==========================================================" -ForegroundColor Green
    Write-Host "  SETUP COMPLETE: Ghostline is ready to run!" -ForegroundColor Green
    Write-Host "  Launch with: .\run.bat or .\run.ps1" -ForegroundColor Cyan
    Write-Host "==========================================================" -ForegroundColor Green
} else {
    Write-Warning "Some verification tests failed. Review the log above."
}
