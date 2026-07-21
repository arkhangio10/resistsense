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
- Usage counter: Firestore stores only a SHA-256 hash of a random browser UUID and aggregate count; no IP, FASTA, filename, or identity is stored by the application. Google Cloud infrastructure request logs remain subject to the project's logging configuration and retention policy.

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

## Configure the counter and automatic cost guard

After the first Cloud Run deployment, run the operations script. It creates the Firestore anonymous-browser counter, sends an email to `arkhangio@gmail.com` at 50% of actual monthly spend, and deploys a Pub/Sub-triggered guard that changes only the ResistSense service to internal-only ingress and removes its public invoker at 100%.

This billing account uses PEN, so the configured monthly amount is **S/34**, approximately USD 9.98 using the SBS/BCRP 17 July 2026 selling rate of S/3.408 per USD. The email threshold is **S/17**, approximately USD 4.99. This stays just below the requested USD 10 ceiling; revisit the PEN amount if the exchange rate moves materially.

Google Cloud budgets use delayed estimated billing data and are not hard real-time caps. The guard is reversible and safer than disabling billing for the whole project, but a small overrun beyond USD 10 remains possible. Artifact Registry and Secret Manager storage can also continue to incur a small cost after public access closes.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
    -File ".\deploy\cloudrun\Configure-ResistSenseOperations.ps1" `
    -ProjectId "YOUR_PROJECT_ID" `
    -BillingAccountId "YOUR_BILLING_ACCOUNT_ID" `
    -BudgetAmount 34 `
    -BudgetCurrency "PEN" `
    -AlertEmail "arkhangio@gmail.com"
```

The displayed count is **unique anonymous browsers**, not verified people. The same browser is counted once while it keeps local storage; another browser/profile or cleared storage counts as a new visitor.

If the budget guard closes the demo and you later decide to reopen it, first inspect the spend, then run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
    -File ".\deploy\cloudrun\Restore-ResistSensePublicAccess.ps1" `
    -ProjectId "YOUR_PROJECT_ID"
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
