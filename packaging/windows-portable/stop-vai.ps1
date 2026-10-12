[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$State = Join-Path $Root "state"

foreach ($Name in @("api", "web")) {
    $PidFile = Join-Path $State "$Name.pid"
    if (-not (Test-Path -LiteralPath $PidFile)) { continue }
    $ProcessId = [int](Get-Content -LiteralPath $PidFile -Raw)
    $Process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if ($Process -and $Process.Path -like "$Root\runtime\*") {
        Stop-Process -Id $ProcessId -Force
        [void]$Process.WaitForExit(10000)
    }
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
}

$PgCtl = Join-Path $Root "runtime\postgresql\bin\pg_ctl.exe"
$PostgresData = Join-Path $Root "data\postgres"
if (Test-Path (Join-Path $PostgresData "postmaster.pid")) {
    & $PgCtl -D $PostgresData stop -m fast -w
    if ($LASTEXITCODE -ne 0) { throw "Unable to stop the bundled PostgreSQL database." }
}

Write-Host "VAI stopped. Local data was preserved."
