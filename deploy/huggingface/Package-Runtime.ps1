[CmdletBinding()]
param(
    [string]$Version = "hf-v0.1.0"
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$stagingPath = Join-Path $projectRoot "tmp\hf-runtime-package"
$releasePath = Join-Path $projectRoot "release"
$bundleName = "resistsense-runtime-$Version.zip"
$bundlePath = Join-Path $releasePath $bundleName

if (-not $stagingPath.StartsWith((Join-Path $projectRoot "tmp"), [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Unsafe runtime staging path: $stagingPath"
}

$requiredPaths = @(
    (Join-Path $projectRoot "artifacts\runtime\models"),
    (Join-Path $projectRoot "artifacts\phase2"),
    (Join-Path $projectRoot "artifacts\evaluation\prediction_autopsy.json"),
    (Join-Path $projectRoot "artifacts\evaluation\class_aware_safety_report.json")
)

foreach ($requiredPath in $requiredPaths) {
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        throw "Required runtime asset is missing: $requiredPath"
    }
}

if (Test-Path -LiteralPath $stagingPath) {
    Remove-Item -LiteralPath $stagingPath -Recurse -Force
}

New-Item -ItemType Directory -Force -Path (Join-Path $stagingPath "artifacts\runtime") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $stagingPath "artifacts\evaluation") | Out-Null
New-Item -ItemType Directory -Force -Path $releasePath | Out-Null

Copy-Item -LiteralPath (Join-Path $projectRoot "artifacts\runtime\models") `
    -Destination (Join-Path $stagingPath "artifacts\runtime\models") -Recurse
Copy-Item -LiteralPath (Join-Path $projectRoot "artifacts\phase2") `
    -Destination (Join-Path $stagingPath "artifacts\phase2") -Recurse
Copy-Item -LiteralPath (Join-Path $projectRoot "artifacts\evaluation\prediction_autopsy.json") `
    -Destination (Join-Path $stagingPath "artifacts\evaluation\prediction_autopsy.json")
Copy-Item -LiteralPath (Join-Path $projectRoot "artifacts\evaluation\class_aware_safety_report.json") `
    -Destination (Join-Path $stagingPath "artifacts\evaluation\class_aware_safety_report.json")

if (Test-Path -LiteralPath $bundlePath) {
    Remove-Item -LiteralPath $bundlePath -Force
}

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$bundleStream = [System.IO.File]::Open(
    $bundlePath,
    [System.IO.FileMode]::CreateNew,
    [System.IO.FileAccess]::ReadWrite,
    [System.IO.FileShare]::None
)
$archive = New-Object System.IO.Compression.ZipArchive(
    $bundleStream,
    [System.IO.Compression.ZipArchiveMode]::Create,
    $false
)
$fixedTimestamp = [System.DateTimeOffset]::Parse("2026-01-01T00:00:00Z")

try {
    $files = Get-ChildItem -LiteralPath $stagingPath -Recurse -File | Sort-Object FullName
    foreach ($file in $files) {
        $relativePath = $file.FullName.Substring($stagingPath.Length + 1).Replace("\", "/")
        $entry = $archive.CreateEntry(
            $relativePath,
            [System.IO.Compression.CompressionLevel]::Optimal
        )
        $entry.LastWriteTime = $fixedTimestamp
        $inputStream = [System.IO.File]::OpenRead($file.FullName)
        $entryStream = $entry.Open()
        try {
            $inputStream.CopyTo($entryStream)
        }
        finally {
            $entryStream.Dispose()
            $inputStream.Dispose()
        }
    }
}
finally {
    $archive.Dispose()
    $bundleStream.Dispose()
}

$bundleHash = (Get-FileHash -LiteralPath $bundlePath -Algorithm SHA256).Hash.ToLowerInvariant()
$bundleSize = (Get-Item -LiteralPath $bundlePath).Length

Remove-Item -LiteralPath $stagingPath -Recurse -Force

[pscustomobject]@{
    Version = $Version
    BundleName = $bundleName
    BundlePath = $bundlePath
    Sha256 = $bundleHash
    SizeMB = [math]::Round($bundleSize / 1MB, 2)
}
