param(
    [Parameter(Mandatory = $true)]
    [string]$InputPath,
    [Parameter(Mandatory = $true)]
    [string]$OutputPath,
    [Parameter(Mandatory = $true)]
    [ValidateSet("buildings", "trees", "building_heights", "tree_heights")]
    [string]$Layer,
    [single]$MaxHeight = 100,
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

function New-HeightClasses {
    param([string]$Prefix, [bool]$IsTree, [single]$Maximum)
    $entries = [Collections.Generic.List[MapInfo.RasterEngine.Common.ClassInfo]]::new()
    $forestColors = @(
        "229,254,250", "220,247,238", "212,240,227", "203,234,215", "197,229,206",
        "196,228,198", "194,226,190", "192,225,182", "190,223,174", "189,222,166",
        "187,220,158", "185,219,148", "183,217,140", "182,216,132", "180,214,124",
        "178,213,116", "177,211,108", "175,210,100", "173,208,92", "170,207,87",
        "163,204,85", "154,202,84", "147,199,82", "139,197,80", "132,195,79",
        "125,192,77", "117,190,76", "110,188,74", "103,185,73", "95,183,71",
        "88,181,69", "80,178,68", "72,176,66", "65,173,64", "57,171,63",
        "50,168,61", "42,166,60", "35,164,58", "28,161,57", "20,159,55",
        "13,157,53", "6,154,52"
    )
    $baseColor = if ($IsTree) { @(220, 245, 210) } else { @(232, 213, 195) }
    $endColor = if ($IsTree) { @(66, 160, 55) } else { @(125, 76, 45) }
    $topStep = [Math]::Max(1, [Math]::Ceiling($Maximum * 2))
    for ($step = 1; $step -le $topStep; $step++) {
        $height = $step / 2
        $lower = if ($step -eq 1) { 0.001 } else { $height - 0.25 }
        $upper = $height + 0.25
        if ($IsTree) {
            $lowIndex = if ($height -le 0.5) { 0 } else { [Math]::Min(41, [Math]::Floor($height)) }
            $highIndex = [Math]::Min(41, [Math]::Ceiling($height))
            $lowColor = [int[]]($forestColors[$lowIndex] -split ',')
            $highColor = [int[]]($forestColors[$highIndex] -split ',')
            $fraction = $height - [Math]::Floor($height)
            $rgb = for ($index = 0; $index -lt 3; $index++) {
                [int][Math]::Round($lowColor[$index] + (($highColor[$index] - $lowColor[$index]) * $fraction))
            }
        } else {
            $ratio = $step / $topStep
            $rgb = for ($index = 0; $index -lt 3; $index++) {
                [int][Math]::Round($baseColor[$index] + (($endColor[$index] - $baseColor[$index]) * $ratio))
            }
        }
        $labelHeight = $height.ToString("0.0", [Globalization.CultureInfo]::InvariantCulture)
        $entries.Add((New-ClassEntry $lower $upper $height "$Prefix ${labelHeight}m" (New-Color @rgb)))
    }
    return $entries.ToArray()
}

if ($Layer -eq "buildings") {
    $classes = [MapInfo.RasterEngine.Common.ClassInfo[]]@(
        (New-ClassEntry 84.5 85.5 1 "building" (New-Color 145 84 46))
    )
} elseif ($Layer -eq "trees") {
    $classes = [MapInfo.RasterEngine.Common.ClassInfo[]]@(
        (New-ClassEntry 0.5 1.5 1 "forest" (New-Color 34 139 34)),
        (New-ClassEntry 42.5 43.5 2 "woodland" (New-Color 107 142 35))
    )
} elseif ($Layer -eq "building_heights") {
    $classes = New-HeightClasses "Building" $false $MaxHeight
} else {
    $classes = New-HeightClasses "Forest" $true $MaxHeight
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
