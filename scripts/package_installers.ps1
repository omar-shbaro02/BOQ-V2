[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$OutputDirectory = Join-Path $Root "dist\installers"
$StagingDirectory = Join-Path ([System.IO.Path]::GetTempPath()) (
    "vai-installer-" + [System.Guid]::NewGuid().ToString("N")
)
$BundleDirectory = Join-Path $StagingDirectory "vai-local-evaluation"
$SourceArchive = Join-Path $StagingDirectory "source.tar"
$WindowsArchive = Join-Path $OutputDirectory "vai-local-evaluation-windows.zip"
$LinuxArchive = Join-Path $OutputDirectory "vai-local-evaluation-linux.tar.gz"
$ChecksumFile = Join-Path $OutputDirectory "SHA256SUMS.txt"

try {
    New-Item -ItemType Directory -Force -Path $OutputDirectory, $BundleDirectory | Out-Null

    & tar -cf $SourceArchive `
        --exclude=.git `
        --exclude=.venv `
        --exclude=node_modules `
        --exclude=.next `
        --exclude=dist `
        --exclude=.data `
        --exclude=.pytest_cache `
        --exclude=.ruff_cache `
        --exclude=__pycache__ `
        -C $Root .
    if ($LASTEXITCODE -ne 0) { throw "Unable to stage the installer source tree." }

    & tar -xf $SourceArchive -C $BundleDirectory
    if ($LASTEXITCODE -ne 0) { throw "Unable to extract the staged installer source tree." }

    Remove-Item -LiteralPath $WindowsArchive, $LinuxArchive, $ChecksumFile `
        -Force -ErrorAction SilentlyContinue
    Compress-Archive -Path $BundleDirectory -DestinationPath $WindowsArchive -CompressionLevel Optimal
    & tar -czf $LinuxArchive -C $StagingDirectory "vai-local-evaluation"
    if ($LASTEXITCODE -ne 0) { throw "Unable to create the Linux installer archive." }

    $Checksums = @($LinuxArchive, $WindowsArchive) | ForEach-Object {
        $Hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $_).Hash.ToLowerInvariant()
        "$Hash *$(Split-Path -Leaf $_)"
    }
    Set-Content -LiteralPath $ChecksumFile -Value $Checksums -Encoding ascii

    Write-Host "Created:"
    Write-Host "  $LinuxArchive"
    Write-Host "  $WindowsArchive"
    Write-Host "  $ChecksumFile"
}
finally {
    if (Test-Path -LiteralPath $StagingDirectory) {
        Remove-Item -LiteralPath $StagingDirectory -Recurse -Force
    }
}
