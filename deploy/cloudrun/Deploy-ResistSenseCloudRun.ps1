[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectId,
    [string]$Region = "us-central1",
    [string]$ServiceName = "resistsense",
    [string]$RepositoryName = "resistsense",
    [string]$OpenAISecretName = "resistsense-openai-api-key",
    [string]$RuntimeServiceAccountName = "resistsense-runner"
)

# Windows PowerShell 5 surfaces normal gcloud progress written to stderr as a
# NativeCommandError. Native command exit codes are checked explicitly below.
$ErrorActionPreference = "Continue"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location -LiteralPath $projectRoot

foreach ($command in @("gcloud.cmd")) {
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
        throw "Required command is unavailable: $command"
    }
}

$requiredPaths = @(
    "artifacts\runtime\models",
    "artifacts\phase2\curated_cohort_summary.json",
    "artifacts\evaluation\prediction_autopsy.json",
    "artifacts\evaluation\class_aware_safety_report.json",
    "deploy\cloudrun\Dockerfile"
)
foreach ($path in $requiredPaths) {
    if (-not (Test-Path -LiteralPath (Join-Path $projectRoot $path))) {
        throw "Required deployment asset is missing: $path"
    }
}

gcloud.cmd config set project $ProjectId
if ($LASTEXITCODE -ne 0) { throw "Unable to select Google Cloud project." }

gcloud.cmd services enable run.googleapis.com cloudbuild.googleapis.com `
    artifactregistry.googleapis.com secretmanager.googleapis.com
if ($LASTEXITCODE -ne 0) { throw "Unable to enable required Google Cloud APIs." }

$repositoryUri = "$Region-docker.pkg.dev/$ProjectId/$RepositoryName"
gcloud.cmd artifacts repositories describe $RepositoryName `
    --location $Region *> $null
if ($LASTEXITCODE -ne 0) {
    gcloud.cmd artifacts repositories create $RepositoryName `
        --repository-format docker `
        --location $Region `
        --description "ResistSense research demo images"
    if ($LASTEXITCODE -ne 0) { throw "Unable to create Artifact Registry repository." }
}

gcloud.cmd secrets describe $OpenAISecretName --project $ProjectId *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Secret '$OpenAISecretName' is missing. Create it before deployment; never place the key in this script or Docker image."
}

$serviceAccount = "$RuntimeServiceAccountName@$ProjectId.iam.gserviceaccount.com"
gcloud.cmd iam service-accounts describe $serviceAccount --project $ProjectId *> $null
if ($LASTEXITCODE -ne 0) {
    gcloud.cmd iam service-accounts create $RuntimeServiceAccountName `
        --project $ProjectId `
        --display-name "ResistSense Cloud Run runtime"
    if ($LASTEXITCODE -ne 0) { throw "Unable to create the runtime service account." }
}
gcloud.cmd secrets add-iam-policy-binding $OpenAISecretName `
    --project $ProjectId `
    --member "serviceAccount:$serviceAccount" `
    --role "roles/secretmanager.secretAccessor" *> $null
if ($LASTEXITCODE -ne 0) { throw "Unable to grant runtime access to the OpenAI secret." }
$secretVersion = gcloud.cmd secrets versions list $OpenAISecretName `
    --project $ProjectId `
    --filter "state=ENABLED" `
    --sort-by "~createTime" `
    --limit 1 `
    --format "value(name)"
if (-not $secretVersion) { throw "The OpenAI secret has no enabled version." }

$tag = (Get-Date).ToUniversalTime().ToString("yyyyMMdd-HHmmss")
$image = "$repositoryUri/$ServiceName`:$tag"

gcloud.cmd builds submit `
    --project $ProjectId `
    --config deploy/cloudrun/cloudbuild.yaml `
    --substitutions "_IMAGE=$image" `
    --ignore-file .gcloudignore
if ($LASTEXITCODE -ne 0) { throw "Cloud Build failed." }

gcloud.cmd run deploy $ServiceName `
    --image $image `
    --region $Region `
    --platform managed `
    --allow-unauthenticated `
    --cpu 2 `
    --memory 2Gi `
    --concurrency 1 `
    --min-instances 0 `
    --max-instances 1 `
    --timeout 900 `
    --startup-probe "httpGet.path=/health,httpGet.port=8080,periodSeconds=2,timeoutSeconds=2,failureThreshold=60" `
    --service-account $serviceAccount `
    --set-env-vars "AMRFINDER_THREADS=2,RESISTSENSE_USAGE_COUNTER_ENABLED=true,RESISTSENSE_OPENAI_USAGE_GUARD_ENABLED=true" `
    --set-secrets "OPENAI_API_KEY=$OpenAISecretName`:$secretVersion" `
    --quiet
if ($LASTEXITCODE -ne 0) { throw "Cloud Run deployment failed." }

$serviceUrl = gcloud.cmd run services describe $ServiceName `
    --region $Region `
    --format "value(status.url)"
if (-not $serviceUrl) { throw "Deployment completed but no service URL was returned." }

$health = Invoke-RestMethod -Uri "$serviceUrl/health" -TimeoutSec 60
if (-not $health.ok) { throw "Cloud Run health check did not return ok=true." }

[pscustomobject]@{
    Project = $ProjectId
    Region = $Region
    Service = $ServiceName
    Image = $image
    Url = $serviceUrl
    Health = $health.ok
}
