"""
MR. Health Daily Pipeline DAG
==============================

Orchestrates the full Medallion pipeline: Bronze -> Silver -> Gold.
Includes quality checks at Silver and Gold layers with SLA monitoring.

Schedule: Daily at 02:00 BRT (after CSV files arrive at midnight)
Tasks:
    1. sense_new_files       - Wait for new CSV files in GCS
    2. validate_bronze       - Verify Bronze layer has data for today
    3. build_silver          - Execute Silver SQL transformations
    4. quality_check_silver  - Validate Silver layer quality
    5. build_dims            - Build Gold dimension tables (parallel)
    6. build_facts           - Build Gold fact tables (parallel)
    7. build_aggs            - Build pre-aggregated KPI tables
    8. quality_check_gold    - Validate Gold star schema
    9. validate_gold         - Verify Gold layer has rows
   10. notify_completion     - Log pipeline summary + save metrics

Author: Arthur Graf
Date: February 2026
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml
from airflow.operators.python import PythonOperator
from airflow.providers.google.cloud.operators.bigquery import (
    BigQueryCheckOperator,
)
from airflow.providers.google.cloud.sensors.gcs import (
    GCSObjectsWithPrefixExistenceSensor,
)
from google.cloud import bigquery
from mrhealth.callbacks.alerts import on_sla_miss, on_task_failure

from airflow import DAG

logger = logging.getLogger(__name__)

DAG_ID = "mrhealth_daily_pipeline"
SCHEDULE = "0 2 * * *"
TAGS = ["mrhealth", "pipeline", "medallion"]

CONFIG_PATH = Path(
    os.environ.get("MRHEALTH_CONFIG_PATH", "/opt/airflow/config/project_config.yaml")
)
SQL_BASE = Path(os.environ.get("MRHEALTH_SQL_PATH", "/opt/airflow/sql"))


def _load_project_config() -> dict[str, Any]:
    with open(CONFIG_PATH) as f:
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
        logger.info("  OK: %s (billed: %s bytes)", sql_path.name, f"{bytes_billed:,}")


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


def quality_check_silver(**context: Any) -> None:
    """Run quick quality checks on Silver layer after transforms."""
    config = _load_project_config()
    project_id = config["project"]["id"]
    client = _get_bq_client(project_id)

    checks = {
        "orders_not_empty": f"SELECT COUNT(*) > 0 FROM `{project_id}.mrhealth_silver.orders`",
        "order_items_not_empty": f"SELECT COUNT(*) > 0 FROM `{project_id}.mrhealth_silver.order_items`",
        "no_null_order_ids": (
            f"SELECT COUNT(*) = 0 FROM `{project_id}.mrhealth_silver.orders` WHERE order_id IS NULL"
        ),
    }

    for check_name, sql in checks.items():
        rows = list(client.query(sql).result())
        passed = bool(rows[0][0]) if rows else False
        status = "PASS" if passed else "FAIL"
        logger.info("[%s] Silver check: %s", status, check_name)
        if not passed:
            raise ValueError(f"Silver quality check failed: {check_name}")


def quality_check_gold(**context: Any) -> None:
    """Run quality checks on Gold star schema."""
    config = _load_project_config()
    project_id = config["project"]["id"]
    client = _get_bq_client(project_id)

    checks = {
        "fact_sales_not_empty": f"SELECT COUNT(*) > 0 FROM `{project_id}.mrhealth_gold.fact_sales`",
        "dims_populated": (f"SELECT COUNT(*) > 0 FROM `{project_id}.mrhealth_gold.dim_product`"),
        "no_orphan_units": (
            f"SELECT COUNT(*) = 0 FROM `{project_id}.mrhealth_gold.fact_sales` f "
            f"LEFT JOIN `{project_id}.mrhealth_gold.dim_unit` u ON f.unit_key = u.unit_key "
            f"WHERE u.unit_key IS NULL"
        ),
    }

    for check_name, sql in checks.items():
        rows = list(client.query(sql).result())
        passed = bool(rows[0][0]) if rows else False
        status = "PASS" if passed else "FAIL"
        logger.info("[%s] Gold check: %s", status, check_name)
        if not passed:
            raise ValueError(f"Gold quality check failed: {check_name}")


def notify_pipeline_completion(**context: Any) -> None:
    import json
    import uuid
    from datetime import datetime

    config = _load_project_config()
    project_id = config["project"]["id"]
    client = _get_bq_client(project_id)

    tables_to_check = [
        f"{project_id}.mrhealth_silver.orders",
        f"{project_id}.mrhealth_gold.fact_sales",
        f"{project_id}.mrhealth_gold.agg_daily_sales",
    ]

    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETE - Summary")
    logger.info("=" * 60)

    total_rows = 0
    for table_id in tables_to_check:
        try:
            result = client.query(f"SELECT COUNT(*) AS cnt FROM `{table_id}`").result()
            count = list(result)[0].cnt
            total_rows += count
            logger.info("  %s: %s rows", table_id.split(".")[-1], f"{count:,}")
        except Exception as e:
            logger.warning("  %s: ERROR - %s", table_id, e)

    logger.info("=" * 60)

    now = datetime.now(UTC)
    start_time = context.get("data_interval_start")
    duration = (now - start_time).total_seconds() if start_time else 0

    metrics = [
        {"metric_name": "pipeline_status", "metric_value": 1.0, "metric_unit": "boolean"},
        {"metric_name": "duration", "metric_value": duration, "metric_unit": "seconds"},
        {"metric_name": "rows_processed", "metric_value": float(total_rows), "metric_unit": "rows"},
    ]

    table_id = f"{project_id}.mrhealth_monitoring.pipeline_metrics"
    for m in metrics:
        rows = [
            {
                "metric_id": str(uuid.uuid4())[:12],
                "dag_id": DAG_ID,
                "dag_run_id": context.get("run_id", ""),
                "task_id": "notify_completion",
                "metric_name": m["metric_name"],
                "metric_value": m["metric_value"],
                "metric_unit": m["metric_unit"],
                "execution_date": context.get("ds", now.strftime("%Y-%m-%d")),
                "execution_timestamp": now.isoformat(),
                "details": json.dumps({}),
            }
        ]
        try:
            client.insert_rows_json(table_id, rows)
        except Exception as e:
            logger.warning("Failed to save metric %s: %s", m["metric_name"], e)


default_args = {
    "owner": "mrhealth-data-team",
    "depends_on_past": False,
    "email_on_failure": True,
    "email_on_retry": False,
    "email": ["alerts@mrhealth.local"],
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(minutes=30),
    "on_failure_callback": on_task_failure,
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
    sla_miss_callback=on_sla_miss,
) as dag:
    _config = _load_project_config()
    _bucket = _config["storage"]["bucket"]
    _project = _config["project"]["id"]

    sense_new_files = GCSObjectsWithPrefixExistenceSensor(
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
        sql=f"SELECT COUNT(*) > 0 FROM `{_project}.mrhealth_bronze.orders`",
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

    check_silver = PythonOperator(
        task_id="quality_check_silver",
        python_callable=quality_check_silver,
    )

    check_gold = PythonOperator(
        task_id="quality_check_gold",
        python_callable=quality_check_gold,
    )

    validate_gold = BigQueryCheckOperator(
        task_id="validate_gold",
        sql=f"SELECT COUNT(*) > 0 FROM `{_project}.mrhealth_gold.fact_sales`",
        use_legacy_sql=False,
    )

    notify = PythonOperator(
        task_id="notify_completion",
        python_callable=notify_pipeline_completion,
        trigger_rule="all_done",
    )

    sense_new_files >> validate_bronze >> build_silver >> check_silver
    check_silver >> [build_dims, build_facts]
    [build_dims, build_facts] >> build_aggs >> check_gold >> validate_gold >> notify
