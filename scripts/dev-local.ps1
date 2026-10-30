[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Repo
$Portable = Join-Path $Repo "dist\portable-smoke-final\vai-local-evaluation-windows-portable"
$PostgresBin = Join-Path $Portable "runtime\postgresql\bin"
$PostgresData = Join-Path $Portable "data\postgres"
$PopplerBin = Join-Path $Portable "runtime\poppler\Library\bin"
$Python = Join-Path $Repo ".venv\Scripts\python.exe"
$DevData = Join-Path $Repo ".data\dev"
$ApiOut = Join-Path $DevData "api.log"
$ApiErr = Join-Path $DevData "api-error.log"
$ApiProcess = $null

function Assert-Exists([string]$Path, [string]$Message) {
    if (-not (Test-Path -LiteralPath $Path)) { throw $Message }
}

Assert-Exists (Join-Path $Repo ".env") "Create .env from .env.example before starting development."
Assert-Exists $Python "The repository Python environment is missing."
Assert-Exists (Join-Path $PostgresBin "pg_ctl.exe") "The bundled PostgreSQL runtime is missing. Build the Windows portable package first."
Assert-Exists (Join-Path $PopplerBin "pdftotext.exe") "The bundled PDF extraction runtime is missing. Build the Windows portable package first."
New-Item -ItemType Directory -Force -Path $DevData | Out-Null

foreach ($Port in @(8000, 3000)) {
    if (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue) {
        throw "Port $Port is already in use. Stop the existing app (Ctrl+C in its terminal) before running npm run dev."
    }
}

$env:PATH = "$PostgresBin;$PopplerBin;$env:PATH"
$env:VAI_DATABASE_URL = "postgresql+psycopg://vai@127.0.0.1:55432/vai"
$env:VAI_CORS_ORIGINS = '["http://localhost:3000"]'

& (Join-Path $PostgresBin "pg_ctl.exe") -D $PostgresData status *> $null
if ($LASTEXITCODE -ne 0) {
    if (Get-NetTCPConnection -State Listen -LocalPort 55432 -ErrorAction SilentlyContinue) {
        throw "Port 55432 is occupied by an unknown process."
    }
    & (Join-Path $PostgresBin "pg_ctl.exe") -D $PostgresData -l (Join-Path $DevData "postgres.log") -o "-h 127.0.0.1 -p 55432" start -w
    if ($LASTEXITCODE -ne 0) { throw "Bundled PostgreSQL failed to start." }
}

& $Python -m alembic -c (Join-Path $Repo "services\api\alembic.ini") upgrade head
if ($LASTEXITCODE -ne 0) { throw "Database migration failed." }

try {
    $ApiProcess = Start-Process -FilePath $Python -WindowStyle Hidden -PassThru -WorkingDirectory $Repo `
        -RedirectStandardOutput $ApiOut -RedirectStandardError $ApiErr `
        -ArgumentList @("-m", "uvicorn", "app.main:app", "--app-dir", "services/api", "--host", "127.0.0.1", "--port", "8000")

    $ApiReady = $false
    for ($attempt = 1; $attempt -le 30; $attempt++) {
        try {
            if ((Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:8000/health" -TimeoutSec 1).StatusCode -eq 200) { $ApiReady = $true; break }
        } catch {}
        if ($ApiProcess.HasExited) { break }
        Start-Sleep -Milliseconds 300
    }
    if (-not $ApiReady) {
        throw "API failed to start. Inspect .data/dev/api-error.log."
    }

    Write-Host "VAI development services are ready."
    Write-Host "Web: http://localhost:3000"
    Write-Host "API: http://localhost:8000"
    & npm.cmd --prefix $Repo run dev:web
}
finally {
    if ($ApiProcess -and -not $ApiProcess.HasExited) {
        # The Windows virtualenv launcher can own a child Python process.
        & taskkill.exe /PID $ApiProcess.Id /T /F *> $null
    }
}
