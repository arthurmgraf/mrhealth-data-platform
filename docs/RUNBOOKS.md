# MR. HEALTH - Operational Runbooks

> Incident response procedures for the MR. HEALTH Data Platform.
> Last updated: 2026-02-07

---

## 1. Pipeline Failure: Bronze-to-Silver Transformation

### Symptoms
- Airflow DAG `bronze_to_silver` shows FAILED status
- Silver tables have stale data (>24h old)

### Diagnosis
```bash
# Check Airflow logs
kubectl logs -f deployment/airflow-webserver -n airflow

# Check BigQuery Bronze freshness
bq query --use_legacy_sql=false \
  'SELECT MAX(ingestion_timestamp) FROM mrhealth_bronze.raw_sales'

# Check Cloud Function logs
gcloud functions logs read csv-processor --limit=50
```

### Resolution
1. **Cloud Function failed**: Check GCS bucket for unprocessed files, re-trigger
2. **BigQuery quota exceeded**: Wait for quota reset (midnight PT)
3. **SQL error**: Check sql/silver/ scripts, fix and re-run DAG
4. **Connectivity issue**: Verify Airflow service account permissions

---

## 2. Data Quality Check Failure

### Symptoms
- DAG `data_quality` tasks FAILED
- Quality results table shows failures

### Diagnosis
```bash
bq query --use_legacy_sql=false \
  'SELECT check_name, check_result, details
   FROM mrhealth_gold.data_quality_results
   ORDER BY run_timestamp DESC LIMIT 20'
```

### Resolution by Check Type
| Check | Common Cause | Fix |
|-------|-------------|-----|
| Freshness | Pipeline delay | See Runbook #1 |
| Null Rate >5% | Malformed CSV | Contact unit, quarantine file |
| Duplicates >1% | Double upload | Run dedup on Bronze, re-run Silver |
| Amount Anomaly | Data entry error | Verify with unit manager |
| Referential Integrity | New product/store | Update PostgreSQL reference tables |

---

## 3. GCS Quota / Storage Issues

### Symptoms
- Cloud Function returns 403 or 429 errors
- `google.api_core.exceptions.TooManyRequests`

### Resolution
1. **Storage full**: Archive old Bronze data to Nearline storage
2. **Operations exceeded**: Wait for monthly reset
3. **Permission error**: Re-verify Workload Identity Federation bindings

---

## 4. Airflow DAG Stuck / Scheduler Issues

### Symptoms
- DAGs show "running" with no progress for >30 min
- Scheduler pod in CrashLoopBackOff

### Resolution
1. **Scheduler crashed**: `kubectl rollout restart deployment/airflow-scheduler -n airflow`
2. **PostgreSQL full**: Check PVC usage, expand if needed
3. **Stuck DAG runs**: Mark as failed in UI, clear and retry
4. **Git-sync broken**: Check git credentials and repo access

---

## 5. Superset Dashboard Issues

### Symptoms
- Superset UI unreachable or showing stale data

### Resolution
1. **Pod crashed**: `kubectl rollout restart deployment/superset -n superset`
2. **BigQuery connection failed**: Verify service account credentials
3. **Stale data**: Check Gold aggregation DAGs ran successfully
4. **Error 1035**: Ensure synchronous DB driver (not async)

---

## Useful Commands

```bash
# Airflow
kubectl port-forward svc/airflow-webserver 8080:8080 -n airflow
airflow dags trigger <dag_id>

# BigQuery
bq ls mrhealth_bronze && bq ls mrhealth_silver && bq ls mrhealth_gold

# K3s
kubectl get all -n airflow
kubectl top pods -n airflow
```
