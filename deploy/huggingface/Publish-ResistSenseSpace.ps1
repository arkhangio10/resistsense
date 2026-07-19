[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern("^[A-Za-z0-9][A-Za-z0-9_-]*$")]
    [string]$Namespace,

    [ValidatePattern("^[A-Za-z0-9][A-Za-z0-9_-]*$")]
    [string]$SpaceName = "resistsense",

    [string]$Version = "hf-v0.1.0",

    [switch]$PrepareOnly
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$stagingPath = Join-Path $projectRoot "tmp\huggingface-space-upload"
$expectedStagingRoot = Join-Path $projectRoot "tmp"

if (-not $stagingPath.StartsWith($expectedStagingRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Unsafe Space staging path: $stagingPath"
}

$runtime = & (Join-Path $PSScriptRoot "Package-Runtime.ps1") -Version $Version
$repository = (gh repo view --json nameWithOwner --jq .nameWithOwner).Trim()
if ($LASTEXITCODE -ne 0 -or -not $repository) {
    throw "GitHub CLI could not resolve the current repository."
}

$releaseTag = "resistsense-$Version"
$runtimeUrl = "https://github.com/$repository/releases/download/$releaseTag/$($runtime.BundleName)"

if (Test-Path -LiteralPath $stagingPath) {
    Remove-Item -LiteralPath $stagingPath -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $stagingPath | Out-Null

$trackedPaths = git -C $projectRoot ls-files -- pyproject.toml src configs frontend
if ($LASTEXITCODE -ne 0 -or -not $trackedPaths) {
    throw "Git could not enumerate the application source files."
}

foreach ($relativePath in $trackedPaths) {
    $sourcePath = Join-Path $projectRoot $relativePath
    if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
        continue
    }
    $destinationPath = Join-Path $stagingPath $relativePath
    $destinationDirectory = Split-Path -Parent $destinationPath
    New-Item -ItemType Directory -Force -Path $destinationDirectory | Out-Null
    Copy-Item -LiteralPath $sourcePath -Destination $destinationPath
}
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "SPACE_README.md") `
    -Destination (Join-Path $stagingPath "README.md")
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "nginx.conf") -Destination $stagingPath
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "start.sh") -Destination $stagingPath
Copy-Item -LiteralPath (Join-Path $PSScriptRoot ".dockerignore") -Destination $stagingPath

$dockerTemplate = Get-Content -Raw (Join-Path $PSScriptRoot "Dockerfile.template")
$dockerContent = $dockerTemplate.Replace("__RUNTIME_BUNDLE_URL__", $runtimeUrl)
$dockerContent = $dockerContent.Replace("__RUNTIME_BUNDLE_SHA256__", $runtime.Sha256)
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText((Join-Path $stagingPath "Dockerfile"), $dockerContent, $utf8NoBom)

if ($PrepareOnly) {
    [pscustomobject]@{
        StagingPath = $stagingPath
        RuntimeBundle = $runtime.BundlePath
        RuntimeSha256 = $runtime.Sha256
        RuntimeUrl = $runtimeUrl
    }
    return
}

if (-not (Get-Command hf -ErrorAction SilentlyContinue)) {
    throw "The hf CLI is not installed. Install huggingface_hub and run hf auth login."
}

hf auth whoami | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Hugging Face authentication is required. Run: hf auth login"
}

gh release view $releaseTag --repo $repository *> $null
if ($LASTEXITCODE -eq 0) {
    $verificationPath = Join-Path $projectRoot "tmp\hf-release-verification"
    if (-not $verificationPath.StartsWith($expectedStagingRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Unsafe release verification path: $verificationPath"
    }
    if (Test-Path -LiteralPath $verificationPath) {
        Remove-Item -LiteralPath $verificationPath -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $verificationPath | Out-Null
    gh release download $releaseTag `
        --repo $repository `
        --pattern $runtime.BundleName `
        --dir $verificationPath
    if ($LASTEXITCODE -ne 0) {
        throw "The existing GitHub release does not contain $($runtime.BundleName)."
    }
    $downloadedBundle = Join-Path $verificationPath $runtime.BundleName
    $downloadedHash = (Get-FileHash -LiteralPath $downloadedBundle -Algorithm SHA256).Hash.ToLowerInvariant()
    Remove-Item -LiteralPath $verificationPath -Recurse -Force
    if ($downloadedHash -ne $runtime.Sha256) {
        throw "The existing GitHub release asset has a different checksum. Use a new -Version value."
    }
}
else {
    gh release create $releaseTag $runtime.BundlePath `
        --repo $repository `
        --title "ResistSense Hugging Face runtime $Version" `
        --notes "Checksum-frozen runtime assets for the public ResistSense Docker Space."
    if ($LASTEXITCODE -ne 0) {
        throw "The GitHub runtime release could not be created."
    }
}

$spaceId = "$Namespace/$SpaceName"
hf repos create $spaceId --repo-type space --sdk docker --exist-ok
if ($LASTEXITCODE -ne 0) {
    throw "The Hugging Face Space could not be created."
}

hf upload $spaceId $stagingPath . `
    --repo-type space `
    --commit-message "Deploy ResistSense Genome Firewall"
if ($LASTEXITCODE -ne 0) {
    throw "The Hugging Face Space files could not be uploaded."
}

$spaceSlug = ("$Namespace-$SpaceName").ToLowerInvariant().Replace("_", "-")
$permanentUrl = "https://$spaceSlug.hf.space"
$buildDeadline = (Get-Date).AddMinutes(30)
$lastStage = ""
$running = $false

do {
    try {
        $spaceInfo = Invoke-RestMethod -Uri "https://huggingface.co/api/spaces/$spaceId" -TimeoutSec 30
        $stage = [string]$spaceInfo.runtime.stage
    }
    catch {
        $stage = "WAITING_FOR_STATUS"
    }

    if ($stage -ne $lastStage) {
        Write-Host "Hugging Face build status: $stage"
        $lastStage = $stage
    }

    if ($stage -eq "RUNNING") {
        $running = $true
        break
    }
    if ($stage -match "ERROR|FAILED") {
        throw "The Hugging Face build failed with status: $stage"
    }

    Start-Sleep -Seconds 10
} while ((Get-Date) -lt $buildDeadline)

if (-not $running) {
    Write-Warning "The Space upload succeeded, but the remote build is still pending after 30 minutes."
}
else {
    $health = Invoke-RestMethod -Uri "$permanentUrl/health" -TimeoutSec 60
    if (-not $health.ok) {
        throw "The Space is running, but its health endpoint did not pass."
    }
}

[pscustomobject]@{
    SpaceRepository = "https://huggingface.co/spaces/$spaceId"
    PermanentUrl = $permanentUrl
    RuntimeRelease = "https://github.com/$repository/releases/tag/$releaseTag"
    Ready = $running
}
