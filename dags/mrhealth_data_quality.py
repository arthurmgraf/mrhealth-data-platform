"""
MR. Health Data Quality DAG
============================

Executes 6 automated quality checks across all Medallion layers.
Results are saved to mrhealth_monitoring.data_quality_log.

Schedule: Daily at 03:00 BRT (after daily_pipeline completes at 02:00)
Tasks:
    1-6. check_* (parallel) - 6 independent quality checks
    7. save_results          - Persist results to BigQuery
    8. alert_on_failures     - Alert if any check failed

Author: Arthur Graf
Date: February 2026
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from airflow import DAG
from airflow.operators.python import PythonOperator

from mrhealth.callbacks.alerts import on_task_failure
from mrhealth.config.loader import get_project_id

logger = logging.getLogger(__name__)

DAG_ID = "mrhealth_data_quality"
SCHEDULE = "0 3 * * *"
TAGS = ["mrhealth", "quality", "monitoring"]

CHECK_NAMES = [
    "freshness",
    "completeness",
    "accuracy",
    "uniqueness",
    "referential_integrity",
    "volume_anomaly",
]


def run_quality_check(check_name: str, **context: Any) -> dict[str, Any]:
    """Execute a single quality check and return the result via XCom."""
    from mrhealth.quality.checks import DataQualityChecker

    project_id = get_project_id()
    ds = context["ds"]

    checker = DataQualityChecker(
        project_id=project_id,
        execution_date=datetime.strptime(ds, "%Y-%m-%d").date(),
    )

    check_method = getattr(checker, f"check_{check_name}")
    result = check_method()

    logger.info(
        "[%s] %s: %s (actual=%s)",
        result.result.upper(),
        result.check_name,
        result.check_category,
        result.actual_value,
    )

    return {
        "check_name": result.check_name,
        "result": result.result,
        "actual_value": result.actual_value,
    }


def save_all_results(**context: Any) -> None:
    """Run all checks and save results to BigQuery."""
    from mrhealth.quality.checks import DataQualityChecker

    project_id = get_project_id()
    ds = context["ds"]
    dag_run_id = context["run_id"]

    checker = DataQualityChecker(
        project_id=project_id,
        execution_date=datetime.strptime(ds, "%Y-%m-%d").date(),
    )
    checker.run_all_checks()
    saved = checker.save_results(dag_run_id=dag_run_id)
    logger.info("Saved %d quality check results to BigQuery.", saved)


def alert_on_failures(**context: Any) -> None:
    """Check results and alert if any check failed."""
    from mrhealth.quality.checks import DataQualityChecker

    project_id = get_project_id()
    ds = context["ds"]

    checker = DataQualityChecker(
        project_id=project_id,
        execution_date=datetime.strptime(ds, "%Y-%m-%d").date(),
    )
    results = checker.run_all_checks()

    failures = [r for r in results if r.result == "fail"]
    if failures:
        for f in failures:
            logger.error(
                "QUALITY FAILURE: %s - expected %s, got %s",
                f.check_name,
                f.expected_value,
                f.actual_value,
            )
    else:
        logger.info("All %d quality checks PASSED.", len(results))


default_args = {
    "owner": "mrhealth-data-team",
    "depends_on_past": False,
    "email_on_failure": True,
    "email": ["alerts@mrhealth.local"],
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(minutes=20),
    "on_failure_callback": on_task_failure,
}

with DAG(
    dag_id=DAG_ID,
    default_args=default_args,
    description="Data quality checks across all Medallion layers",
    schedule=SCHEDULE,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=TAGS,
    doc_md=__doc__,
) as dag:

    check_tasks = []
    for check_name in CHECK_NAMES:
        task = PythonOperator(
            task_id=f"check_{check_name}",
            python_callable=run_quality_check,
            op_kwargs={"check_name": check_name},
        )
        check_tasks.append(task)

    save = PythonOperator(
        task_id="save_results",
        python_callable=save_all_results,
    )

    alert = PythonOperator(
        task_id="alert_on_failures",
        python_callable=alert_on_failures,
        trigger_rule="all_done",
    )

    check_tasks >> save >> alert
