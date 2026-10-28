[CmdletBinding()]
param(
    [string]$PostgresBin = "dist/portable-smoke-final/vai-local-evaluation-windows-portable/runtime/postgresql/bin",
    [int]$Port = 55441,
    [string]$DowngradeTarget = "0026_boq_activity_allocations",
    [switch]$RunLoadProbe,
    [string]$EvidenceDirectory = ""
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
$RuntimePath = if ([IO.Path]::IsPathRooted($PostgresBin)) { $PostgresBin } else { Join-Path $Repo $PostgresBin }
$Runtime = (Resolve-Path -LiteralPath $RuntimePath).Path
$Scratch = Join-Path $Repo (".test-tmp/pg-remediation-" + [guid]::NewGuid().ToString("N"))
if ($EvidenceDirectory) {
    $Scratch = [IO.Path]::GetFullPath($EvidenceDirectory)
    $AllowedEvidenceRoot = [IO.Path]::GetFullPath((Join-Path $Repo '.test-tmp')) + [IO.Path]::DirectorySeparatorChar
    if (-not $Scratch.StartsWith($AllowedEvidenceRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'EvidenceDirectory must be a new directory inside the repository .test-tmp directory'
    }
    if (Test-Path -LiteralPath $Scratch) { throw 'EvidenceDirectory must not already exist' }
}
$Cluster = Join-Path $Scratch "data"
$Python = Join-Path $Repo ".venv/Scripts/python.exe"
$PreviousDatabase = $env:VAI_DATABASE_URL
$PreviousTestDatabase = $env:VAI_TEST_POSTGRES_URL
$PreviousPostgresBin = $env:VAI_TEST_POSTGRES_BIN
$PreviousLoadProfile = $env:VAI_TEST_LOAD_PROFILE
$Started = $false
New-Item -ItemType Directory -Path $Scratch -Force | Out-Null

function Assert-NativeSuccess([string]$Step) {
    if ($LASTEXITCODE -ne 0) { throw "$Step failed with exit code $LASTEXITCODE" }
}

Push-Location $Repo
try {
    & (Join-Path $Runtime "initdb.exe") -D $Cluster -U vai -A trust --encoding=UTF8 --locale=C
    Assert-NativeSuccess "Initialize isolated PostgreSQL"
    # Wait for pg_ctl itself, not its persistent postgres descendants or inherited pipes.
    $Start = Start-Process -FilePath (Join-Path $Runtime "pg_ctl.exe") -WindowStyle Hidden -PassThru -ArgumentList @('-D', ('"' + $Cluster + '"'), '-l', ('"' + (Join-Path $Scratch "postgres.log") + '"'), '-o', ('"-h 127.0.0.1 -p ' + $Port + '"'), 'start', '-w') -RedirectStandardOutput (Join-Path $Scratch "start.stdout.log") -RedirectStandardError (Join-Path $Scratch "start.stderr.log")
    # Windows PowerShell can lose the exit code after the process handle closes.
    $null = $Start.Handle
    $StartFinished = $Start.WaitForExit(30000)
    $Start.Refresh()
    if (-not $StartFinished -or $Start.ExitCode -ne 0) {
        & (Join-Path $Runtime "pg_ctl.exe") -D $Cluster stop -m fast -w
        throw "Start isolated PostgreSQL failed; inspect $Scratch/start.*.log"
    }
    $Started = $true
    & (Join-Path $Runtime "createdb.exe") -h 127.0.0.1 -p $Port -U vai vai_remediation
    Assert-NativeSuccess "Create isolated database"
    $env:VAI_DATABASE_URL = "postgresql+psycopg://vai@127.0.0.1:$Port/vai_remediation"
    $env:VAI_TEST_POSTGRES_URL = $env:VAI_DATABASE_URL
    $env:VAI_TEST_POSTGRES_BIN = $Runtime
    $env:VAI_TEST_LOAD_PROFILE = if ($RunLoadProbe) { "1" } else { "0" }
    & $Python -m alembic -c services/api/alembic.ini upgrade head
    Assert-NativeSuccess "Upgrade to head"
    & $Python -m alembic -c services/api/alembic.ini downgrade $DowngradeTarget
    Assert-NativeSuccess "Downgrade requested revision"
    & $Python -m alembic -c services/api/alembic.ini upgrade head
    Assert-NativeSuccess "Re-upgrade to head"
    & $Python -m pytest services/api/tests/integration/test_project_context_postgres.py --basetemp (Join-Path $Scratch "pytest") -o "cache_dir=$Scratch/cache" --junitxml (Join-Path $Scratch 'pytest.xml') --tb=short
    Assert-NativeSuccess "Migrated API and append-only behavior"
    Write-Host "Rehearsal passed. Isolated cluster and log: $Scratch"
}
finally {
    if ($Started) { & (Join-Path $Runtime "pg_ctl.exe") -D $Cluster stop -m fast -w }
    $env:VAI_DATABASE_URL = $PreviousDatabase
    $env:VAI_TEST_POSTGRES_URL = $PreviousTestDatabase
    $env:VAI_TEST_POSTGRES_BIN = $PreviousPostgresBin
    $env:VAI_TEST_LOAD_PROFILE = $PreviousLoadProfile
    Pop-Location
}
