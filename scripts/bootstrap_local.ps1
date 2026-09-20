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

function Assert-Python311 {
    param(
        [string]$Executable,
        [string]$Purpose
    )
    $Version = & $Executable -c "import sys; print('.'.join(map(str, sys.version_info[:3])))"
    if ($LASTEXITCODE -ne 0) {
        throw "Could not determine the version of $Purpose at '$Executable'."
    }
    if (-not $Version.Trim().StartsWith("3.11.")) {
        throw "$Purpose must use Python 3.11.x; found $($Version.Trim())."
    }
    Write-Host "${Purpose}: Python $($Version.Trim())"
}

Write-Host "Repo root: $RepoRoot"
Assert-Python311 $PythonExe "Selected Python"

if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating virtual environment at $VenvPath"
    & $PythonExe -m venv $VenvPath
}

Assert-Python311 $VenvPython "Virtual environment"

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
