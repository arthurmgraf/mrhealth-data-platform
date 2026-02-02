# Case Ficticio - Teste -- Deploy Data Generator Cloud Function
# ==============================================================
#
# Deploys the data-generator HTTP Cloud Function and creates
# the Cloud Scheduler job for continuous data generation.
#
# Prerequisites:
#   - gcloud CLI authenticated
#   - Cloud Scheduler API enabled
#   - Environment variables: GCP_PROJECT_ID, GCS_BUCKET_NAME
#
# Usage:
#   cd cloud_functions/data_generator
#   .\deploy.ps1

$ErrorActionPreference = "Stop"

# Load configuration from environment
$PROJECT_ID = $env:GCP_PROJECT_ID
$REGION = if ($env:GCP_REGION) { $env:GCP_REGION } else { "us-central1" }
$BUCKET = $env:GCS_BUCKET_NAME

if (-not $PROJECT_ID -or -not $BUCKET) {
    Write-Host "[ERROR] Set GCP_PROJECT_ID and GCS_BUCKET_NAME environment variables" -ForegroundColor Red
    Write-Host "  Example:" -ForegroundColor Gray
    Write-Host '  $env:GCP_PROJECT_ID = "your-project-id"' -ForegroundColor Gray
    Write-Host '  $env:GCS_BUCKET_NAME = "your-bucket-name"' -ForegroundColor Gray
    exit 1
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Case Ficticio - Teste -- Deploy Data Generator" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Project:  $PROJECT_ID"
Write-Host "Region:   $REGION"
Write-Host "Bucket:   $BUCKET"
Write-Host "Function: data-generator"
Write-Host ""

# Step 1: Deploy Cloud Function
Write-Host "[STEP 1] Deploying Cloud Function (2nd gen)..." -ForegroundColor Yellow

gcloud functions deploy data-generator `
  --gen2 `
  --runtime=python311 `
  --region=$REGION `
  --source=. `
  --entry-point=generate_data `
  --trigger-http `
  --memory=256MB `
  --timeout=300s `
  --set-env-vars="PROJECT_ID=$PROJECT_ID,BUCKET_NAME=$BUCKET,NUM_UNITS=50" `
  --allow-unauthenticated

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Cloud Function deployment failed!" -ForegroundColor Red
    exit 1
}

Write-Host "[SUCCESS] Cloud Function deployed!" -ForegroundColor Green

# Get function URL
$functionUrl = gcloud functions describe data-generator `
  --gen2 --region=$REGION --format="value(serviceConfig.uri)"

Write-Host "Function URL: $functionUrl" -ForegroundColor Cyan

# Step 2: Create Cloud Scheduler job
Write-Host ""
Write-Host "[STEP 2] Creating Cloud Scheduler job..." -ForegroundColor Yellow

# Delete existing job if present (idempotent redeploy)
gcloud scheduler jobs delete continuous-data-generator `
  --location=$REGION --quiet 2>$null

gcloud scheduler jobs create http continuous-data-generator `
  --location=$REGION `
  --schedule="0 10,12,14,16,18,20,22 * * *" `
  --timezone="America/Sao_Paulo" `
  --uri="$functionUrl" `
  --http-method=POST `
  --attempt-deadline=300s

if ($LASTEXITCODE -ne 0) {
    Write-Host "[WARN] Cloud Scheduler job creation failed." -ForegroundColor Yellow
    Write-Host "  This may mean billing is not enabled for Cloud Scheduler." -ForegroundColor Gray
    Write-Host "  Enable billing: gcloud services enable cloudscheduler.googleapis.com" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  You can still test manually:" -ForegroundColor Cyan
    Write-Host "  gcloud functions call data-generator --gen2 --region=$REGION" -ForegroundColor Cyan
} else {
    Write-Host "[SUCCESS] Cloud Scheduler job created!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Schedule: 7x/day (10, 12, 14, 16, 18, 20, 22) BRT" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Management commands:" -ForegroundColor Cyan
    Write-Host "  Pause:  gcloud scheduler jobs pause continuous-data-generator --location=$REGION"
    Write-Host "  Resume: gcloud scheduler jobs resume continuous-data-generator --location=$REGION"
    Write-Host "  Run:    gcloud scheduler jobs run continuous-data-generator --location=$REGION"
    Write-Host "  Logs:   gcloud functions logs read data-generator --gen2 --region=$REGION --limit=20"
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Deployment complete!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
