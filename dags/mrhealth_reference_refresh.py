"""
MR. Health Reference Refresh DAG
==================================

Synchronizes PostgreSQL master data (K3s) to BigQuery Bronze via
the pg-reference-extractor Cloud Function and GCS.

Schedule: Daily at 01:00 BRT (before daily_pipeline at 02:00)
Tasks:
    1. trigger_pg_extraction - HTTP POST to pg-reference-extractor CF
    2. wait_for_gcs_files    - Sensor waits for 4 reference CSVs in GCS
    3. load_to_bronze        - WRITE_TRUNCATE reference tables in Bronze
    4. validate_references   - Check row counts and FK integrity
    5. notify_completion     - Log summary

Author: Arthur Graf
Date: February 2026
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from airflow.operators.python import PythonOperator
from airflow.providers.google.cloud.sensors.gcs import GCSObjectsWithPrefixExistenceSensor
from google.cloud import bigquery
from mrhealth.callbacks.alerts import on_task_failure
from mrhealth.config.loader import get_project_id, load_config

from airflow import DAG

logger = logging.getLogger(__name__)

DAG_ID = "mrhealth_reference_refresh"
SCHEDULE = "0 1 * * *"
TAGS = ["mrhealth", "reference", "postgresql"]

REFERENCE_TABLES = ["products", "units", "states", "countries"]


def trigger_pg_extraction(**context: Any) -> None:
    """Trigger the pg-reference-extractor Cloud Function via HTTP."""
    import google.auth.transport.requests
    import google.oauth2.id_token
    import requests

    config = load_config()
    cf_config = config["cloud_functions"]["pg_reference_extractor"]
    project_id = get_project_id()

    function_url = (
        f"https://{config['project'].get('region', 'us-central1')}"
        f"-{project_id}.cloudfunctions.net/{cf_config['name']}"
    )

    auth_req = google.auth.transport.requests.Request()
    id_token = google.oauth2.id_token.fetch_id_token(auth_req, function_url)

    response = requests.post(
        function_url,
        headers={"Authorization": f"Bearer {id_token}"},
        json={"trigger_source": "airflow_reference_refresh"},
        timeout=300,
    )
    response.raise_for_status()
    logger.info("pg-reference-extractor triggered: %s", response.text[:200])


def load_references_to_bronze(**context: Any) -> None:
    """Load reference CSVs from GCS to BigQuery Bronze with WRITE_TRUNCATE."""
    config = load_config()
    project_id = get_project_id()
    bucket_name = config["storage"]["bucket"]
    client = bigquery.Client(project=project_id)

    for table_name in REFERENCE_TABLES:
        gcs_uri = f"gs://{bucket_name}/raw/reference_data/{table_name}.csv"
        table_id = f"{project_id}.mrhealth_bronze.{table_name}"

        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.CSV,
            skip_leading_rows=1,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
            autodetect=False,
        )

        job = client.load_table_from_uri(gcs_uri, table_id, job_config=job_config)
        job.result()
        logger.info("Loaded %s -> %s (%d rows)", gcs_uri, table_id, job.output_rows or 0)


def validate_references(**context: Any) -> None:
    """Validate reference data: row counts and basic integrity."""
    project_id = get_project_id()
    client = bigquery.Client(project=project_id)

    expected_counts = {
        "products": 30,
        "units": 50,
        "states": 27,
        "countries": 1,
    }

    for table_name, expected in expected_counts.items():
        sql = f"SELECT COUNT(*) as cnt FROM `{project_id}.mrhealth_bronze.{table_name}`"
        rows = list(client.query(sql).result())
        count = rows[0].cnt if rows else 0
        status = "OK" if count >= expected else "WARN"
        logger.info("[%s] bronze.%s: %d rows (expected >= %d)", status, table_name, count, expected)

    fk_sql = f"""
    SELECT COUNT(*) as orphan_units
    FROM `{project_id}.mrhealth_bronze.units` u
    LEFT JOIN `{project_id}.mrhealth_bronze.states` s
      ON u.id_estado = s.id_estado
    WHERE s.id_estado IS NULL
    """
    rows = list(client.query(fk_sql).result())
    orphans = rows[0].orphan_units if rows else -1
    if orphans > 0:
        logger.warning("FK integrity issue: %d units without matching state", orphans)
    else:
        logger.info("FK integrity OK: all units have matching states")


def notify_completion(**context: Any) -> None:
    """Log reference refresh summary."""
    logger.info("=" * 50)
    logger.info("REFERENCE REFRESH COMPLETE")
    logger.info("Tables refreshed: %s", ", ".join(REFERENCE_TABLES))
    logger.info("=" * 50)


default_args = {
    "owner": "mrhealth-data-team",
    "depends_on_past": False,
    "email_on_failure": True,
    "email": ["alerts@mrhealth.local"],
    "retries": 3,
    "retry_delay": timedelta(minutes=10),
    "execution_timeout": timedelta(minutes=20),
    "on_failure_callback": on_task_failure,
}

with DAG(
    dag_id=DAG_ID,
    default_args=default_args,
    description="Sync PostgreSQL reference data to BigQuery Bronze",
    schedule=SCHEDULE,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=TAGS,
    doc_md=__doc__,
) as dag:
    _config = load_config()
    _bucket = _config["storage"]["bucket"]

    trigger = PythonOperator(
        task_id="trigger_pg_extraction",
        python_callable=trigger_pg_extraction,
    )

    wait_gcs = GCSObjectsWithPrefixExistenceSensor(
        task_id="wait_for_gcs_files",
        bucket=_bucket,
        prefix="raw/reference_data/",
        timeout=600,
        poke_interval=30,
        mode="poke",
    )

    load = PythonOperator(
        task_id="load_to_bronze",
        python_callable=load_references_to_bronze,
    )

    validate = PythonOperator(
        task_id="validate_references",
        python_callable=validate_references,
    )

    notify = PythonOperator(
        task_id="notify_completion",
        python_callable=notify_completion,
        trigger_rule="all_done",
    )

    trigger >> wait_gcs >> load >> validate >> notify
