[CmdletBinding()]
param(
    [switch]$Stop,
    [switch]$ResetData,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$ComposeFile = Join-Path $Root "compose.installer.yml"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker Desktop is required. Install it, start it, then run this installer again."
}

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Docker Desktop is installed but not running. Start Docker Desktop and try again."
}

if ($Stop -or $ResetData) {
    $Arguments = @("compose", "-f", $ComposeFile, "down")
    if ($ResetData) { $Arguments += "--volumes" }
    & docker @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Unable to stop the VAI application." }
    if ($Stop -and -not $ResetData) { Write-Host "VAI stopped. Local data was preserved."; exit 0 }
    if ($ResetData) { Write-Host "VAI stopped and local database/evidence volumes were removed."; exit 0 }
}

Write-Host "Building and starting VAI. The first installation can take several minutes..."
& docker compose -f $ComposeFile up -d --build
if ($LASTEXITCODE -ne 0) { throw "VAI installation failed. Run 'docker compose -f compose.installer.yml logs' for details." }

Write-Host "Waiting for the API health check..."
for ($Attempt = 1; $Attempt -le 60; $Attempt++) {
    try {
        $Health = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 2
        if ($Health.status -eq "ok") { break }
    } catch { Start-Sleep -Seconds 2 }
}
if ($Health.status -ne "ok") { throw "VAI started but did not become healthy. Inspect the Docker Desktop logs." }

Write-Host "VAI is ready at http://localhost:3000"
Write-Host "This package is for local evaluation and usability testing, not production deployment."
if (-not $NoBrowser) { Start-Process "http://localhost:3000" }
