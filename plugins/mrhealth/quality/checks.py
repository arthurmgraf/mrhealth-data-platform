"""
MR. HEALTH Data Quality Framework
===================================
Custom SQL-based quality checks for the Medallion pipeline.
Each check returns a DataQualityResult saved to BigQuery monitoring.

Usage:
    checker = DataQualityChecker(project_id="your-project-id")
    results = checker.run_all_checks()
    checker.save_results(dag_run_id="manual__2026-02-05")
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from google.cloud import bigquery

logger = logging.getLogger(__name__)


@dataclass
class DataQualityResult:
    """Resultado de um check de qualidade."""

    check_name: str
    check_category: str
    layer: str
    table_name: str
    check_sql: str
    result: str
    expected_value: str
    actual_value: str
    details: dict[str, Any] = field(default_factory=dict)
    duration_seconds: float = 0.0

    @property
    def passed(self) -> bool:
        return self.result == "pass"

    @property
    def failed(self) -> bool:
        return self.result == "fail"


class DataQualityChecker:
    """Executa e registra checks de qualidade no BigQuery."""

    MONITORING_DATASET = "mrhealth_monitoring"
    QUALITY_TABLE = "data_quality_log"

    def __init__(
        self,
        project_id: str,
        execution_date: date | None = None,
    ) -> None:
        self.project_id = project_id
        self.client = bigquery.Client(project=project_id)
        self.execution_date = execution_date or date.today()
        self.results: list[DataQualityResult] = []

    def _run_query(self, sql: str) -> list[dict[str, Any]]:
        job = self.client.query(sql)
        return [dict(row) for row in job.result()]

    def check_freshness(self) -> DataQualityResult:
        """Verifica se existem dados de hoje em fact_sales."""
        sql = f"""
        SELECT COUNT(*) as cnt
        FROM `{self.project_id}.mrhealth_gold.fact_sales`
        WHERE order_date = '{self.execution_date}'
        """
        start = time.time()
        rows = self._run_query(sql)
        count = rows[0]["cnt"] if rows else 0
        result = "pass" if count > 0 else "fail"
        return DataQualityResult(
            check_name="freshness_fact_sales",
            check_category="freshness",
            layer="gold",
            table_name="fact_sales",
            check_sql=sql.strip(),
            result=result,
            expected_value=">0",
            actual_value=str(count),
            details={"date_checked": str(self.execution_date)},
            duration_seconds=round(time.time() - start, 2),
        )

    def check_completeness(self, expected_units: int = 50) -> DataQualityResult:
        """Verifica se todas as unidades reportaram dados."""
        sql = f"""
        SELECT COUNT(DISTINCT unit_key) as active_units
        FROM `{self.project_id}.mrhealth_gold.fact_sales`
        WHERE order_date = '{self.execution_date}'
        """
        start = time.time()
        rows = self._run_query(sql)
        count = rows[0]["active_units"] if rows else 0
        result = (
            "pass"
            if count >= expected_units
            else ("warn" if count >= expected_units * 0.9 else "fail")
        )
        return DataQualityResult(
            check_name="completeness_all_units",
            check_category="completeness",
            layer="gold",
            table_name="fact_sales",
            check_sql=sql.strip(),
            result=result,
            expected_value=str(expected_units),
            actual_value=str(count),
            details={"missing_units": expected_units - count},
            duration_seconds=round(time.time() - start, 2),
        )

    def check_accuracy(self) -> DataQualityResult:
        """Verifica se totais de items_subtotal batem entre Silver e Gold."""
        sql = f"""
        WITH silver_total AS (
          SELECT ROUND(SUM(unit_price * quantity), 2) as total
          FROM `{self.project_id}.mrhealth_silver.order_items`
        ),
        gold_total AS (
          SELECT ROUND(SUM(items_subtotal), 2) as total
          FROM `{self.project_id}.mrhealth_gold.fact_sales`
        )
        SELECT
          s.total as silver_total,
          g.total as gold_total,
          ABS(COALESCE(s.total, 0) - COALESCE(g.total, 0)) as diff
        FROM silver_total s, gold_total g
        """
        start = time.time()
        rows = self._run_query(sql)
        diff = rows[0]["diff"] if rows else -1
        result = "pass" if diff < 0.01 else ("warn" if diff < 1.0 else "fail")
        return DataQualityResult(
            check_name="accuracy_cross_layer_totals",
            check_category="accuracy",
            layer="gold",
            table_name="fact_sales",
            check_sql=sql.strip(),
            result=result,
            expected_value="diff < 0.01",
            actual_value=str(diff),
            details={
                "silver_total": str(rows[0]["silver_total"]) if rows else "N/A",
                "gold_total": str(rows[0]["gold_total"]) if rows else "N/A",
            },
            duration_seconds=round(time.time() - start, 2),
        )

    def check_uniqueness(self) -> DataQualityResult:
        """Verifica ausencia de order_id duplicados em Gold."""
        sql = f"""
        SELECT order_id, COUNT(*) as cnt
        FROM `{self.project_id}.mrhealth_gold.fact_sales`
        GROUP BY order_id
        HAVING cnt > 1
        LIMIT 10
        """
        start = time.time()
        rows = self._run_query(sql)
        dup_count = len(rows)
        result = "pass" if dup_count == 0 else "fail"
        return DataQualityResult(
            check_name="uniqueness_order_id",
            check_category="uniqueness",
            layer="gold",
            table_name="fact_sales",
            check_sql=sql.strip(),
            result=result,
            expected_value="0 duplicates",
            actual_value=f"{dup_count} duplicates found",
            details={"sample_duplicates": [r["order_id"] for r in rows[:5]]},
            duration_seconds=round(time.time() - start, 2),
        )

    def check_referential_integrity(self) -> DataQualityResult:
        """Verifica se todos os product_key em fact_order_items existem em dim_product."""
        sql = f"""
        SELECT COUNT(*) as orphan_count
        FROM `{self.project_id}.mrhealth_gold.fact_order_items` f
        LEFT JOIN `{self.project_id}.mrhealth_gold.dim_product` p
          ON f.product_key = p.product_key
        WHERE p.product_key IS NULL
        """
        start = time.time()
        rows = self._run_query(sql)
        orphans = rows[0]["orphan_count"] if rows else -1
        result = "pass" if orphans == 0 else "fail"
        return DataQualityResult(
            check_name="referential_integrity_product",
            check_category="referential",
            layer="gold",
            table_name="fact_order_items",
            check_sql=sql.strip(),
            result=result,
            expected_value="0 orphans",
            actual_value=f"{orphans} orphan records",
            duration_seconds=round(time.time() - start, 2),
        )

    def check_volume_anomaly(self, std_dev_threshold: float = 2.0) -> DataQualityResult:
        """Detecta se o volume de hoje esta fora do padrao (>2 desvios padrao)."""
        sql = f"""
        WITH daily_counts AS (
          SELECT order_date, COUNT(*) as daily_orders
          FROM `{self.project_id}.mrhealth_gold.fact_sales`
          WHERE order_date >= DATE_SUB('{self.execution_date}', INTERVAL 30 DAY)
          GROUP BY order_date
        ),
        stats AS (
          SELECT
            AVG(daily_orders) as avg_orders,
            STDDEV(daily_orders) as std_orders
          FROM daily_counts
          WHERE order_date < '{self.execution_date}'
        ),
        today AS (
          SELECT COALESCE(daily_orders, 0) as today_orders
          FROM daily_counts
          WHERE order_date = '{self.execution_date}'
        )
        SELECT
          s.avg_orders,
          s.std_orders,
          t.today_orders,
          ABS(t.today_orders - s.avg_orders) / NULLIF(s.std_orders, 0) as z_score
        FROM stats s, today t
        """
        start = time.time()
        rows = self._run_query(sql)
        if not rows or rows[0].get("z_score") is None:
            result = "warn"
            z_score = -1.0
        else:
            z_score = rows[0]["z_score"]
            result = "pass" if z_score <= std_dev_threshold else "warn"
        return DataQualityResult(
            check_name="volume_anomaly_detection",
            check_category="volume",
            layer="gold",
            table_name="fact_sales",
            check_sql=sql.strip(),
            result=result,
            expected_value=f"z_score <= {std_dev_threshold}",
            actual_value=(f"z_score = {z_score:.2f}" if z_score >= 0 else "insufficient data"),
            details={
                "avg_orders": str(rows[0].get("avg_orders", "N/A")) if rows else "N/A",
                "today_orders": str(rows[0].get("today_orders", "N/A")) if rows else "N/A",
            },
            duration_seconds=round(time.time() - start, 2),
        )

    def run_all_checks(self) -> list[DataQualityResult]:
        """Executa todos os 6 checks e retorna lista de resultados."""
        checks = [
            self.check_freshness,
            self.check_completeness,
            self.check_accuracy,
            self.check_uniqueness,
            self.check_referential_integrity,
            self.check_volume_anomaly,
        ]
        self.results = []
        for check_fn in checks:
            try:
                result = check_fn()
                self.results.append(result)
                logger.info(
                    "[%s] %s: %s (actual=%s)",
                    result.result.upper(),
                    result.check_name,
                    result.check_category,
                    result.actual_value,
                )
            except Exception as e:
                logger.error("Check %s failed with error: %s", check_fn.__name__, e)
                self.results.append(
                    DataQualityResult(
                        check_name=check_fn.__name__,
                        check_category="error",
                        layer="unknown",
                        table_name="",
                        check_sql="",
                        result="fail",
                        expected_value="no error",
                        actual_value=str(e),
                    )
                )
        return self.results

    def save_results(self, dag_run_id: str = "") -> int:
        """Salva resultados na tabela data_quality_log via streaming insert."""
        if not self.results:
            return 0
        rows = []
        now = datetime.now(UTC)
        for r in self.results:
            rows.append(
                {
                    "check_id": str(uuid.uuid4())[:12],
                    "check_name": r.check_name,
                    "check_category": r.check_category,
                    "layer": r.layer,
                    "table_name": r.table_name,
                    "check_sql": r.check_sql[:4000],
                    "result": r.result,
                    "expected_value": r.expected_value,
                    "actual_value": r.actual_value,
                    "details": json.dumps(r.details),
                    "execution_date": str(self.execution_date),
                    "execution_timestamp": now.isoformat(),
                    "dag_run_id": dag_run_id,
                    "duration_seconds": r.duration_seconds,
                }
            )
        table_id = f"{self.project_id}.{self.MONITORING_DATASET}.{self.QUALITY_TABLE}"
        errors = self.client.insert_rows_json(table_id, rows)
        if errors:
            logger.error("Erro ao salvar resultados: %s", errors)
        return len(rows)
