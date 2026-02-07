# Deploy CSV Processor Cloud Function

## Overview

This deploys a 2nd generation Cloud Function that:
- Triggers automatically when CSV files are uploaded to `gs://${GCS_BUCKET_NAME}/raw/csv_sales/`
- Validates and processes orders (pedido.csv) and order items (item_pedido.csv)
- Loads valid data into BigQuery Bronze layer
- Quarantines invalid files with error reports

---

## Deployment Command

Run this command from the `cloud_functions/csv_processor/` directory:

```powershell
gcloud functions deploy csv-processor `
  --gen2 `
  --runtime=python311 `
  --region=us-central1 `
  --source=. `
  --entry-point=process_csv `
  --trigger-event-filters="type=google.cloud.storage.object.v1.finalized" `
  --trigger-event-filters="bucket=${GCS_BUCKET_NAME}" `
  --memory=256MB `
  --timeout=300s `
  --set-env-vars="PROJECT_ID=${PROJECT_ID},BUCKET_NAME=${GCS_BUCKET_NAME},BQ_DATASET=mrhealth_bronze" `
  --allow-unauthenticated
```

**Expected output:**
```
Deploying function...
✓ Function deployed successfully
  URL: https://us-central1-${PROJECT_ID}.cloudfunctions.net/csv-processor
  Trigger: google.cloud.storage.object.v1.finalized (bucket: ${GCS_BUCKET_NAME})
```

---

## Testing the Function

### Step 1: Trigger by uploading a test file

```powershell
# Upload pedido.csv to trigger the function
gsutil cp ../../output/csv_sales/2026/01/28/unit_001/pedido.csv `
  gs://${GCS_BUCKET_NAME}/raw/csv_sales/test/pedido.csv

# Upload item_pedido.csv to trigger the function
gsutil cp ../../output/csv_sales/2026/01/28/unit_001/item_pedido.csv `
  gs://${GCS_BUCKET_NAME}/raw/csv_sales/test/item_pedido.csv
```

### Step 2: Check function execution logs

```powershell
gcloud functions logs read csv-processor --gen2 --region=us-central1 --limit=20
```

**Expected log output:**
```
Processing: gs://${GCS_BUCKET_NAME}/raw/csv_sales/test/pedido.csv
  Read 54 rows from pedido.csv
  [OK] Loaded 54 rows into mrhealth_bronze.orders
```

### Step 3: Verify data in BigQuery

```powershell
# Check orders table
bq query --use_legacy_sql=false `
  "SELECT COUNT(*) as row_count FROM ``${PROJECT_ID}.mrhealth_bronze.orders``"

# Check order_items table
bq query --use_legacy_sql=false `
  "SELECT COUNT(*) as row_count FROM ``${PROJECT_ID}.mrhealth_bronze.order_items``"

# View sample data
bq query --use_legacy_sql=false --max_rows=5 `
  "SELECT * FROM ``${PROJECT_ID}.mrhealth_bronze.orders`` ORDER BY _ingest_timestamp DESC LIMIT 5"
```

---

## Trigger All Uploaded Files

Once the function is deployed and tested, trigger ingestion of all previously uploaded CSV files:

```powershell
# List all CSV files currently in GCS
gsutil ls -r gs://${GCS_BUCKET_NAME}/raw/csv_sales/**/*.csv

# The function will trigger automatically for new uploads
# To process existing files, you need to either:
# 1. Re-upload them (copy to new location then back)
# 2. Or load them manually using a batch script
```

---

## Monitoring and Debugging

### View recent function executions:
```powershell
gcloud functions logs read csv-processor --gen2 --region=us-central1 --limit=50
```

### Check function details:
```powershell
gcloud functions describe csv-processor --gen2 --region=us-central1
```

### Check quarantined files:
```powershell
gsutil ls gs://${GCS_BUCKET_NAME}/quarantine/
```

---

## Cost Estimate

- **Cloud Function invocations:** 100 files/day x 30 days = 3,000/month (FREE - under 2M limit)
- **Compute time:** ~2 seconds/file x 256 MB = 512 MB-sec/file x 3,000 = 1,536,000 MB-sec/month (FREE - under 400K GB-sec limit)
- **Network egress:** Negligible (same region)
- **Total:** $0.00

---

## Troubleshooting

### Issue: Function not triggering
- Check that bucket name matches exactly: `${GCS_BUCKET_NAME}`
- Verify files are uploaded to `raw/csv_sales/` prefix
- Check Eventarc logs: `gcloud eventarc triggers list --location=us-central1`

### Issue: Function fails with permission errors
- Ensure Cloud Functions service account has these roles:
  - Storage Object Viewer (read GCS)
  - BigQuery Data Editor (write BQ)
- Default Compute Service Account should have these by default

### Issue: Data not appearing in BigQuery
- Check function logs for errors
- Verify CSV files have correct schema (semicolon-delimited, matching expected columns)
- Check quarantine folder for rejected files

---

**Status:** Ready to deploy
**Next:** Deploy the function and test with uploaded CSV files
