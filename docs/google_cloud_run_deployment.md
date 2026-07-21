# Permanent Google Cloud Run deployment

The production target is one Cloud Run service containing the React/vinext frontend, FastAPI backend, pinned AMRFinderPlus runtime/database, trained model artifacts, evaluation reports, and an Nginx same-origin proxy. Once deployed, the public URL remains available when the development laptop is off.

## Cost and safety profile

- Region: `us-central1`
- CPU: 2 vCPU
- Memory: 2 GiB
- Concurrency: 1 analysis per instance
- Minimum instances: 0
- Maximum instances: 1
- Request timeout: 900 seconds
- OpenAI key: Secret Manager, pinned secret version
- Uploaded FASTA: held in request memory/temporary tool directories only; not persisted by ResistSense
- API access log: disabled; Nginx logs route metadata, not request bodies

Scaling to zero controls idle cost, but Cloud Build, Artifact Registry, Secret Manager, Cloud Run execution, networking, and OpenAI API usage can still incur charges.

## Prerequisites

1. A dedicated Google Cloud project with billing enabled.
2. Google Cloud CLI installed and authenticated.
3. The local runtime artifacts already present under `artifacts/runtime/models`, `artifacts/phase2`, and `artifacts/evaluation`.
4. A server-side OpenAI API key. Never use a `NEXT_PUBLIC_*` variable for it.

```powershell
gcloud.cmd auth login
gcloud.cmd auth application-default login
gcloud.cmd config set project "YOUR_PROJECT_ID"
```

## Create the OpenAI secret without command-history exposure

Run this once from PowerShell. It asks for the key without displaying it and sends it through standard input rather than a command argument.

```powershell
$ProjectId = "YOUR_PROJECT_ID"
$SecretName = "resistsense-openai-api-key"
$SecureKey = Read-Host "OpenAI API key" -AsSecureString
$Pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureKey)
try {
    $PlainKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($Pointer)
    $PlainKey | gcloud.cmd secrets create $SecretName `
        --project $ProjectId `
        --replication-policy automatic `
        --data-file=-
}
finally {
    if ($Pointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Pointer)
    }
    $PlainKey = $null
    $SecureKey = $null
}
```

If the secret already exists, replace `gcloud secrets create ...` with:

```powershell
$PlainKey | gcloud.cmd secrets versions add $SecretName --project $ProjectId --data-file=-
```

## Create a budget alert

Budgets send alerts but do not impose a hard spending cap. The following example scopes a USD 10 monthly budget to the deployment project and alerts at 50%, 90%, and 100% of actual spend.

```powershell
$ProjectId = "YOUR_PROJECT_ID"
$ProjectNumber = gcloud.cmd projects describe $ProjectId --format="value(projectNumber)"
$BillingResource = gcloud.cmd billing projects describe $ProjectId --format="value(billingAccountName)"
$BillingAccount = ($BillingResource -split "/")[-1]

gcloud.cmd billing budgets create `
    --billing-account $BillingAccount `
    --display-name "ResistSense demo budget" `
    --budget-amount 10USD `
    --filter-projects "projects/$ProjectNumber" `
    --threshold-rule percent=0.50,basis=current-spend `
    --threshold-rule percent=0.90,basis=current-spend `
    --threshold-rule percent=1.00,basis=current-spend
```

## Build and deploy

The script validates required local artifacts, enables the required APIs, creates a dedicated runtime service account and Artifact Registry repository when absent, grants access only to the named secret, builds the explicit Dockerfile in Cloud Build, deploys Cloud Run with bounded scaling, and runs a health check.

```powershell
Set-Location "C:\Users\braya\Desktop\project_personal\genoma_firewall"

powershell.exe -NoProfile -ExecutionPolicy Bypass `
    -File ".\deploy\cloudrun\Deploy-ResistSenseCloudRun.ps1" `
    -ProjectId "YOUR_PROJECT_ID" `
    -Region "us-central1"
```

The final output includes the permanent URL. Add that exact URL to the README and hackathon submission only after the smoke checks pass.

## Smoke checks

```powershell
$ServiceUrl = "https://YOUR_CLOUD_RUN_URL"
Invoke-RestMethod "$ServiceUrl/health"
Invoke-RestMethod "$ServiceUrl/api/v1/readiness"
Invoke-RestMethod "$ServiceUrl/api/v1/verified-demo"
Invoke-RestMethod "$ServiceUrl/api/v1/safety-report"
Start-Process $ServiceUrl
```

Verify in the browser that:

- the verified judge example loads without a FASTA upload;
- a real `.fa`, `.fna`, or `.fasta` upload reaches the scientific pipeline;
- the scientific result renders before the optional GPT audit;
- the audit reports `openai` when the secret is available and deterministic fallback otherwise;
- the downloadable JSON preserves the scientific result and audit separately;
- no request body, filename, checksum, or sequence appears in Cloud Run logs.

## Remove the deployment after judging

Deleting the service stops future Cloud Run execution but does not remove Artifact Registry images, Secret Manager versions, or Cloud Build history.

```powershell
gcloud.cmd run services delete resistsense --region us-central1 --project "YOUR_PROJECT_ID"
```
