param(
    [string]$OutputPath = "release\resistsense-0.1.0-assets.zip"
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$manifestPath = Join-Path $projectRoot "release\manifest.json"
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$modelDir = Join-Path $projectRoot "artifacts\runtime\models"
$evaluationDir = Join-Path $projectRoot "artifacts\evaluation"
$resolvedOutput = [IO.Path]::GetFullPath((Join-Path $projectRoot $OutputPath))

if (-not $resolvedOutput.StartsWith($projectRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Release output must stay inside the project workspace"
}

foreach ($model in $manifest.models) {
    $path = Join-Path $modelDir $model.name
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Missing release model: $($model.name)"
    }
    $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLower()
    if ($actual -ne $model.sha256) {
        throw "Checksum mismatch for $($model.name)"
    }
}

$evaluationChecks = @{
    "predictions.csv" = $manifest.predictions_sha256
    "model_selection.json" = $manifest.model_selection_sha256
    "evaluation.json" = $manifest.evaluation_sha256
    "prediction_autopsy.json" = $manifest.prediction_autopsy_sha256
}
foreach ($name in $evaluationChecks.Keys) {
    $path = Join-Path $evaluationDir $name
    $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLower()
    if ($actual -ne $evaluationChecks[$name]) {
        throw "Checksum mismatch for $name"
    }
}

$temporary = Join-Path $projectRoot "tmp\release-package"
if (Test-Path -LiteralPath $temporary) {
    $resolvedTemporary = (Resolve-Path -LiteralPath $temporary).Path
    if (-not $resolvedTemporary.StartsWith($projectRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Temporary path escaped the project workspace"
    }
    Remove-Item -LiteralPath $resolvedTemporary -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $temporary | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $temporary "models") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $temporary "evaluation") | Out-Null

Copy-Item -LiteralPath $manifestPath -Destination (Join-Path $temporary "manifest.json")
foreach ($model in $manifest.models) {
    Copy-Item -LiteralPath (Join-Path $modelDir $model.name) -Destination (Join-Path $temporary "models")
}
foreach ($name in @(
    "evaluation.json",
    "feature_ablation.json",
    "model_selection.json",
    "prediction_autopsy.json",
    "predictions.csv",
    "release_gate.json"
)) {
    Copy-Item -LiteralPath (Join-Path $evaluationDir $name) -Destination (Join-Path $temporary "evaluation")
}

$outputDirectory = Split-Path -Parent $resolvedOutput
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
if (Test-Path -LiteralPath $resolvedOutput) {
    Remove-Item -LiteralPath $resolvedOutput -Force
}
Compress-Archive -Path (Join-Path $temporary "*") -DestinationPath $resolvedOutput -CompressionLevel Optimal
$bundleHash = (Get-FileHash -LiteralPath $resolvedOutput -Algorithm SHA256).Hash.ToLower()

[pscustomobject]@{
    output = $resolvedOutput
    size_bytes = (Get-Item -LiteralPath $resolvedOutput).Length
    sha256 = $bundleHash
    models = @($manifest.models).Count
} | ConvertTo-Json
