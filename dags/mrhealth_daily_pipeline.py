"""
MR. Health Daily Pipeline DAG
==============================

Orchestrates the full Medallion pipeline: Bronze -> Silver -> Gold.

Schedule: Daily at 02:00 BRT (after CSV files arrive at midnight)
Tasks:
    1. sense_new_files   - Wait for new CSV files in GCS
    2. validate_bronze   - Verify Bronze layer has data for today
    3. build_silver      - Execute Silver SQL transformations
    4. build_dims        - Build Gold dimension tables (parallel)
    5. build_facts       - Build Gold fact tables (parallel)
    6. build_aggs        - Build pre-aggregated KPI tables
    7. validate_gold     - Verify Gold layer has rows
    8. notify_completion - Log pipeline summary

Author: Arthur Graf
Date: February 2026
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import yaml
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.google.cloud.operators.bigquery import (
    BigQueryCheckOperator,
)
from airflow.providers.google.cloud.sensors.gcs import (
    GCSObjectsWithPrefixSensor,
)
from google.cloud import bigquery

logger = logging.getLogger(__name__)

DAG_ID = "mrhealth_daily_pipeline"
SCHEDULE = "0 2 * * *"
TAGS = ["mrhealth", "pipeline", "medallion"]

CONFIG_PATH = Path(os.environ.get("MRHEALTH_CONFIG_PATH", "/opt/airflow/config/project_config.yaml"))
SQL_BASE = Path(os.environ.get("MRHEALTH_SQL_PATH", "/opt/airflow/sql"))


def _load_project_config() -> dict[str, Any]:
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


def _get_bq_client(project_id: str) -> bigquery.Client:
    return bigquery.Client(project=project_id)


def _execute_sql_files(
    client: bigquery.Client,
    sql_files: list[tuple[Path, str]],
) -> None:
    for sql_path, description in sql_files:
        logger.info("Executing: %s (%s)", description, sql_path.name)
        sql = sql_path.read_text(encoding="utf-8")
        job = client.query(sql)
        job.result()
        bytes_billed = job.total_bytes_billed or 0
        logger.info(
            "  OK: %s (billed: %s bytes)", sql_path.name, f"{bytes_billed:,}"
        )


def run_silver_transforms(**context: Any) -> None:
    config = _load_project_config()
    client = _get_bq_client(config["project"]["id"])
    sql_files = [
        (SQL_BASE / "silver" / "01_reference_tables.sql", "Reference tables"),
        (SQL_BASE / "silver" / "02_orders.sql", "Orders"),
        (SQL_BASE / "silver" / "03_order_items.sql", "Order items"),
    ]
    _execute_sql_files(client, sql_files)
    logger.info("Silver layer complete.")


def run_gold_dimensions(**context: Any) -> None:
    config = _load_project_config()
    client = _get_bq_client(config["project"]["id"])
    sql_files = [
        (SQL_BASE / "gold" / "01_dim_date.sql", "dim_date"),
        (SQL_BASE / "gold" / "02_dim_product.sql", "dim_product"),
        (SQL_BASE / "gold" / "03_dim_unit.sql", "dim_unit"),
        (SQL_BASE / "gold" / "04_dim_geography.sql", "dim_geography"),
    ]
    _execute_sql_files(client, sql_files)
    logger.info("Gold dimensions complete.")


def run_gold_facts(**context: Any) -> None:
    config = _load_project_config()
    client = _get_bq_client(config["project"]["id"])
    sql_files = [
        (SQL_BASE / "gold" / "05_fact_sales.sql", "fact_sales"),
        (SQL_BASE / "gold" / "06_fact_order_items.sql", "fact_order_items"),
    ]
    _execute_sql_files(client, sql_files)
    logger.info("Gold facts complete.")


def run_aggregations(**context: Any) -> None:
    config = _load_project_config()
    client = _get_bq_client(config["project"]["id"])
    sql_files = [
        (SQL_BASE / "gold" / "07_agg_daily_sales.sql", "agg_daily_sales"),
        (SQL_BASE / "gold" / "08_agg_unit_performance.sql", "agg_unit_performance"),
        (SQL_BASE / "gold" / "09_agg_product_performance.sql", "agg_product_performance"),
    ]
    _execute_sql_files(client, sql_files)
    logger.info("Aggregations complete.")


def notify_pipeline_completion(**context: Any) -> None:
    config = _load_project_config()
    project_id = config["project"]["id"]
    client = _get_bq_client(project_id)

    tables_to_check = [
        f"{project_id}.case_ficticio_silver.orders",
        f"{project_id}.case_ficticio_gold.fact_sales",
        f"{project_id}.case_ficticio_gold.agg_daily_sales",
    ]

    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETE - Summary")
    logger.info("=" * 60)

    for table_id in tables_to_check:
        try:
            result = client.query(
                f"SELECT COUNT(*) AS cnt FROM `{table_id}`"
            ).result()
            count = list(result)[0].cnt
            logger.info("  %s: %s rows", table_id.split(".")[-1], f"{count:,}")
        except Exception as e:
            logger.warning("  %s: ERROR - %s", table_id, e)

    logger.info("=" * 60)


default_args = {
    "owner": "mrhealth-data-team",
    "depends_on_past": False,
    "email_on_failure": True,
    "email_on_retry": False,
    "email": ["alerts@mrhealth.local"],
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(minutes=30),
}

with DAG(
    dag_id=DAG_ID,
    default_args=default_args,
    description="Daily Medallion pipeline: Bronze -> Silver -> Gold",
    schedule=SCHEDULE,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=TAGS,
    doc_md=__doc__,
) as dag:

    _config = _load_project_config()
    _bucket = _config["storage"]["bucket"]
    _project = _config["project"]["id"]

    sense_new_files = GCSObjectsWithPrefixSensor(
        task_id="sense_new_files",
        bucket=_bucket,
        prefix="raw/csv_sales/{{ ds_nodash[:4] }}/{{ ds_nodash[4:6] }}/{{ ds_nodash[6:8] }}",
        timeout=3600,
        poke_interval=120,
        mode="poke",
        soft_fail=True,
    )

    validate_bronze = BigQueryCheckOperator(
        task_id="validate_bronze",
        sql=f"SELECT COUNT(*) > 0 FROM `{_project}.case_ficticio_bronze.orders`",
        use_legacy_sql=False,
    )

    build_silver = PythonOperator(
        task_id="build_silver",
        python_callable=run_silver_transforms,
    )

    build_dims = PythonOperator(
        task_id="build_gold_dimensions",
        python_callable=run_gold_dimensions,
    )

    build_facts = PythonOperator(
        task_id="build_gold_facts",
        python_callable=run_gold_facts,
    )

    build_aggs = PythonOperator(
        task_id="build_aggregations",
        python_callable=run_aggregations,
    )

    validate_gold = BigQueryCheckOperator(
        task_id="validate_gold",
        sql=f"SELECT COUNT(*) > 0 FROM `{_project}.case_ficticio_gold.fact_sales`",
        use_legacy_sql=False,
    )

    notify = PythonOperator(
        task_id="notify_completion",
        python_callable=notify_pipeline_completion,
        trigger_rule="all_done",
    )

    sense_new_files >> validate_bronze >> build_silver
    build_silver >> [build_dims, build_facts]
    [build_dims, build_facts] >> build_aggs >> validate_gold >> notify
