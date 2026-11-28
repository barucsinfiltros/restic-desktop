# Build the Windows onedir distribution using the project's pinned requirements.
$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $project
try {
    $python = Join-Path $project 'env\Scripts\python.exe'
    if (!(Test-Path -LiteralPath $python)) {
        throw 'Create env and install requirements.txt before building.'
    }
    & $python -m PyInstaller --noconfirm --clean restic_manager.spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed ($LASTEXITCODE)." }
    $bundle = Join-Path $project 'dist\ResticDesktop'
    $version = & (Join-Path $bundle '_internal\restic\windows\restic.exe') version
    if ($LASTEXITCODE -ne 0 -or $version -notmatch '^restic ') {
        throw 'The bundled Restic did not report its version.'
    }
    Write-Output $version
    Write-Output (Join-Path $bundle 'ResticDesktop.exe')
} finally {
    Pop-Location
}
