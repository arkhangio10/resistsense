[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectId,
    [string]$Region = "us-central1",
    [string]$ServiceName = "resistsense"
)

# Windows PowerShell 5 surfaces normal gcloud progress written to stderr as a
# NativeCommandError. Every native command is checked explicitly below.
$ErrorActionPreference = "Continue"
gcloud.cmd run services update $ServiceName `
    --project $ProjectId `
    --region $Region `
    --ingress "all" `
    --quiet *> $null
if ($LASTEXITCODE -ne 0) { throw "Unable to restore public ingress." }

gcloud.cmd run services add-iam-policy-binding $ServiceName `
    --project $ProjectId `
    --region $Region `
    --member "allUsers" `
    --role "roles/run.invoker" `
    --quiet
if ($LASTEXITCODE -ne 0) { throw "Unable to restore public access." }

$serviceUrl = gcloud.cmd run services describe $ServiceName `
    --project $ProjectId `
    --region $Region `
    --format "value(status.url)"
[pscustomobject]@{ PublicAccess = "restored"; Url = $serviceUrl }
