# MR. HEALTH Data Platform -- GCP Infrastructure Setup Script
# Executes TASK_002, TASK_003, TASK_004, TASK_006
# Project: ${GCP_PROJECT_ID}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "MR. HEALTH Data Platform -- GCP Infrastructure Setup" -ForegroundColor Cyan
Write-Host "Project: $PROJECT_ID" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Configuration from environment variables (load from .env or set manually)
$PROJECT_ID = $env:GCP_PROJECT_ID
$REGION = if ($env:GCP_REGION) { $env:GCP_REGION } else { "us-central1" }
$BUCKET_NAME = $env:GCS_BUCKET_NAME
$LOCATION = if ($env:GCP_LOCATION) { $env:GCP_LOCATION } else { "US" }

if (-not $PROJECT_ID -or -not $BUCKET_NAME) {
    Write-Host "[ERROR] Required environment variables not set:" -ForegroundColor Red
    Write-Host "  GCP_PROJECT_ID  = $PROJECT_ID" -ForegroundColor Red
    Write-Host "  GCS_BUCKET_NAME = $BUCKET_NAME" -ForegroundColor Red
    Write-Host "Set them or load from .env file before running this script." -ForegroundColor Red
    exit 1
}

# Set active project
Write-Host "[SETUP] Setting active project..." -ForegroundColor Yellow
gcloud config set project $PROJECT_ID
gcloud config set compute/region $REGION
gcloud config set compute/zone us-central1-a

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "TASK_002: Enable Required APIs" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

gcloud services enable `
  storage.googleapis.com `
  bigquery.googleapis.com `
  bigquerydatatransfer.googleapis.com `
  cloudfunctions.googleapis.com `
  cloudbuild.googleapis.com `
  cloudscheduler.googleapis.com `
  eventarc.googleapis.com `
  run.googleapis.com `
  monitoring.googleapis.com `
  logging.googleapis.com `
  iam.googleapis.com `
  cloudresourcemanager.googleapis.com

Write-Host ""
Write-Host "[OK] APIs enabled successfully" -ForegroundColor Green
Write-Host ""

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "TASK_003: Create GCS Bucket" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# Create bucket
gsutil mb `
  -p $PROJECT_ID `
  -c STANDARD `
  -l $REGION `
  -b on `
  gs://$BUCKET_NAME/

Write-Host ""
Write-Host "[OK] Bucket created: gs://$BUCKET_NAME" -ForegroundColor Green

# Create prefix structure
Write-Host "[INFO] Creating prefix structure..." -ForegroundColor Yellow

$prefixes = @(
    "raw/csv_sales/.keep",
    "raw/reference_data/.keep",
    "bronze/orders/.keep",
    "bronze/order_items/.keep",
    "bronze/products/.keep",
    "bronze/units/.keep",
    "bronze/states/.keep",
    "bronze/countries/.keep",
    "quarantine/.keep",
    "scripts/.keep"
)

foreach ($prefix in $prefixes) {
    echo $null | gsutil cp - gs://$BUCKET_NAME/$prefix
}

Write-Host "[OK] Prefix structure created" -ForegroundColor Green
Write-Host ""

# Verify bucket
Write-Host "[VERIFY] Listing bucket contents:" -ForegroundColor Yellow
gsutil ls gs://$BUCKET_NAME/
Write-Host ""

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "TASK_004: Create BigQuery Datasets" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# Create datasets
bq mk `
  --project_id=$PROJECT_ID `
  --dataset `
  --location=$LOCATION `
  --description="Bronze layer: schema-enforced, deduplicated data from CSV and reference sources" `
  --label environment:mvp `
  --label layer:bronze `
  mrhealth_bronze

