# Redeploy Cloud Function with Numeric Fix

## Issue Fixed
Converted float columns to Decimal type before loading to BigQuery to resolve pyarrow serialization error:
```
Got bytestring of length 8 (expected 16)
```

## Deployment Command

From the `cloud_functions/csv_processor/` directory:

```powershell
gcloud functions deploy csv-processor `
  --gen2 `
  --runtime=python311 `
  --region=us-central1 `
  --source=. `
  --entry-point=process_csv `
  --trigger-event-filters="type=google.cloud.storage.object.v1.finalized" `
  --trigger-event-filters="bucket=mrhealth-datalake-485810" `
  --memory=256MB `
  --timeout=300s `
  --set-env-vars="PROJECT_ID=${PROJECT_ID},BUCKET_NAME=mrhealth-datalake-485810,BQ_DATASET=mrhealth_bronze" `
  --allow-unauthenticated
```

**Deployment time:** ~2-3 minutes

---

## Test After Deployment

### 1. Upload a test file to trigger the function:
```powershell
gsutil cp ../../output/csv_sales/2026/01/28/unit_001/pedido.csv `
  gs://mrhealth-datalake-485810/raw/csv_sales/test/pedido.csv
```

### 2. Check function logs for success:
```powershell
gcloud functions logs read csv-processor --gen2 --region=us-central1 --limit=20
```

**Expected output:**
```
Processing: gs://mrhealth-datalake-485810/raw/csv_sales/test/pedido.csv
  Read 54 rows from pedido.csv
  [OK] Loaded 54 rows into mrhealth_bronze.orders
```

### 3. Verify data in BigQuery Bronze:
```powershell
bq query "SELECT COUNT(*) as row_count,
          ROUND(SUM(vlr_pedido), 2) as total_value
          FROM ``${PROJECT_ID}.mrhealth_bronze.orders``"
```

### 4. Rebuild Silver and Gold layers:
```powershell
py scripts/build_silver_layer.py
py scripts/build_gold_layer.py
```

### 5. Verify data in Gold layer:
```powershell
bq query "SELECT
  d.year_month,
  COUNT(*) as total_orders,
  ROUND(SUM(f.order_value), 2) as total_revenue
FROM ``${PROJECT_ID}.mrhealth_gold.fact_sales`` f
JOIN ``${PROJECT_ID}.mrhealth_gold.dim_date`` d ON f.date_key = d.date_key
GROUP BY d.year_month
ORDER BY d.year_month"
```

---

## What Was Fixed

**Before:**
- pandas float64 → pyarrow → BigQuery NUMERIC ❌ (type mismatch)

**After:**
- pandas float64 → Python Decimal → pyarrow → BigQuery NUMERIC ✅

**Code change in `main.py`:**
```python
# Convert float columns to Decimal for NUMERIC compatibility
for col in ["vlr_pedido", "taxa_entrega", "vlr_item"]:
    if col in df.columns:
        df[col] = df[col].apply(lambda x: Decimal(str(round(x, 2))) if pd.notna(x) else None)
```

---

## Next Steps After Successful Test

Once the test file loads successfully:

1. **Batch upload all CSV files** to trigger ingestion:
```powershell
# Upload all pedido.csv files
Get-ChildItem -Path "output\csv_sales" -Recurse -Filter "pedido.csv" | ForEach-Object {
    $relativePath = $_.FullName.Substring((Get-Location).Path.Length + 1)
    $gcsPath = $relativePath -replace '\\', '/'
    gsutil cp $_.FullName "gs://mrhealth-datalake-485810/raw/csv_sales/$gcsPath"
}

# Upload all item_pedido.csv files
Get-ChildItem -Path "output\csv_sales" -Recurse -Filter "item_pedido.csv" | ForEach-Object {
    $relativePath = $_.FullName.Substring((Get-Location).Path.Length + 1)
    $gcsPath = $relativePath -replace '\\', '/'
    gsutil cp $_.FullName "gs://mrhealth-datalake-485810/raw/csv_sales/$gcsPath"
}
```

2. **Monitor ingestion**:
```powershell
# Watch function logs in real-time
gcloud functions logs read csv-processor --gen2 --region=us-central1 --limit=50
```

3. **Rebuild transformation layers**:
```powershell
py scripts/build_silver_layer.py
py scripts/build_gold_layer.py
```

4. **Verify complete pipeline**:
```powershell
# Check row counts across all layers
bq query "
SELECT 'bronze_orders' as layer, COUNT(*) as rows FROM ``${PROJECT_ID}.mrhealth_bronze.orders``
UNION ALL SELECT 'silver_orders', COUNT(*) FROM ``${PROJECT_ID}.mrhealth_silver.orders``
UNION ALL SELECT 'gold_fact_sales', COUNT(*) FROM ``${PROJECT_ID}.mrhealth_gold.fact_sales``
"
```

---

**Status:** Ready to redeploy with fix
