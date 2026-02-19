"""
BigQuery Data Quality Operator
================================
Custom Airflow Operator that executes a SQL quality check against BigQuery,
evaluates the result, and optionally records it in the monitoring table.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from airflow.models import BaseOperator
from google.cloud import bigquery

logger = logging.getLogger(__name__)


class BigQueryDataQualityOperator(BaseOperator):
    """Executa um SQL check de qualidade no BigQuery e registra o resultado."""

    template_fields = ("sql", "project_id", "check_name")
    ui_color = "#4285F4"
    ui_fgcolor = "#ffffff"

    def __init__(
        self,
        *,
        check_name: str,
        check_category: str,
        sql: str,
        project_id: str,
        expected_result: bool = True,
        layer: str = "gold",
        table_name: str = "",
        save_to_monitoring: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.check_name = check_name
        self.check_category = check_category
        self.sql = sql
        self.project_id = project_id
        self.expected_result = expected_result
        self.layer = layer
        self.table_name = table_name
        self.save_to_monitoring = save_to_monitoring

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        client = bigquery.Client(project=self.project_id)
        start = time.time()

        job = client.query(self.sql)
        rows = list(job.result())
        duration = round(time.time() - start, 2)

        check_passed = bool(rows[0][0]) if rows else False

        result = "pass" if check_passed == self.expected_result else "fail"

        logger.info(
            "[%s] %s: %s (duration=%.2fs)",
            result.upper(),
            self.check_name,
            self.check_category,
            duration,
        )

        result_dict = {
            "check_name": self.check_name,
            "check_category": self.check_category,
            "result": result,
            "duration_seconds": duration,
        }

        if self.save_to_monitoring:
            self._save_result(client, result, duration, context)

        return result_dict

    def _save_result(
        self,
        client: bigquery.Client,
        result: str,
        duration: float,
        context: dict[str, Any],
    ) -> None:
        table_id = f"{self.project_id}.mrhealth_monitoring.data_quality_log"
        rows = [
            {
                "check_id": str(uuid.uuid4())[:12],
                "check_name": self.check_name,
                "check_category": self.check_category,
                "layer": self.layer,
                "table_name": self.table_name,
                "check_sql": self.sql[:4000],
                "result": result,
                "expected_value": str(self.expected_result),
                "actual_value": result,
                "details": json.dumps({}),
                "execution_date": context["ds"],
                "execution_timestamp": datetime.now(UTC).isoformat(),
                "dag_run_id": context.get("run_id", ""),
                "duration_seconds": duration,
            }
        ]
        errors = client.insert_rows_json(table_id, rows)
        if errors:
            logger.error("Erro ao salvar resultado: %s", errors)
