[CmdletBinding()]
param(
    [string]$PostgresRoot = "C:\Program Files\PostgreSQL\18",
    [string]$PythonCommand = "py",
    [string]$PythonVersion = "-3.13"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Output = Join-Path $Root "dist\installers"
$Staging = Join-Path ([System.IO.Path]::GetTempPath()) (
    "vai-portable-" + [System.Guid]::NewGuid().ToString("N")
)
$Bundle = Join-Path $Staging "vai-local-evaluation-windows-portable"
$Runtime = Join-Path $Bundle "runtime"
$Archive = Join-Path $Output "vai-local-evaluation-windows-portable.zip"

try {
    if (-not (Test-Path (Join-Path $PostgresRoot "bin\postgres.exe"))) {
        throw "PostgreSQL binaries were not found under $PostgresRoot."
    }
    $PythonExe = (& $PythonCommand $PythonVersion -c "import sys; print(sys.executable)").Trim()
    if (-not (Test-Path $PythonExe)) { throw "Python $PythonVersion was not found." }

    & npm run build:web
    if ($LASTEXITCODE -ne 0) { throw "The production web build failed." }

    New-Item -ItemType Directory -Force -Path $Output, $Runtime | Out-Null
    Copy-Item -Recurse -Force (Join-Path $Root "packaging\windows-portable\*") $Bundle

    $PythonRoot = Split-Path -Parent $PythonExe
    Copy-Item -Recurse -Force $PythonRoot (Join-Path $Runtime "python")
    $BundledSitePackages = Join-Path $Runtime "python\Lib\site-packages"
    if (Test-Path -LiteralPath $BundledSitePackages) {
        Remove-Item -LiteralPath $BundledSitePackages -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $BundledSitePackages | Out-Null
    & $PythonExe -m pip install --disable-pip-version-check --no-compile `
        --target $BundledSitePackages -r (Join-Path $Root "services\api\requirements.lock")
    if ($LASTEXITCODE -ne 0) { throw "Unable to install the bundled Python dependencies." }
    & $PythonExe -m pip install --disable-pip-version-check --no-compile --no-deps `
        --target $BundledSitePackages (Join-Path $Root "services\api")
    if ($LASTEXITCODE -ne 0) { throw "Unable to install the bundled API package." }

    $NodeRoot = Split-Path -Parent (Get-Command node.exe).Source
    New-Item -ItemType Directory -Force -Path (Join-Path $Runtime "node") | Out-Null
    Copy-Item -Force (Join-Path $NodeRoot "node.exe") (Join-Path $Runtime "node\node.exe")
    $NodeVersion = (& (Join-Path $NodeRoot "node.exe") --version).Trim()
    Invoke-WebRequest -UseBasicParsing `
        -Uri "https://raw.githubusercontent.com/nodejs/node/$NodeVersion/LICENSE" `
        -OutFile (Join-Path $Runtime "node\LICENSE")

    $PostgresTarget = Join-Path $Runtime "postgresql"
    New-Item -ItemType Directory -Force -Path $PostgresTarget | Out-Null
    Copy-Item -Recurse -Force (Join-Path $PostgresRoot "bin") $PostgresTarget
    Copy-Item -Recurse -Force (Join-Path $PostgresRoot "lib") $PostgresTarget
    Copy-Item -Recurse -Force (Join-Path $PostgresRoot "share") $PostgresTarget
    Copy-Item -Force (Join-Path $PostgresRoot "server_license.txt") $PostgresTarget

    $PopplerZip = Join-Path $Staging "poppler.zip"
    Invoke-WebRequest -UseBasicParsing `
        -Uri "https://github.com/oschwartz10612/poppler-windows/releases/download/v26.09.0-0/Release-26.09.0-0.zip" `
        -OutFile $PopplerZip
    $PopplerExtract = Join-Path $Staging "poppler-extract"
    Expand-Archive -LiteralPath $PopplerZip -DestinationPath $PopplerExtract
    $PopplerRoot = Get-ChildItem -Path $PopplerExtract -Directory | Where-Object {
        Test-Path (Join-Path $_.FullName "Library\bin\pdftotext.exe")
    } | Select-Object -First 1
    if (-not $PopplerRoot) { throw "The Poppler archive did not contain pdftotext.exe." }
    New-Item -ItemType Directory -Force -Path (Join-Path $Runtime "poppler") | Out-Null
    Copy-Item -Recurse -Force (Join-Path $PopplerRoot.FullName "*") (Join-Path $Runtime "poppler")

    $ApiTarget = Join-Path $Bundle "app\api"
    New-Item -ItemType Directory -Force -Path $ApiTarget | Out-Null
    Copy-Item -Recurse -Force (Join-Path $Root "services\api\alembic") $ApiTarget
    Copy-Item -Recurse -Force (Join-Path $Root "services\api\app") $ApiTarget
    Copy-Item -Force (Join-Path $Root "services\api\alembic.ini") $ApiTarget

    $WebTarget = Join-Path $Bundle "app\web"
    New-Item -ItemType Directory -Force -Path $WebTarget | Out-Null
    Copy-Item -Recurse -Force (Join-Path $Root "apps\web\.next\standalone\*") $WebTarget
    $StaticTarget = Join-Path $WebTarget "apps\web\.next\static"
    New-Item -ItemType Directory -Force -Path $StaticTarget | Out-Null
    Copy-Item -Recurse -Force (Join-Path $Root "apps\web\.next\static\*") $StaticTarget

    New-Item -ItemType Directory -Force -Path `
        (Join-Path $Bundle "data"), (Join-Path $Bundle "logs"), (Join-Path $Bundle "state") | Out-Null

    Remove-Item -LiteralPath $Archive -Force -ErrorAction SilentlyContinue
    Compress-Archive -Path $Bundle -DestinationPath $Archive -CompressionLevel Optimal
    $Hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $Archive).Hash.ToLowerInvariant()
    Set-Content -LiteralPath (Join-Path $Output "WINDOWS_PORTABLE_SHA256.txt") `
        -Value "$Hash *$(Split-Path -Leaf $Archive)" -Encoding ascii
    Write-Host "Created $Archive"
}
finally {
    if (Test-Path -LiteralPath $Staging) {
        Remove-Item -LiteralPath $Staging -Recurse -Force
    }
}
