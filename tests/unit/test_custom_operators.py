"""
Unit tests for custom Airflow operators and sensors.
Tests BigQueryDataQualityOperator, GCSCleanupOperator, BigQueryFreshnessSensor.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest


class TestBigQueryDataQualityOperator:
    @patch("plugins.mrhealth.operators.bigquery_quality.bigquery.Client")
    def test_execute_pass(self, mock_bq_cls):
        from plugins.mrhealth.operators.bigquery_quality import BigQueryDataQualityOperator

        client = MagicMock()
        mock_bq_cls.return_value = client
        job = MagicMock()
        row = MagicMock()
        row.__getitem__ = lambda self, i: True
        job.result.return_value = [row]
        client.query.return_value = job
        client.insert_rows_json.return_value = []

        op = BigQueryDataQualityOperator(
            task_id="test_check",
            check_name="test_freshness",
            check_category="freshness",
            sql="SELECT COUNT(*) > 0 FROM table",
            project_id="test-project",
            save_to_monitoring=False,
        )

        context = {"ds": "2026-02-05", "run_id": "test__2026-02-05"}
        result = op.execute(context)

        assert result["result"] == "pass"
        assert result["check_name"] == "test_freshness"

    @patch("plugins.mrhealth.operators.bigquery_quality.bigquery.Client")
    def test_execute_fail(self, mock_bq_cls):
        from plugins.mrhealth.operators.bigquery_quality import BigQueryDataQualityOperator

        client = MagicMock()
        mock_bq_cls.return_value = client
        job = MagicMock()
        row = MagicMock()
        row.__getitem__ = lambda self, i: False
        job.result.return_value = [row]
        client.query.return_value = job

        op = BigQueryDataQualityOperator(
            task_id="test_check",
            check_name="test_freshness",
            check_category="freshness",
            sql="SELECT COUNT(*) > 0 FROM table",
            project_id="test-project",
            save_to_monitoring=False,
        )

        context = {"ds": "2026-02-05", "run_id": "test__2026-02-05"}
        result = op.execute(context)

        assert result["result"] == "fail"


class TestGCSCleanupOperator:
    @patch("plugins.mrhealth.operators.gcs_cleanup.storage.Client")
    def test_cleanup_deletes_old_files(self, mock_storage_cls):
        from plugins.mrhealth.operators.gcs_cleanup import GCSCleanupOperator

        client = MagicMock()
        mock_storage_cls.return_value = client
        bucket = MagicMock()
        client.bucket.return_value = bucket

        old_blob = MagicMock()
        old_blob.updated = datetime(2025, 1, 1, tzinfo=timezone.utc)
        old_blob.size = 1024
        old_blob.name = "raw/csv_sales/old_file.csv"

        new_blob = MagicMock()
        new_blob.updated = datetime(2026, 2, 1, tzinfo=timezone.utc)
        new_blob.size = 2048
        new_blob.name = "raw/csv_sales/new_file.csv"

        bucket.list_blobs.return_value = [old_blob, new_blob]

        op = GCSCleanupOperator(
            task_id="test_cleanup",
            bucket_name="test-bucket",
            prefix="raw/csv_sales/",
            max_age_days=60,
        )

        result = op.execute({})

        assert result["deleted_count"] == 1
        assert result["skipped_count"] == 1
        old_blob.delete.assert_called_once()
        new_blob.delete.assert_not_called()

    @patch("plugins.mrhealth.operators.gcs_cleanup.storage.Client")
    def test_cleanup_dry_run(self, mock_storage_cls):
        from plugins.mrhealth.operators.gcs_cleanup import GCSCleanupOperator

        client = MagicMock()
        mock_storage_cls.return_value = client
        bucket = MagicMock()
        client.bucket.return_value = bucket

        old_blob = MagicMock()
        old_blob.updated = datetime(2025, 1, 1, tzinfo=timezone.utc)
        old_blob.size = 1024
        bucket.list_blobs.return_value = [old_blob]

        op = GCSCleanupOperator(
            task_id="test_cleanup",
            bucket_name="test-bucket",
            prefix="raw/",
            max_age_days=60,
            dry_run=True,
        )

        result = op.execute({})

        assert result["dry_run"] is True
        old_blob.delete.assert_not_called()


class TestBigQueryFreshnessSensor:
    @patch("plugins.mrhealth.sensors.bigquery_freshness.bigquery.Client")
    def test_poke_returns_true_when_data_exists(self, mock_bq_cls):
        from plugins.mrhealth.sensors.bigquery_freshness import BigQueryFreshnessSensor

        client = MagicMock()
        mock_bq_cls.return_value = client
        job = MagicMock()
        row = MagicMock()
        row.cnt = 100
        job.result.return_value = [row]
        client.query.return_value = job

        sensor = BigQueryFreshnessSensor(
            task_id="test_sensor",
            project_id="test-project",
            dataset="mrhealth_gold",
            table="fact_sales",
            target_date="2026-02-05",
        )

        assert sensor.poke({}) is True

    @patch("plugins.mrhealth.sensors.bigquery_freshness.bigquery.Client")
    def test_poke_returns_false_when_no_data(self, mock_bq_cls):
        from plugins.mrhealth.sensors.bigquery_freshness import BigQueryFreshnessSensor

        client = MagicMock()
        mock_bq_cls.return_value = client
        job = MagicMock()
        row = MagicMock()
        row.cnt = 0
        job.result.return_value = [row]
        client.query.return_value = job

        sensor = BigQueryFreshnessSensor(
            task_id="test_sensor",
            project_id="test-project",
            dataset="mrhealth_gold",
            table="fact_sales",
            target_date="2026-02-05",
        )

        assert sensor.poke({}) is False
