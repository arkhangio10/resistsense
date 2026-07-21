[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectId,
    [Parameter(Mandatory = $true)]
    [string]$BillingAccountId,
    [string]$Region = "us-central1",
    [string]$ServiceName = "resistsense",
    [string]$RuntimeServiceAccountName = "resistsense-runner",
    [string]$BudgetGuardServiceAccountName = "resistsense-budget-guard",
    [string]$BudgetDisplayName = "ResistSense demo budget",
    [decimal]$BudgetAmount = 34,
    [string]$BudgetCurrency = "PEN",
    [decimal]$ReferenceAmountUsd = 10,
    [string]$AlertEmail = "arkhangio@gmail.com",
    [string]$BudgetTopicName = "resistsense-budget-events",
    [string]$BudgetFunctionName = "resistsense-budget-guard"
)

# Windows PowerShell 5 surfaces normal gcloud progress written to stderr as a
# NativeCommandError. Native command exit codes are checked explicitly below.
$ErrorActionPreference = "Continue"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location -LiteralPath $projectRoot

if (-not (Get-Command "gcloud.cmd" -ErrorAction SilentlyContinue)) {
    throw "Required command is unavailable: gcloud.cmd"
}

gcloud.cmd config set project $ProjectId *> $null
if ($LASTEXITCODE -ne 0) { throw "Unable to select Google Cloud project." }

$billingCurrency = gcloud.cmd billing accounts describe $BillingAccountId `
    --format "value(currencyCode)"
if ($LASTEXITCODE -ne 0 -or -not $billingCurrency) {
    throw "Unable to resolve the billing account currency."
}
if ($billingCurrency -ne $BudgetCurrency) {
    throw "Budget currency '$BudgetCurrency' does not match billing currency '$billingCurrency'."
}

$serviceUrl = gcloud.cmd run services describe $ServiceName `
    --project $ProjectId `
    --region $Region `
    --format "value(status.url)"
if ($LASTEXITCODE -ne 0 -or -not $serviceUrl) {
    throw "Deploy Cloud Run service '$ServiceName' before configuring operations."
}

gcloud.cmd services enable `
    billingbudgets.googleapis.com `
    cloudbilling.googleapis.com `
    cloudfunctions.googleapis.com `
    eventarc.googleapis.com `
    firestore.googleapis.com `
    iam.googleapis.com `
    monitoring.googleapis.com `
    pubsub.googleapis.com `
    run.googleapis.com
if ($LASTEXITCODE -ne 0) { throw "Unable to enable operations APIs." }

gcloud.cmd firestore databases describe `
    --project $ProjectId `
    --database "(default)" *> $null
if ($LASTEXITCODE -ne 0) {
    gcloud.cmd firestore databases create `
        --project $ProjectId `
        --database "(default)" `
        --location $Region `
        --type firestore-native `
        --quiet
    if ($LASTEXITCODE -ne 0) { throw "Unable to create the Firestore counter database." }
}

$runtimeServiceAccount = "$RuntimeServiceAccountName@$ProjectId.iam.gserviceaccount.com"
gcloud.cmd projects add-iam-policy-binding $ProjectId `
    --member "serviceAccount:$runtimeServiceAccount" `
    --role "roles/datastore.user" `
    --condition None `
    --quiet *> $null
if ($LASTEXITCODE -ne 0) { throw "Unable to grant Firestore access to the runtime service account." }

gcloud.cmd run services update $ServiceName `
    --project $ProjectId `
    --region $Region `
    --update-env-vars "RESISTSENSE_USAGE_COUNTER_ENABLED=true" `
    --quiet *> $null
if ($LASTEXITCODE -ne 0) { throw "Unable to enable the anonymous usage counter." }

gcloud.cmd pubsub topics describe $BudgetTopicName --project $ProjectId *> $null
if ($LASTEXITCODE -ne 0) {
    gcloud.cmd pubsub topics create $BudgetTopicName --project $ProjectId *> $null
    if ($LASTEXITCODE -ne 0) { throw "Unable to create the budget Pub/Sub topic." }
}
$topicResource = "projects/$ProjectId/topics/$BudgetTopicName"

$guardServiceAccount = "$BudgetGuardServiceAccountName@$ProjectId.iam.gserviceaccount.com"
gcloud.cmd iam service-accounts describe $guardServiceAccount --project $ProjectId *> $null
if ($LASTEXITCODE -ne 0) {
    gcloud.cmd iam service-accounts create $BudgetGuardServiceAccountName `
        --project $ProjectId `
        --display-name "ResistSense reversible budget guard" *> $null
    if ($LASTEXITCODE -ne 0) { throw "Unable to create the budget guard service account." }
}
gcloud.cmd projects add-iam-policy-binding $ProjectId `
    --member "serviceAccount:$guardServiceAccount" `
    --role "roles/run.admin" `
    --condition None `
    --quiet *> $null
