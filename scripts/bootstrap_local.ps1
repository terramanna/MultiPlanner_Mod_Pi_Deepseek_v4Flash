param(
    [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$VenvPath = Join-Path $RepoRoot ".venv"
$VenvPython = Join-Path $VenvPath "Scripts\python.exe"
$ApiPath = Join-Path $RepoRoot "apps\api"
$WebPath = Join-Path $RepoRoot "apps\web"
$LocalNodeDir = Join-Path $VenvPath "tools\node"
$LocalNode = Join-Path $LocalNodeDir "node.exe"

function Invoke-Checked {
    param(
        [string]$Description,
        [string]$Executable,
        [string[]]$Arguments
    )
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Description failed with exit code $LASTEXITCODE."
    }
}

Write-Host "Repo root: $RepoRoot"

if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating virtual environment at $VenvPath"
    & $PythonExe -m venv $VenvPath
}

Write-Host "Upgrading pip"
Invoke-Checked "pip upgrade" $VenvPython @("-m", "pip", "install", "--use-feature=truststore", "--upgrade", "pip")

Write-Host "Installing API dependencies"
Invoke-Checked "API dependency install" $VenvPython @(
    "-m", "pip", "install", "--use-feature=truststore", "-e", $ApiPath, "pytest", "httpx"
)

if (Test-Path (Join-Path $WebPath "package.json")) {
    $NodeCommand = Get-Command node -CommandType Application -ErrorAction Stop
    Write-Host "Installing frontend dependencies"
    Push-Location $WebPath
    try {
        Invoke-Checked "frontend dependency install" "npm" @("install")
    }
    finally {
        Pop-Location
    }

    Write-Host "Installing project-local Node runtime"
    New-Item -ItemType Directory -Force -Path $LocalNodeDir | Out-Null
    Copy-Item -LiteralPath $NodeCommand.Source -Destination $LocalNode -Force
}

Write-Host ""
Write-Host "Bootstrap complete."
Write-Host "Activate the environment with:"
Write-Host "  .\.venv\Scripts\Activate.ps1"
