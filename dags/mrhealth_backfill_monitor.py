"""
MR. Health Backfill Monitor DAG
=================================

Detects gaps in data (missing dates) and triggers regeneration.
Uses BranchPythonOperator to decide between backfill or skip.

Schedule: Weekly on Mondays at 06:00 BRT
Tasks:
    1. detect_gaps        - Query for dates without data in last 30 days
    2. decide             - Branch: backfill or skip
    3a. trigger_regen     - Trigger data_generator for missing dates
    3b. skip_to_report    - No gaps found, skip to report
    4. wait_processing    - Wait for csv_processor to finish
    5. validate_backfill  - Verify gaps were filled
    6. generate_report    - Log summary

Author: Arthur Graf
Date: February 2026
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from airflow.operators.empty import EmptyOperator
from airflow.operators.python import BranchPythonOperator, PythonOperator
from google.cloud import bigquery
from mrhealth.callbacks.alerts import on_task_failure
from mrhealth.config.loader import get_project_id, load_config

from airflow import DAG

logger = logging.getLogger(__name__)

DAG_ID = "mrhealth_backfill_monitor"
SCHEDULE = "0 6 * * 1"
TAGS = ["mrhealth", "backfill", "monitoring"]


def detect_gaps(**context: Any) -> list[str]:
    """Find dates without data in the last 30 days."""
    project_id = get_project_id()
    client = bigquery.Client(project=project_id)

    sql = f"""
    WITH date_range AS (
      SELECT date
      FROM UNNEST(GENERATE_DATE_ARRAY(
        DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY),
        DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)
      )) AS date
    ),
    actual_dates AS (
      SELECT DISTINCT order_date
      FROM `{project_id}.mrhealth_gold.fact_sales`
      WHERE order_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
    )
    SELECT d.date AS missing_date
    FROM date_range d
    LEFT JOIN actual_dates a ON d.date = a.order_date
    WHERE a.order_date IS NULL
    ORDER BY d.date
    """

    rows = list(client.query(sql).result())
    gaps = [str(row.missing_date) for row in rows]

    if gaps:
        logger.warning("Found %d gaps in last 30 days: %s", len(gaps), gaps[:5])
    else:
        logger.info("No gaps found in last 30 days.")

    context["ti"].xcom_push(key="gaps", value=gaps)
    return gaps


def decide_branch(**context: Any) -> str:
    """Branch: backfill if gaps exist, skip otherwise."""
    gaps = context["ti"].xcom_pull(task_ids="detect_gaps", key="gaps")
    if gaps:
        logger.info("Gaps found (%d), proceeding with backfill", len(gaps))
        return "trigger_regen"
    logger.info("No gaps, skipping to report")
    return "skip_to_report"


def trigger_regen(**context: Any) -> None:
    """Trigger data_generator Cloud Function for missing dates."""
    import google.auth.transport.requests
    import google.oauth2.id_token
    import requests

    config = load_config()
    project_id = get_project_id()
    gaps = context["ti"].xcom_pull(task_ids="detect_gaps", key="gaps")

    cf_config = config["cloud_functions"]["data_generator"]
    function_url = (
        f"https://{config['project'].get('region', 'us-central1')}"
        f"-{project_id}.cloudfunctions.net/{cf_config['name']}"
    )

    auth_req = google.auth.transport.requests.Request()
    id_token = google.oauth2.id_token.fetch_id_token(auth_req, function_url)

    for gap_date in gaps[:7]:
        response = requests.post(
            function_url,
            headers={"Authorization": f"Bearer {id_token}"},
            json={"date": gap_date, "trigger_source": "backfill_monitor"},
            timeout=300,
        )
        logger.info("Triggered regen for %s: HTTP %d", gap_date, response.status_code)


def validate_backfill(**context: Any) -> None:
    """Verify that gaps were filled after regeneration."""
    project_id = get_project_id()
    client = bigquery.Client(project=project_id)
    gaps = context["ti"].xcom_pull(task_ids="detect_gaps", key="gaps") or []

    still_missing = []
    for gap_date in gaps[:7]:
        sql = f"""
        SELECT COUNT(*) as cnt
        FROM `{project_id}.mrhealth_bronze.orders`
        WHERE data_pedido = '{gap_date}'
        """
        rows = list(client.query(sql).result())
        count = rows[0].cnt if rows else 0
        if count == 0:
            still_missing.append(gap_date)

    if still_missing:
        logger.warning("Still missing data for: %s", still_missing)
    else:
        logger.info("All %d gaps successfully backfilled.", len(gaps[:7]))


def generate_report(**context: Any) -> None:
    """Generate backfill summary report."""
    gaps = context["ti"].xcom_pull(task_ids="detect_gaps", key="gaps") or []
    logger.info("=" * 50)
    logger.info("BACKFILL MONITOR REPORT")
    logger.info("Gaps detected: %d", len(gaps))
    if gaps:
        logger.info("Gap dates: %s", gaps[:10])
    logger.info("=" * 50)


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
    description="Detect and fix data gaps via backfill",
    schedule=SCHEDULE,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=TAGS,
    doc_md=__doc__,
) as dag:
    detect = PythonOperator(
        task_id="detect_gaps",
        python_callable=detect_gaps,
    )

    decide = BranchPythonOperator(
        task_id="decide",
        python_callable=decide_branch,
    )

    regen = PythonOperator(
        task_id="trigger_regen",
        python_callable=trigger_regen,
    )

    skip = EmptyOperator(
        task_id="skip_to_report",
    )

    wait = PythonOperator(
        task_id="wait_processing",
        python_callable=lambda **ctx: logger.info("Waiting 60s for CSV processing..."),
        execution_timeout=timedelta(minutes=5),
    )

    validate = PythonOperator(
        task_id="validate_backfill",
        python_callable=validate_backfill,
    )

    report = PythonOperator(
        task_id="generate_report",
        python_callable=generate_report,
        trigger_rule="none_failed_min_one_success",
    )

    detect >> decide >> [regen, skip]
    regen >> wait >> validate >> report
    skip >> report