if ($LASTEXITCODE -ne 0) { throw "Unable to grant selective Cloud Run shutdown permission." }
gcloud.cmd iam service-accounts add-iam-policy-binding $runtimeServiceAccount `
    --project $ProjectId `
    --member "serviceAccount:$guardServiceAccount" `
    --role "roles/iam.serviceAccountUser" `
    --quiet *> $null
if ($LASTEXITCODE -ne 0) { throw "Unable to grant the budget guard access to update the ResistSense service." }

gcloud.cmd functions deploy $BudgetFunctionName `
    --gen2 `
    --project $ProjectId `
    --region $Region `
    --runtime python311 `
    --source deploy/budget_guard `
    --entry-point handle_budget_event `
    --trigger-topic $BudgetTopicName `
    --service-account $guardServiceAccount `
    --set-env-vars "TARGET_PROJECT_ID=$ProjectId,TARGET_REGION=$Region,TARGET_SERVICE=$ServiceName,EXPECTED_BUDGET_NAME=$BudgetDisplayName" `
    --memory 256Mi `
    --timeout 60s `
    --min-instances 0 `
    --max-instances 1 `
    --quiet
if ($LASTEXITCODE -ne 0) { throw "Unable to deploy the budget guard function." }

$accessToken = gcloud.cmd auth print-access-token
if ($LASTEXITCODE -ne 0 -or -not $accessToken) {
    throw "Unable to obtain a Google Cloud access token for Monitoring."
}
$headers = @{ Authorization = "Bearer $accessToken" }
$channelsUri = "https://monitoring.googleapis.com/v3/projects/$ProjectId/notificationChannels"
$channels = Invoke-RestMethod -Method Get -Uri $channelsUri -Headers $headers
$emailChannel = @($channels.notificationChannels) | Where-Object {
    $_.type -eq "email" -and $_.labels.email_address -eq $AlertEmail
} | Select-Object -First 1
if (-not $emailChannel) {
    $channelBody = @{
        type = "email"
        displayName = "ResistSense budget alert"
        description = "Email alert for the dedicated ResistSense demo budget."
        labels = @{ email_address = $AlertEmail }
        enabled = $true
    } | ConvertTo-Json -Depth 4
    $emailChannel = Invoke-RestMethod `
        -Method Post `
        -Uri $channelsUri `
        -Headers $headers `
        -ContentType "application/json" `
        -Body $channelBody
}
$channelResource = $emailChannel.name
if (-not $channelResource) { throw "Unable to create or find the email notification channel." }
$accessToken = $null
$headers = $null

$projectNumber = gcloud.cmd projects describe $ProjectId --format "value(projectNumber)"
if ($LASTEXITCODE -ne 0 -or -not $projectNumber) { throw "Unable to resolve the project number." }
$projectFilter = "projects/$projectNumber"
$budgetAmountWithCurrency = "$BudgetAmount$BudgetCurrency"
$budgetResource = gcloud.cmd billing budgets list `
    --billing-account $BillingAccountId `
    --filter "displayName='$BudgetDisplayName'" `
    --format "value(name)" `
    --limit 1
if ($LASTEXITCODE -ne 0) { throw "Unable to inspect existing budgets." }

if ($budgetResource) {
    $budgetId = ($budgetResource -split "/")[-1]
    gcloud.cmd billing budgets update $budgetId `
        --billing-account $BillingAccountId `
        --budget-amount $budgetAmountWithCurrency `
        --filter-projects $projectFilter `
        --notifications-rule-monitoring-notification-channels $channelResource `
        --notifications-rule-pubsub-topic $topicResource `
        --clear-threshold-rules `
        --add-threshold-rule "percent=0.50,basis=current-spend" `
        --add-threshold-rule "percent=1.00,basis=current-spend" `
        --quiet *> $null
    if ($LASTEXITCODE -ne 0) { throw "Unable to update the existing budget." }
}
else {
    $budgetResource = gcloud.cmd billing budgets create `
        --billing-account $BillingAccountId `
        --display-name $BudgetDisplayName `
        --budget-amount $budgetAmountWithCurrency `
        --filter-projects $projectFilter `
        --notifications-rule-monitoring-notification-channels $channelResource `
        --notifications-rule-pubsub-topic $topicResource `
        --threshold-rule "percent=0.50,basis=current-spend" `
        --threshold-rule "percent=1.00,basis=current-spend" `
        --format "value(name)"
    if ($LASTEXITCODE -ne 0 -or -not $budgetResource) { throw "Unable to create the budget." }
}

[pscustomobject]@{
    Project = $ProjectId
    ServiceUrl = $serviceUrl
    Counter = "Firestore unique anonymous browsers"
    Budget = "$BudgetAmount $BudgetCurrency monthly actual spend (approximately $ReferenceAmountUsd USD at configuration time)"
    EmailAlert = "50% ($($BudgetAmount / 2) $BudgetCurrency) -> $AlertEmail"
    PublicAccessGuard = "100% ($BudgetAmount $BudgetCurrency) -> internal-only ingress and remove allUsers invoker"
    BudgetResource = $budgetResource
    NotificationTopic = $topicResource
    Warning = "Billing notifications are delayed; a small overrun remains possible."
}
