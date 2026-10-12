[CmdletBinding()]
param([switch]$NoBrowser)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Runtime = Join-Path $Root "runtime"
$Data = Join-Path $Root "data"
$Logs = Join-Path $Root "logs"
$State = Join-Path $Root "state"
$PostgresData = Join-Path $Data "postgres"
$EvidenceData = Join-Path $Data "evidence"
$Python = Join-Path $Runtime "python\python.exe"
$Node = Join-Path $Runtime "node\node.exe"
$PostgresBin = Join-Path $Runtime "postgresql\bin"
$PopplerBin = Join-Path $Runtime "poppler\Library\bin"
$ApiLog = Join-Path $Logs "api.log"
$ApiErrorLog = Join-Path $Logs "api-error.log"
$WebLog = Join-Path $Logs "web.log"
$WebErrorLog = Join-Path $Logs "web-error.log"

New-Item -ItemType Directory -Force -Path $Data, $Logs, $State, $EvidenceData | Out-Null

function Assert-PortAvailable([int]$Port) {
    if (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue) {
        throw "Port $Port is already in use. Stop the conflicting application and try again."
    }
}

function Test-HttpReady([string]$Uri) {
    try {
        $Response = Invoke-WebRequest -UseBasicParsing -Uri $Uri -TimeoutSec 2
        return $Response.StatusCode -eq 200
    }
    catch { return $false }
}

if (Test-HttpReady "http://127.0.0.1:8000/health" -and `
    (Test-HttpReady "http://127.0.0.1:3000/")) {
    Write-Host "VAI is already running at http://localhost:3000"
    if (-not $NoBrowser) { Start-Process "http://localhost:3000" }
    exit 0
}

Assert-PortAvailable 8000
Assert-PortAvailable 3000

$env:PATH = "$PostgresBin;$PopplerBin;$(Join-Path $Runtime 'node');$(Join-Path $Runtime 'python');$env:PATH"
$env:VAI_ENVIRONMENT = "development"
$env:VAI_DATABASE_URL = "postgresql+psycopg://vai@127.0.0.1:55432/vai"
$env:VAI_CORS_ORIGINS = '["http://localhost:3000"]'
$env:VAI_EVIDENCE_STORAGE_BACKEND = "local"
$env:VAI_EVIDENCE_STORAGE_PATH = $EvidenceData
$env:NEXT_PUBLIC_VAI_API_URL = "http://localhost:8000"
$env:HOSTNAME = "127.0.0.1"
$env:PORT = "3000"

if (-not (Test-Path (Join-Path $PostgresData "PG_VERSION"))) {
    Write-Host "Initializing the bundled PostgreSQL database..."
    & (Join-Path $PostgresBin "initdb.exe") -D $PostgresData -U vai --encoding=UTF8 --auth=trust
    if ($LASTEXITCODE -ne 0) { throw "PostgreSQL initialization failed." }
}

$PostgresRunning = $false
& (Join-Path $PostgresBin "pg_ctl.exe") -D $PostgresData status *> $null
$PostgresRunning = $LASTEXITCODE -eq 0
if (-not $PostgresRunning) {
    Assert-PortAvailable 55432
    Write-Host "Starting the bundled PostgreSQL database..."
    & (Join-Path $PostgresBin "pg_ctl.exe") -D $PostgresData -l (Join-Path $Logs "postgres.log") `
        -o "-h 127.0.0.1 -p 55432" start -w
    if ($LASTEXITCODE -ne 0) { throw "PostgreSQL did not start." }
}

$DatabaseExists = & (Join-Path $PostgresBin "psql.exe") -h 127.0.0.1 -p 55432 -U vai `
    -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='vai'"
if (("$DatabaseExists").Trim() -ne "1") {
    & (Join-Path $PostgresBin "createdb.exe") -h 127.0.0.1 -p 55432 -U vai vai
    if ($LASTEXITCODE -ne 0) { throw "Unable to create the VAI database." }
}

Write-Host "Applying database migrations..."
& $Python -m alembic -c (Join-Path $Root "app\api\alembic.ini") upgrade head
if ($LASTEXITCODE -ne 0) { throw "Database migration failed." }

$ApiProcess = Start-Process -FilePath $Python -WindowStyle Hidden -PassThru `
    -WorkingDirectory $Root -RedirectStandardOutput $ApiLog -RedirectStandardError $ApiErrorLog `
    -ArgumentList @("-m", "uvicorn", "app.main:app", "--app-dir", "app/api", "--host", "127.0.0.1", "--port", "8000")
$ApiProcess.Id | Set-Content -LiteralPath (Join-Path $State "api.pid") -Encoding ascii

$WebProcess = Start-Process -FilePath $Node -WindowStyle Hidden -PassThru `
    -WorkingDirectory $Root -RedirectStandardOutput $WebLog -RedirectStandardError $WebErrorLog `
    -ArgumentList @("app/web/apps/web/server.js")
$WebProcess.Id | Set-Content -LiteralPath (Join-Path $State "web.pid") -Encoding ascii

for ($Attempt = 1; $Attempt -le 60; $Attempt++) {
    if ((Test-HttpReady "http://127.0.0.1:8000/health") -and `
        (Test-HttpReady "http://127.0.0.1:3000/")) { break }
    Start-Sleep -Seconds 2
}
if (-not (Test-HttpReady "http://127.0.0.1:8000/health") -or `
    -not (Test-HttpReady "http://127.0.0.1:3000/")) {
    throw "VAI did not become healthy. Inspect the files in the logs folder."
}

Write-Host "VAI is ready at http://localhost:3000"
Write-Host "Use 'Stop VAI.cmd' before moving or deleting this folder."
if (-not $NoBrowser) { Start-Process "http://localhost:3000" }
