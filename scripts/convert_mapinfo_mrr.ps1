param(
    [Parameter(Mandatory = $true)]
    [string]$InputPath,
    [Parameter(Mandatory = $true)]
    [string]$OutputPath,
    [string]$MapInfoProDir = $env:MULTIPLANNER_MAPINFO_PRO_DIR
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ([string]::IsNullOrWhiteSpace($MapInfoProDir)) {
    $MapInfoProDir = "C:\Program Files\InfoVista\Planet 25.0\mapinfo\Professional"
}

$source = (Resolve-Path -LiteralPath $InputPath).Path
$target = [IO.Path]::GetFullPath($OutputPath)
if ([IO.Path]::GetExtension($target) -ne ".mrr") {
    throw "OutputPath must use the .mrr extension: $target"
}
if (Test-Path -LiteralPath $target) {
    throw "Output already exists: $target"
}

$rasterDir = Join-Path $MapInfoProDir "Raster"
$env:PATH = "$MapInfoProDir;$rasterDir;$env:PATH"
@(
    "MapInfo.RasterEngine.Common.dll",
    "MapInfo.RasterEngine.IO.dll",
    "MapInfo.RasterEngine.Operations.dll"
) | ForEach-Object {
    [void][Reflection.Assembly]::LoadFrom((Join-Path $rasterDir $_))
}

$driver = [MapInfo.RasterEngine.IO.DriverIDExtensions]::GetString(
    [MapInfo.RasterEngine.IO.DriverID]::MRR
)
[MapInfo.RasterEngine.Operations.RasterProcessing]::Convert($source, $target, $driver)

$created = Get-Item -LiteralPath $target
if ($created.Length -eq 0) {
    throw "MapInfo created an empty MRR: $target"
}
Write-Output $created.FullName
