param(
    [Parameter(Mandatory = $true)]
    [string]$InputPath,
    [Parameter(Mandatory = $true)]
    [string]$OutputPath,
    [Parameter(Mandatory = $true)]
    [ValidateSet("buildings", "trees")]
    [string]$Layer,
    [string]$MapInfoProDir = $env:MULTIPLANNER_MAPINFO_PRO_DIR
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ([string]::IsNullOrWhiteSpace($MapInfoProDir)) {
    $MapInfoProDir = "C:\Program Files\InfoVista\Planet 25.0\mapinfo\Professional"
}

$source = (Resolve-Path -LiteralPath $InputPath).Path
$target = [IO.Path]::GetFullPath($OutputPath)
if ([IO.Path]::GetExtension($target) -ne ".grc") {
    throw "OutputPath must use the .grc extension: $target"
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

function New-ClassEntry {
    param(
        [single]$LowerBound,
        [single]$UpperBound,
        [single]$NewValue,
        [string]$Label,
        [object]$Color
    )
    $entry = [MapInfo.RasterEngine.Common.ClassInfo]::new()
    $entry.LowerBound = $LowerBound
    $entry.UpperBound = $UpperBound
    $entry.NewValue = $NewValue
    $entry.NewLabel = $Label
    $entry.NewColor = $Color
    return $entry
}

$colorType = [MapInfo.RasterEngine.Common.ClassInfo].GetProperty("NewColor").PropertyType
function New-Color {
    param([int]$Red, [int]$Green, [int]$Blue)
    $signature = [type[]]@([int], [int], [int])
    return $colorType.GetMethod("FromArgb", $signature).Invoke($null, @($Red, $Green, $Blue))
}

if ($Layer -eq "buildings") {
    $classes = [MapInfo.RasterEngine.Common.ClassInfo[]]@(
        (New-ClassEntry 84.5 85.5 1 "building" (New-Color 145 84 46))
    )
} else {
    $classes = [MapInfo.RasterEngine.Common.ClassInfo[]]@(
        (New-ClassEntry 0.5 1.5 1 "forest" (New-Color 34 139 34)),
        (New-ClassEntry 42.5 43.5 2 "woodland" (New-Color 107 142 35))
    )
}

$undefined = [MapInfo.RasterEngine.Common.UndefinedClassInfo]::new()
$undefined.SetNullForUndefinedRange = $true

$driver = [MapInfo.RasterEngine.IO.DriverIDExtensions]::GetString(
    [MapInfo.RasterEngine.IO.DriverID]::GRC
)
$options = [MapInfo.RasterEngine.Common.RasterApiOptions]::new()
[MapInfo.RasterEngine.Operations.RasterAnalysis]::ClassifyRaster(
    $source,
    $target,
    $driver,
    [MapInfo.RasterEngine.Common.ClassificationType]::Classified,
    $classes,
    $undefined,
    0,
    0,
    $true,
    $options,
    $null
)

$created = Get-Item -LiteralPath $target
if ($created.Length -eq 0) {
    throw "MapInfo created an empty GRC: $target"
}
Write-Output $created.FullName
