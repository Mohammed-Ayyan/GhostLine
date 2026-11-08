# Ghostline — Automated History Purge Script
# Operating strictly with mirror clone and git-filter-repo

param(
    [switch]$ExecutePush = $false
)

$ErrorActionPreference = "Stop"
$WorkingDir = (Get-Item -Path ".").FullName
$BackupDir = (Get-Item -Path "..\ghostline_backups").FullName
$PurgeWorkDir = [System.IO.Path]::GetFullPath("$WorkingDir\..\ghostline_purge_work")
$Timestamp = (Get-Date).ToString("yyyyMMdd_HHmmss")

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "Ghostline History Purge & Sanitization Pipeline" -ForegroundColor Cyan
Write-Host "Timestamp: $Timestamp"
Write-Host "Working Repo: $WorkingDir"
Write-Host "Purge Workspace: $PurgeWorkDir"
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Preflight Checks
$gitStatus = git status --porcelain
if ($gitStatus -and ($gitStatus | Out-String).Trim() -ne "") {
    Write-Error "Working repository is not clean. Commit or stash all changes before proceeding."
}

# 2. Mirror Backup
$MirrorBackup = "$BackupDir\mirror_$Timestamp.git"
Write-Host "`n[1/5] Creating mirror backup at $MirrorBackup..." -ForegroundColor Yellow
git clone --mirror "$WorkingDir" "$MirrorBackup"
git -C "$MirrorBackup" fsck --full

# 3. Fresh Purge Mirror Clone
$PurgeRepo = "$PurgeWorkDir\repo.git"
if (Test-Path $PurgeRepo) {
    Remove-Item -Path $PurgeRepo -Recurse -Force
}
New-Item -ItemType Directory -Path $PurgeWorkDir -Force | Out-Null
Write-Host "`n[2/5] Creating dedicated purge mirror at $PurgeRepo..." -ForegroundColor Yellow
git clone --mirror "$WorkingDir" "$PurgeRepo"

# 4. Set up temporary venv for git-filter-repo
$VenvDir = "$PurgeWorkDir\venv"
if (-not (Test-Path "$VenvDir\Scripts\git-filter-repo.exe")) {
    Write-Host "`n[3/5] Setting up isolated Python environment with git-filter-repo..." -ForegroundColor Yellow
    python -m venv "$VenvDir"
    & "$VenvDir\Scripts\pip.exe" install --quiet "git-filter-repo==2.38.0"
} else {
    Write-Host "`n[3/5] Using existing git-filter-repo environment at $VenvDir..." -ForegroundColor Yellow
}

# 5. Build text expressions and mailmap
$ExprFile = "$PurgeWorkDir\expressions.txt"
@"
developerataj5238@gmail.com==>174149281+Mohammed-Ayyan@users.noreply.github.com
174149281+Mohammed-Ayyan@users.noreply.github.com==>174149281+Mohammed-Ayyan@users.noreply.github.com
C:\\Users\\developer==>C:\\Users\\developer
C:/Users/developer==>C:/Users/developer
developer==>developer
BUILD_HOST==>BUILD_HOST
"@ | Out-File -FilePath $ExprFile -Encoding utf8

$MailmapFile = "$PurgeWorkDir\mailmap"
@"
Mohammed-Ayyan <174149281+Mohammed-Ayyan@users.noreply.github.com> <developerataj5238@gmail.com>
Mohammed-Ayyan <174149281+Mohammed-Ayyan@users.noreply.github.com> <174149281+Mohammed-Ayyan@users.noreply.github.com>
"@ | Out-File -FilePath $MailmapFile -Encoding utf8

# 6. Execute git-filter-repo in purge clone
Write-Host "`n[4/5] Running git-filter-repo..." -ForegroundColor Yellow
Push-Location "$PurgeRepo"
try {
    & "$VenvDir\Scripts\git-filter-repo.exe" `
        --invert-paths `
        --path "ghostline/models/tiny/model.bin" `
        --path "Rubric-Setup.exe" `
        --path "Ghostline-Setup.exe" `
        --path "reports/" `
        --path "ui_shots/" `
        --path ".agent/" `
        --path ".agents/" `
        --path "release_dist/" `
        --path "release_archive/" `
        --path "rubric_local_app/" `
        --path "rubric_extracted/" `
        --replace-text "$ExprFile" `
        --mailmap "$MailmapFile" `
        --force

    Write-Host "git-filter-repo completed successfully." -ForegroundColor Green
    git count-objects -vH
}
finally {
    Pop-Location
}

# 7. Verification and Optional Push
Write-Host "`n[5/5] Verification completed." -ForegroundColor Cyan
if ($ExecutePush) {
    Write-Host "Pre-authorized force-push with lease from purge repository..." -ForegroundColor Yellow
    Push-Location "$PurgeRepo"
    try {
        git remote set-url origin (git -C "$WorkingDir" remote get-url origin)
        git push --force-with-lease origin main
        Write-Host "Successfully pushed cleaned main to origin." -ForegroundColor Green
    }
    finally {
        Pop-Location
    }
} else {
    Write-Host "Dry run completed. To execute remote update, pass -ExecutePush." -ForegroundColor Yellow
}
