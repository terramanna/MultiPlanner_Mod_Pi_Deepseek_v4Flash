param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

Push-Location $repoRoot
try {
    $existingRaw = & git config --get core.hooksPath
    $existing = if ($LASTEXITCODE -eq 0 -and $null -ne $existingRaw) { $existingRaw.Trim() } else { "" }
    if ($existing -and $existing -ne ".githooks" -and -not $Force) {
        throw "Refusing to overwrite existing core.hooksPath '$existing'. Re-run with -Force to use .githooks."
    }
    & git config core.hooksPath .githooks
    if ($LASTEXITCODE -ne 0) {
        throw "git config core.hooksPath .githooks failed"
    }
    Write-Host "Configured git hooksPath -> .githooks" -ForegroundColor Green
}
finally {
    Pop-Location
}
