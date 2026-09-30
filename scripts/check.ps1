<#
Runs every automated check for KaushalSetu and prints a summary.

Usage (from the repository root, in PowerShell):
    powershell -ExecutionPolicy Bypass -File scripts\check.ps1

Before running:
  - Database container running:   docker compose up -d db
  - Migrations applied:           (in backend\) .\.venv\Scripts\alembic.exe upgrade head
  - Optional, for the full browser test: backend running on port 8000.
    Without it, one Playwright test is skipped (not failed).
#>

$ErrorActionPreference = "Continue"
$repo = Split-Path -Parent $PSScriptRoot
$results = [System.Collections.Generic.List[object]]::new()

function Invoke-Check([string]$Name, [string]$Folder, [scriptblock]$Command) {
    Write-Host ""
    Write-Host "=== $Name ===" -ForegroundColor Cyan
    Push-Location (Join-Path $repo $Folder)
    try {
        & $Command
        $ok = ($LASTEXITCODE -eq 0)
    } finally {
        Pop-Location
    }
    $results.Add([pscustomobject]@{ Check = $Name; Result = $(if ($ok) { "PASS" } else { "FAIL" }) })
}

$py = ".\.venv\Scripts\python.exe"

Invoke-Check "Database container" "." {
    $id = docker compose ps --status running --quiet db
    if (-not $id) {
        Write-Host "db container is not running. Start it with: docker compose up -d db"
        $global:LASTEXITCODE = 1
    }
}
Invoke-Check "Configuration (config/*.yaml)" "backend" { & $py -m app.config }
Invoke-Check "Synthetic data export (planted patterns)" "backend" { & $py -m app.cli.synthetic validate --source export }
Invoke-Check "Backend lint (ruff)"      "backend"  { & $py -m ruff check . }
Invoke-Check "Backend format (black)"   "backend"  { & $py -m black --check . }
Invoke-Check "Backend tests (pytest)"   "backend"  { & $py -m pytest }
Invoke-Check "Frontend lint (oxlint)"   "frontend" { npm run lint }
Invoke-Check "Frontend format"          "frontend" { npm run format:check }
Invoke-Check "Frontend build"           "frontend" { npm run build }
Invoke-Check "Frontend e2e (Playwright)" "frontend" { npm run test:e2e }

Write-Host ""
Write-Host "=== Summary ===" -ForegroundColor Cyan
$results | Format-Table -AutoSize | Out-String | Write-Host
if ($results.Result -contains "FAIL") { exit 1 } else { exit 0 }
