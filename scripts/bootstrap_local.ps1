param(
    [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$VenvPath = Join-Path $RepoRoot ".venv"
$VenvPython = Join-Path $VenvPath "Scripts\python.exe"
$ApiPath = Join-Path $RepoRoot "apps\api"
$WebPath = Join-Path $RepoRoot "apps\web"

Write-Host "Repo root: $RepoRoot"

if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating virtual environment at $VenvPath"
    & $PythonExe -m venv $VenvPath
}

Write-Host "Upgrading pip"
& $VenvPython -m pip install --upgrade pip

Write-Host "Installing API dependencies"
& $VenvPython -m pip install -e $ApiPath pytest httpx

if (Test-Path (Join-Path $WebPath "package.json")) {
    Write-Host "Installing frontend dependencies"
    Push-Location $WebPath
    try {
        npm install
    }
    finally {
        Pop-Location
    }
}

Write-Host ""
Write-Host "Bootstrap complete."
Write-Host "Activate the environment with:"
Write-Host "  .\.venv\Scripts\Activate.ps1"
