"""
MR. Health Data Retention DAG
===============================

Manages data lifecycle to keep GCP within Free Tier limits.
Cleans old Bronze rows and GCS files, tracks storage usage.

Schedule: Weekly on Sundays at 04:00 BRT
Tasks:
    1. calculate_storage  - Snapshot current GCS + BQ usage
    2. archive_bronze     - DELETE Bronze rows > 90 days
    3. cleanup_gcs        - Delete GCS CSVs > 60 days
    4. verify_free_tier   - Check usage < 80% of Free Tier limits
    5. report             - Log summary and save to free_tier_usage

Author: Arthur Graf
Date: February 2026
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from airflow import DAG
from airflow.operators.python import PythonOperator
from google.cloud import bigquery, storage

from mrhealth.callbacks.alerts import on_task_failure
from mrhealth.config.loader import get_project_id, load_config

logger = logging.getLogger(__name__)

DAG_ID = "mrhealth_data_retention"
SCHEDULE = "0 4 * * 0"
TAGS = ["mrhealth", "retention", "finops"]


def calculate_storage(**context: Any) -> dict[str, Any]:
    """Calculate current GCS and BigQuery storage usage."""
    config = load_config()
    project_id = get_project_id()
    bucket_name = config["storage"]["bucket"]

    gcs_client = storage.Client(project=project_id)
    bucket = gcs_client.bucket(bucket_name)
    gcs_bytes = sum(blob.size or 0 for blob in bucket.list_blobs())
    gcs_gb = gcs_bytes / (1024**3)

    bq_client = bigquery.Client(project=project_id)
    bq_bytes = 0
    for dataset_name in ["mrhealth_bronze", "mrhealth_silver",
                         "mrhealth_gold", "mrhealth_monitoring"]:
        dataset_ref = bq_client.dataset(dataset_name)
        tables = list(bq_client.list_tables(dataset_ref))
        for table_ref in tables:
            table = bq_client.get_table(table_ref)
            bq_bytes += table.num_bytes or 0
    bq_gb = bq_bytes / (1024**3)

    limits = config.get("free_tier_limits", {})
    result = {
        "gcs_storage_bytes": gcs_bytes,
        "gcs_storage_gb": round(gcs_gb, 3),
        "gcs_limit_gb": limits.get("gcs_storage_gb", 5),
        "gcs_usage_pct": round(gcs_gb / limits.get("gcs_storage_gb", 5) * 100, 1),
        "bq_storage_bytes": bq_bytes,
        "bq_storage_gb": round(bq_gb, 3),
        "bq_limit_gb": limits.get("bq_storage_gb", 10),
        "bq_usage_pct": round(bq_gb / limits.get("bq_storage_gb", 10) * 100, 1),
    }

    logger.info("Storage: GCS=%.2f GB (%.1f%%), BQ=%.2f GB (%.1f%%)",
                gcs_gb, result["gcs_usage_pct"], bq_gb, result["bq_usage_pct"])

    context["ti"].xcom_push(key="storage_snapshot", value=result)
    return result


def archive_bronze(**context: Any) -> dict[str, Any]:
    """Delete Bronze rows older than 90 days."""
    project_id = get_project_id()
    config = load_config()
    max_days = config.get("retention", {}).get("bronze_max_days", 90)
    client = bigquery.Client(project=project_id)

    tables = ["orders", "order_items"]
    total_deleted = 0

    for table in tables:
        sql = f"""
        DELETE FROM `{project_id}.mrhealth_bronze.{table}`
        WHERE _ingest_date < DATE_SUB(CURRENT_DATE(), INTERVAL {max_days} DAY)
        """
        job = client.query(sql)
        job.result()
        affected = job.num_dml_affected_rows or 0
        total_deleted += affected
        logger.info("Deleted %d rows from bronze.%s (older than %d days)",
                     affected, table, max_days)

    return {"total_deleted": total_deleted, "max_days": max_days}


def cleanup_gcs(**context: Any) -> dict[str, Any]:
    """Delete GCS CSV files older than 60 days."""
    config = load_config()
    project_id = get_project_id()
    bucket_name = config["storage"]["bucket"]
    max_days = config.get("retention", {}).get("gcs_raw_max_days", 60)
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_days)

    client = storage.Client(project=project_id)
    bucket = client.bucket(bucket_name)
    deleted = 0
    deleted_bytes = 0

    for blob in bucket.list_blobs(prefix="raw/csv_sales/"):
        if blob.updated and blob.updated < cutoff:
            deleted_bytes += blob.size or 0
            blob.delete()
            deleted += 1

    logger.info("Deleted %d GCS files (%.2f MB, older than %d days)",
                deleted, deleted_bytes / (1024**2), max_days)

    return {"deleted_files": deleted, "deleted_bytes": deleted_bytes}


def verify_free_tier(**context: Any) -> None:
    """Check if usage is within Free Tier limits and alert if > 80%."""
    snapshot = context["ti"].xcom_pull(task_ids="calculate_storage", key="storage_snapshot")
    if not snapshot:
        logger.warning("No storage snapshot available")
        return

    config = load_config()
    alert_pct = config.get("retention", {}).get("free_tier_alert_pct", 80)

    alerts = []
    if snapshot["gcs_usage_pct"] > alert_pct:
        alerts.append(f"GCS: {snapshot['gcs_usage_pct']}% (limit: {alert_pct}%)")
    if snapshot["bq_usage_pct"] > alert_pct:
        alerts.append(f"BQ: {snapshot['bq_usage_pct']}% (limit: {alert_pct}%)")

    if alerts:
        logger.warning("FREE TIER ALERT: %s", " | ".join(alerts))
    else:
        logger.info("Free Tier OK: GCS=%.1f%%, BQ=%.1f%%",
                     snapshot["gcs_usage_pct"], snapshot["bq_usage_pct"])


def save_usage_report(**context: Any) -> None:
    """Save usage snapshot to free_tier_usage table."""
    snapshot = context["ti"].xcom_pull(task_ids="calculate_storage", key="storage_snapshot")
    if not snapshot:
        return

    project_id = get_project_id()
    client = bigquery.Client(project=project_id)
    now = datetime.now(timezone.utc)

    rows = [{
        "snapshot_id": str(uuid.uuid4())[:12],
        "snapshot_date": now.strftime("%Y-%m-%d"),
        "snapshot_timestamp": now.isoformat(),
        "gcs_storage_bytes": snapshot["gcs_storage_bytes"],
        "gcs_storage_gb": snapshot["gcs_storage_gb"],
        "gcs_limit_gb": snapshot["gcs_limit_gb"],
        "gcs_usage_pct": snapshot["gcs_usage_pct"],
        "bq_storage_bytes": snapshot["bq_storage_bytes"],
        "bq_storage_gb": snapshot["bq_storage_gb"],
        "bq_limit_gb": snapshot["bq_limit_gb"],
        "bq_usage_pct": snapshot["bq_usage_pct"],
        "bq_query_bytes_month": 0,
        "bq_query_tb_month": 0.0,
        "bq_query_limit_tb": 1.0,
        "bq_query_usage_pct": 0.0,
        "details": json.dumps({"source": "data_retention_dag"}),
    }]

    table_id = f"{project_id}.mrhealth_monitoring.free_tier_usage"
    errors = client.insert_rows_json(table_id, rows)
    if errors:
        logger.error("Error saving usage report: %s", errors)
    else:
        logger.info("Usage report saved to %s", table_id)


default_args = {
    "owner": "mrhealth-data-team",
    "depends_on_past": False,
    "email_on_failure": True,
    "email": ["alerts@mrhealth.local"],
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(minutes=30),
    "on_failure_callback": on_task_failure,
}

with DAG(
    dag_id=DAG_ID,
    default_args=default_args,
    description="Data retention and Free Tier usage monitoring",
    schedule=SCHEDULE,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=TAGS,
    doc_md=__doc__,
) as dag:

    calc = PythonOperator(
        task_id="calculate_storage",
        python_callable=calculate_storage,
    )

    archive = PythonOperator(
        task_id="archive_bronze",
        python_callable=archive_bronze,
    )

    cleanup = PythonOperator(
        task_id="cleanup_gcs",
        python_callable=cleanup_gcs,
    )

    verify = PythonOperator(
        task_id="verify_free_tier",
        python_callable=verify_free_tier,
    )

    report = PythonOperator(
        task_id="save_usage_report",
        python_callable=save_usage_report,
        trigger_rule="all_done",
    )

    calc >> [archive, cleanup] >> verify >> report
