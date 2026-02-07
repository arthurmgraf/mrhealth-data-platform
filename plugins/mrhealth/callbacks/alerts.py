"""
Airflow Alert Callbacks
========================
Callbacks for SLA miss, task failure, and quality failure.
In production, these would send to Slack/PagerDuty.
Here they log to Airflow + save metrics to BigQuery pipeline_metrics.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from google.cloud import bigquery

logger = logging.getLogger(__name__)

_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "")


def _save_metric(
    project_id: str,
    dag_id: str,
    metric_name: str,
    metric_value: float,
    metric_unit: str,
    details: dict[str, Any] | None = None,
    dag_run_id: str = "",
    task_id: str = "",
) -> None:
    client = bigquery.Client(project=project_id)
    table_id = f"{project_id}.mrhealth_monitoring.pipeline_metrics"
    now = datetime.now(timezone.utc)
    rows = [{
        "metric_id": str(uuid.uuid4())[:12],
        "dag_id": dag_id,
        "dag_run_id": dag_run_id,
        "task_id": task_id,
        "metric_name": metric_name,
        "metric_value": metric_value,
        "metric_unit": metric_unit,
        "execution_date": now.strftime("%Y-%m-%d"),
        "execution_timestamp": now.isoformat(),
        "details": json.dumps(details or {}),
    }]
    errors = client.insert_rows_json(table_id, rows)
    if errors:
        logger.error("Erro ao salvar metrica: %s", errors)


def on_sla_miss(
    dag: Any,
    task_list: Any,
    blocking_task_list: Any,
    slas: Any,
    blocking_tis: Any,
) -> None:
    """Callback when SLA is violated (pipeline > 30 min)."""
    dag_id = dag.dag_id if dag else "unknown"
    task_names = [t.task_id for t in task_list] if task_list else []
    blocking_names = [t.task_id for t in blocking_task_list] if blocking_task_list else []

    logger.error(
        "SLA MISS! DAG: %s | Tasks: %s | Blocking: %s",
        dag_id,
        task_names,
        blocking_names,
    )

    try:
        _save_metric(
            project_id=_PROJECT_ID,
            dag_id=dag_id,
            metric_name="sla_miss",
            metric_value=1.0,
            metric_unit="event",
            details={
                "tasks": task_names,
                "blocking_tasks": blocking_names,
            },
        )
    except Exception as e:
        logger.error("Falha ao salvar SLA miss metric: %s", e)


def on_task_failure(context: dict[str, Any]) -> None:
    """Callback when any task fails."""
    ti = context.get("task_instance")
    dag_id = ti.dag_id if ti else "unknown"
    task_id = ti.task_id if ti else "unknown"
    exception = context.get("exception", "unknown")

    logger.error(
        "TASK FAILURE! DAG: %s | Task: %s | Error: %s",
        dag_id,
        task_id,
        exception,
    )

    try:
        _save_metric(
            project_id=_PROJECT_ID,
            dag_id=dag_id,
            metric_name="task_failure",
            metric_value=1.0,
            metric_unit="event",
            task_id=task_id,
            dag_run_id=context.get("run_id", ""),
            details={"error": str(exception)[:500]},
        )
    except Exception as e:
        logger.error("Falha ao salvar task failure metric: %s", e)


def on_quality_failure(
    failures: list[Any],
    context: dict[str, Any],
) -> None:
    """Callback when quality checks fail."""
    dag_id = context.get("dag", {}).dag_id if context.get("dag") else "unknown"

    for f in failures:
        logger.error(
            "QUALITY FAILURE: %s - expected %s, got %s",
            f.check_name,
            f.expected_value,
            f.actual_value,
        )

    try:
        _save_metric(
            project_id=_PROJECT_ID,
            dag_id=dag_id,
            metric_name="quality_failure",
            metric_value=float(len(failures)),
            metric_unit="checks",
            dag_run_id=context.get("run_id", ""),
            details={
                "failed_checks": [f.check_name for f in failures],
            },
        )
    except Exception as e:
        logger.error("Falha ao salvar quality failure metric: %s", e)
