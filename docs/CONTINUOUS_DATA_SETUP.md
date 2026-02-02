# Continuous Data Strategy Setup Guide

Generate incremental sales data throughout the day, simulating real business activity for the MR. Health data platform.

## Architecture

```
Cloud Scheduler (7x/day BRT)
  -> Cloud Function: data-generator (HTTP)
    -> GCS: raw/csv_sales/{YYYY}/{MM}/{DD}/unit_{NNN}/window_{HHMM}/
      -> csv-processor (Eventarc, existing)
        -> BigQuery Bronze
          -> Airflow DAG: Silver -> Gold (daily rebuild)
```

## Prerequisites

- Python 3.11+ with pandas, Faker
- GCP service account with Storage and BigQuery access
- `csv-processor` Cloud Function deployed and operational
- (Optional) gcloud CLI for Cloud Function deployment

## 1. Local Generation (No GCP Required)

Generate data for a single business window:

```powershell
# Lunch peak: 3-5 orders per unit
python scripts/generate_incremental_sales.py `
  --window-start 12:00 --window-end 14:00

# Dinner peak with specific date and seed
python scripts/generate_incremental_sales.py `
  --window-start 18:00 --window-end 20:00 `
  --date 2026-02-01 --seed 42
```

Output goes to `output/csv_sales/{YYYY}/{MM}/{DD}/unit_{NNN}/window_{HHMM}/`.

### Business Windows

| Window | Hours (BRT) | Orders/Unit | Daily Total (50 units) |
|--------|-------------|-------------|----------------------|
| Morning ramp-up | 10:00-12:00 | 1-2 | 50-100 |
| Lunch peak | 12:00-14:00 | 3-5 | 150-250 |
| Afternoon lull | 14:00-16:00 | 1-2 | 50-100 |
| Late afternoon | 16:00-18:00 | 2-3 | 100-150 |
| Dinner peak | 18:00-20:00 | 4-6 | 200-300 |
| Evening wind-down | 20:00-22:00 | 2-3 | 100-150 |
| **Daily total** | | | **750-1200** |

### CLI Options

| Flag | Description | Default |
|------|-------------|---------|
| `--window-start` | Window start time (HH:MM) | Required |
| `--window-end` | Window end time (HH:MM) | Required |
| `--date` | Date (YYYY-MM-DD) | Today |
| `--units` | Number of restaurant units | 50 |
| `--output-dir` | Output directory | `output` |
| `--upload` | Upload to GCS after generation | Off |
| `--seed` | Random seed for reproducibility | None |

## 2. Upload to GCS

Generate and upload in one step:

```powershell
python scripts/generate_incremental_sales.py `
  --window-start 12:00 --window-end 14:00 --upload
```

This uploads CSVs to `gs://{bucket}/raw/csv_sales/...` and triggers the existing `csv-processor` Cloud Function automatically via Eventarc.

### Verify Upload

```powershell
# Check GCS files
gsutil ls -r gs://$env:GCS_BUCKET_NAME/raw/csv_sales/2026/02/01/unit_001/window_1214/

# Check csv-processor logs (wait ~30 seconds)
gcloud functions logs read csv-processor --gen2 --region=us-central1 --limit=10

# Verify Bronze table growth
bq query "SELECT COUNT(*) FROM case_ficticio_bronze.orders WHERE _ingest_date = CURRENT_DATE()"
```

## 3. Deploy Cloud Function

For fully automated generation via Cloud Scheduler:

```powershell
# Set environment variables
$env:GCP_PROJECT_ID = "your-project-id"
$env:GCS_BUCKET_NAME = "your-bucket-name"

# Deploy function + create scheduler job
cd cloud_functions/data_generator
.\deploy.ps1
```

The deploy script:
1. Deploys `data-generator` as a 2nd gen HTTP Cloud Function
2. Creates `continuous-data-generator` Cloud Scheduler job (7x/day BRT)

### Manual Test

```powershell
gcloud functions call data-generator --gen2 --region=us-central1
```

### View Logs

```powershell
gcloud functions logs read data-generator --gen2 --region=us-central1 --limit=20
```

## 4. Cloud Scheduler Management

```powershell
# Pause generation
gcloud scheduler jobs pause continuous-data-generator --location=us-central1

# Resume generation
gcloud scheduler jobs resume continuous-data-generator --location=us-central1

# Trigger manually (outside schedule)
gcloud scheduler jobs run continuous-data-generator --location=us-central1
```

## 5. Daily Refresh (Silver/Gold Rebuild)

After all windows complete (last at 22:00 BRT), the Silver and Gold layers need rebuilding.

**With Airflow (recommended):** The `mrhealth_daily_pipeline` DAG runs at 02:00 BRT and handles the full rebuild automatically. See `docs/AIRFLOW_SETUP.md`.

**Without Airflow (manual fallback):**

```powershell
python scripts/build_silver_layer.py
python scripts/build_gold_layer.py
python scripts/build_aggregations.py
```

## 6. Window Path Structure

Incremental data uses window-partitioned GCS paths to prevent file collisions:

```
raw/csv_sales/2026/02/01/unit_001/window_1012/pedido.csv      <- 10:00 window
raw/csv_sales/2026/02/01/unit_001/window_1214/pedido.csv      <- 12:00 window
raw/csv_sales/2026/02/01/unit_001/window_1820/pedido.csv      <- 18:00 window
```

The existing `csv-processor` processes these files without modification -- it checks `startswith("raw/csv_sales/")` and `endswith(".csv")`, both of which match.

**Important:** Do not mix bulk generation (`generate_fake_sales.py`) and incremental generation for the same date range. Both produce valid data but combining them would create duplicates in Bronze.

## 7. Troubleshooting

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError: generate_fake_sales` | Run from project root: `python scripts/generate_incremental_sales.py ...` |
| Cloud Function returns "skipped" | Triggered outside business hours (10-22 BRT). Normal behavior. |
| csv-processor not triggering | Verify Eventarc trigger: `gcloud eventarc triggers list --location=us-central1` |
| Scheduler job not created | Enable Cloud Scheduler API: `gcloud services enable cloudscheduler.googleapis.com` |
| Duplicate data in Bronze | Used both bulk and incremental for same date. Delete duplicates or re-run Bronze load. |
| `--upload` fails with auth error | Set `GOOGLE_APPLICATION_CREDENTIALS` or run `gcloud auth application-default login` |

## Free Tier Usage

| Resource | This Feature | Total Platform | Limit |
|----------|-------------|----------------|-------|
| Cloud Scheduler jobs | 1 | 2 of 3 | 3 |
| Function invocations/month | ~210 gen + ~10,500 csv-proc | ~10,700 | 2,000,000 |
| GCS storage/month | ~21 MB | ~50 MB | 5 GB |
| BQ queries/month | ~1.5 GB | ~5 GB | 1 TB |
