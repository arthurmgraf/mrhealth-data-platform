"""
BigQuery Freshness Sensor
===========================
Custom Sensor that waits until fresh data exists in a BigQuery table.
More semantic than BigQueryCheckOperator for freshness verification.
"""

from __future__ import annotations

import logging
from typing import Any

from airflow.sensors.base import BaseSensorOperator
from google.cloud import bigquery

logger = logging.getLogger(__name__)


class BigQueryFreshnessSensor(BaseSensorOperator):
    """Sensor that waits until data exists for a target date."""

    template_fields = ("target_date", "project_id", "dataset", "table")
    ui_color = "#2f9e44"
    ui_fgcolor = "#ffffff"

    def __init__(
        self,
        *,
        project_id: str,
        dataset: str,
        table: str,
        date_column: str = "order_date",
        target_date: str = "{{ ds }}",
        min_row_count: int = 1,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.project_id = project_id
        self.dataset = dataset
        self.table = table
        self.date_column = date_column
        self.target_date = target_date
        self.min_row_count = min_row_count

    def poke(self, context: dict[str, Any]) -> bool:
        client = bigquery.Client(project=self.project_id)
        sql = f"""
        SELECT COUNT(*) as cnt
        FROM `{self.project_id}.{self.dataset}.{self.table}`
        WHERE {self.date_column} = '{self.target_date}'
        """
        job = client.query(sql)
        rows = list(job.result())
        count = rows[0].cnt if rows else 0

        logger.info(
            "BigQueryFreshnessSensor: %s.%s has %d rows for %s (need >= %d)",
            self.dataset,
            self.table,
            count,
            self.target_date,
            self.min_row_count,
        )

        return count >= self.min_row_count