bq mk `
  --project_id=$PROJECT_ID `
  --dataset `
  --location=$LOCATION `
  --description="Silver layer: cleaned, enriched, and normalized data with business rules applied" `
  --label environment:mvp `
  --label layer:silver `
  mrhealth_silver

bq mk `
  --project_id=$PROJECT_ID `
  --dataset `
  --location=$LOCATION `
  --description="Gold layer: star schema dimensional model, KPIs, and aggregations" `
  --label environment:mvp `
  --label layer:gold `
  mrhealth_gold

bq mk `
  --project_id=$PROJECT_ID `
  --dataset `
  --location=$LOCATION `
  --description="Pipeline monitoring: ingestion logs, quality checks, processing metadata" `
  --label environment:mvp `
  --label layer:monitoring `
  mrhealth_monitoring

Write-Host ""
Write-Host "[OK] Datasets created successfully" -ForegroundColor Green

# Verify datasets
Write-Host "[VERIFY] Listing datasets:" -ForegroundColor Yellow
bq ls --project_id=$PROJECT_ID
Write-Host ""

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "TASK_004: Create Bronze Layer Tables" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

Write-Host "[INFO] Creating Bronze tables from SQL files..." -ForegroundColor Yellow
Write-Host "[INFO] Execute: sql/bronze/create_tables.sql" -ForegroundColor Yellow
Write-Host ""

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "TASK_006: Create Service Accounts" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# Create service accounts
gcloud iam service-accounts create sa-mrhealth-ingestion `
  --project=$PROJECT_ID `
  --display-name="MR Health Ingestion Pipeline" `
  --description="Service account for Cloud Functions that process CSV files"

gcloud iam service-accounts create sa-mrhealth-transform `
  --project=$PROJECT_ID `
  --display-name="MR Health Transformation Layer" `
  --description="Service account for BigQuery scheduled queries and transformations"

gcloud iam service-accounts create sa-mrhealth-monitoring `
  --project=$PROJECT_ID `
  --display-name="MR Health Monitoring" `
  --description="Service account for pipeline monitoring and alerting"

Write-Host ""
Write-Host "[OK] Service accounts created" -ForegroundColor Green

# Assign IAM roles
Write-Host "[INFO] Assigning IAM roles..." -ForegroundColor Yellow

$SA_INGESTION = "sa-mrhealth-ingestion@$PROJECT_ID.iam.gserviceaccount.com"
$SA_TRANSFORM = "sa-mrhealth-transform@$PROJECT_ID.iam.gserviceaccount.com"
$SA_MONITORING = "sa-mrhealth-monitoring@$PROJECT_ID.iam.gserviceaccount.com"

# Ingestion SA roles
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$SA_INGESTION" --role="roles/storage.objectViewer" --quiet
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$SA_INGESTION" --role="roles/storage.objectCreator" --quiet
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$SA_INGESTION" --role="roles/bigquery.dataEditor" --quiet
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$SA_INGESTION" --role="roles/bigquery.jobUser" --quiet

# Transform SA roles
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$SA_TRANSFORM" --role="roles/bigquery.dataEditor" --quiet
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$SA_TRANSFORM" --role="roles/bigquery.jobUser" --quiet

# Monitoring SA roles
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$SA_MONITORING" --role="roles/monitoring.viewer" --quiet
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$SA_MONITORING" --role="roles/logging.viewer" --quiet
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$SA_MONITORING" --role="roles/bigquery.metadataViewer" --quiet

Write-Host "[OK] IAM roles assigned" -ForegroundColor Green
Write-Host ""

# Verify
Write-Host "[VERIFY] Service accounts:" -ForegroundColor Yellow
gcloud iam service-accounts list --project=$PROJECT_ID
Write-Host ""

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "SETUP COMPLETE" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "1. Create Bronze tables: bq query < sql/bronze/create_tables.sql" -ForegroundColor White
Write-Host "2. Upload fake data: python scripts/upload_fake_data_to_gcs.py" -ForegroundColor White
Write-Host "3. Verify setup: python scripts/verify_infrastructure.py" -ForegroundColor White
Write-Host ""
