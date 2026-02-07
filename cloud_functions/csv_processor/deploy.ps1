# MR. HEALTH Data Platform -- Deploy CSV Processor Cloud Function
# ==================================================
#
# Deploys a 2nd gen Cloud Function that triggers on GCS file uploads
# to raw/csv_sales/ prefix.
#
# Usage:
#   cd cloud_functions/csv_processor
#   .\deploy.ps1

$ErrorActionPreference = "Stop"

# Load configuration
$configPath = "../../config/project_config.yaml"
if (Test-Path $configPath) {
    Write-Host "Loading configuration from $configPath..." -ForegroundColor Cyan
    $config = ConvertFrom-Yaml (Get-Content $configPath -Raw)
    $PROJECT_ID = $config.project.id
    $REGION = $config.project.region
    $BUCKET = $config.storage.bucket
} else {
    Write-Host "Config not found. Set environment variables or create config file." -ForegroundColor Red
    Write-Host "Required: GCP_PROJECT_ID, GCP_REGION, GCS_BUCKET_NAME" -ForegroundColor Red
    $PROJECT_ID = $env:GCP_PROJECT_ID
    $REGION = if ($env:GCP_REGION) { $env:GCP_REGION } else { "us-central1" }
    $BUCKET = $env:GCS_BUCKET_NAME
    if (-not $PROJECT_ID -or -not $BUCKET) {
        Write-Host "[ERROR] Missing required configuration. Set env vars or create config/project_config.yaml" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "MR. HEALTH Data Platform -- Deploy CSV Processor Cloud Function" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Project:  $PROJECT_ID"
Write-Host "Region:   $REGION"
Write-Host "Bucket:   $BUCKET"
Write-Host "Function: csv-processor"
Write-Host ""

# Deploy Cloud Function
Write-Host "[DEPLOY] Deploying Cloud Function (2nd gen)..." -ForegroundColor Yellow
Write-Host "This may take 2-3 minutes..." -ForegroundColor Gray

gcloud functions deploy csv-processor `
  --gen2 `
  --runtime=python311 `
  --region=$REGION `
  --source=. `
  --entry-point=process_csv `
  --trigger-event-filters="type=google.cloud.storage.object.v1.finalized" `
  --trigger-event-filters="bucket=$BUCKET" `
  --memory=256MB `
  --timeout=300s `
  --set-env-vars="PROJECT_ID=$PROJECT_ID,BUCKET_NAME=$BUCKET" `
  --allow-unauthenticated

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "[SUCCESS] Cloud Function deployed!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "  1. Upload a CSV to test trigger:"
    Write-Host "     gsutil cp ../../output/csv_sales/2026/01/28/unit_001/pedido.csv gs://$BUCKET/raw/csv_sales/test/pedido.csv"
    Write-Host "  2. Check function logs:"
    Write-Host "     gcloud functions logs read csv-processor --gen2 --region=$REGION --limit=20"
    Write-Host "  3. Verify data in BigQuery:"
    Write-Host "     bq query 'SELECT COUNT(*) FROM ``$PROJECT_ID.mrhealth_bronze.orders``'"
} else {
    Write-Host ""
    Write-Host "[ERROR] Deployment failed!" -ForegroundColor Red
    exit 1
}
