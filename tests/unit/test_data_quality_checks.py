"""
Unit tests for the DataQualityChecker class.
Uses mocked BigQuery client to test all 6 quality checks.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from plugins.mrhealth.quality.checks import DataQualityChecker, DataQualityResult


@pytest.fixture
def mock_bq_client():
    with patch("plugins.mrhealth.quality.checks.bigquery.Client") as mock_cls:
        client = MagicMock()
        mock_cls.return_value = client
        yield client


@pytest.fixture
def checker(mock_bq_client):
    return DataQualityChecker(
        project_id="test-project",
        execution_date=date(2026, 2, 5),
    )


def _mock_query_result(client, rows):
    """Helper to mock BigQuery query results."""
    job = MagicMock()
    job.result.return_value = [
        MagicMock(
            **{k: v for k, v in row.items()}, **{"__getitem__": lambda self, k: getattr(self, k)}
        )
        for row in rows
    ]
    # Use dict-based rows
    mock_rows = []
    for row in rows:
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, k, r=row: r[k]
        mock_row.get = lambda k, default=None, r=row: r.get(k, default)
        mock_row.keys = lambda r=row: r.keys()
        mock_rows.append(mock_row)
    job.result.return_value = mock_rows
    client.query.return_value = job


class TestDataQualityResult:
    def test_passed_property(self):
        result = DataQualityResult(
            check_name="test",
            check_category="test",
            layer="gold",
            table_name="t",
            check_sql="",
            result="pass",
            expected_value="",
            actual_value="",
        )
        assert result.passed is True
        assert result.failed is False

    def test_failed_property(self):
        result = DataQualityResult(
            check_name="test",
            check_category="test",
            layer="gold",
            table_name="t",
            check_sql="",
            result="fail",
            expected_value="",
            actual_value="",
        )
        assert result.passed is False
        assert result.failed is True


class TestCheckFreshness:
    def test_freshness_pass(self, checker, mock_bq_client):
        _mock_query_result(mock_bq_client, [{"cnt": 100}])
        result = checker.check_freshness()
        assert result.result == "pass"
        assert result.check_name == "freshness_fact_sales"
        assert result.check_category == "freshness"

    def test_freshness_fail_no_data(self, checker, mock_bq_client):
        _mock_query_result(mock_bq_client, [{"cnt": 0}])
        result = checker.check_freshness()
        assert result.result == "fail"


class TestCheckCompleteness:
    def test_completeness_pass_all_units(self, checker, mock_bq_client):
        _mock_query_result(mock_bq_client, [{"active_units": 50}])
        result = checker.check_completeness(expected_units=50)
        assert result.result == "pass"

    def test_completeness_warn_90_pct(self, checker, mock_bq_client):
        _mock_query_result(mock_bq_client, [{"active_units": 46}])
        result = checker.check_completeness(expected_units=50)
        assert result.result == "warn"

    def test_completeness_fail_low(self, checker, mock_bq_client):
        _mock_query_result(mock_bq_client, [{"active_units": 10}])
        result = checker.check_completeness(expected_units=50)
        assert result.result == "fail"


class TestCheckAccuracy:
    def test_accuracy_pass(self, checker, mock_bq_client):
        _mock_query_result(
            mock_bq_client, [{"silver_total": 1000.0, "gold_total": 1000.0, "diff": 0.0}]
        )
        result = checker.check_accuracy()
        assert result.result == "pass"

    def test_accuracy_warn(self, checker, mock_bq_client):
        _mock_query_result(
            mock_bq_client, [{"silver_total": 1000.0, "gold_total": 999.5, "diff": 0.5}]
        )
        result = checker.check_accuracy()
        assert result.result == "warn"

    def test_accuracy_fail(self, checker, mock_bq_client):
        _mock_query_result(
            mock_bq_client, [{"silver_total": 1000.0, "gold_total": 990.0, "diff": 10.0}]
        )
        result = checker.check_accuracy()
        assert result.result == "fail"


class TestCheckUniqueness:
    def test_uniqueness_pass_no_duplicates(self, checker, mock_bq_client):
        _mock_query_result(mock_bq_client, [])
        result = checker.check_uniqueness()
        assert result.result == "pass"

    def test_uniqueness_fail_with_duplicates(self, checker, mock_bq_client):
        _mock_query_result(mock_bq_client, [{"order_id": "ORD001", "cnt": 2}])
        result = checker.check_uniqueness()
        assert result.result == "fail"


class TestCheckReferentialIntegrity:
    def test_referential_pass(self, checker, mock_bq_client):
        _mock_query_result(mock_bq_client, [{"orphan_count": 0}])
        result = checker.check_referential_integrity()
        assert result.result == "pass"

    def test_referential_fail(self, checker, mock_bq_client):
        _mock_query_result(mock_bq_client, [{"orphan_count": 5}])
        result = checker.check_referential_integrity()
        assert result.result == "fail"


class TestCheckVolumeAnomaly:
    def test_volume_pass_normal(self, checker, mock_bq_client):
        _mock_query_result(
            mock_bq_client,
            [
                {
                    "avg_orders": 100.0,
                    "std_orders": 10.0,
                    "today_orders": 105,
                    "z_score": 0.5,
                }
            ],
        )
        result = checker.check_volume_anomaly()
        assert result.result == "pass"

    def test_volume_warn_anomaly(self, checker, mock_bq_client):
        _mock_query_result(
            mock_bq_client,
            [
                {
                    "avg_orders": 100.0,
                    "std_orders": 10.0,
                    "today_orders": 150,
                    "z_score": 5.0,
                }
            ],
        )
        result = checker.check_volume_anomaly()
        assert result.result == "warn"

    def test_volume_warn_no_data(self, checker, mock_bq_client):
        _mock_query_result(mock_bq_client, [])
        result = checker.check_volume_anomaly()
        assert result.result == "warn"


class TestRunAllChecks:
    def test_run_all_returns_6_results(self, checker, mock_bq_client):
        _mock_query_result(mock_bq_client, [{"cnt": 100}])
        results = checker.run_all_checks()
        assert len(results) == 6

    def test_run_all_handles_exceptions(self, checker, mock_bq_client):
        mock_bq_client.query.side_effect = Exception("BQ unavailable")
        results = checker.run_all_checks()
        assert len(results) == 6
        assert all(r.result == "fail" for r in results)


class TestSaveResults:
    def test_save_results_empty(self, checker, mock_bq_client):
        saved = checker.save_results(dag_run_id="test")
        assert saved == 0

    def test_save_results_success(self, checker, mock_bq_client):
        checker.results = [
            DataQualityResult(
                check_name="test",
                check_category="test",
                layer="gold",
                table_name="t",
                check_sql="SELECT 1",
                result="pass",
                expected_value="1",
                actual_value="1",
            )
        ]
        mock_bq_client.insert_rows_json.return_value = []
        saved = checker.save_results(dag_run_id="test__2026-02-05")
        assert saved == 1
        mock_bq_client.insert_rows_json.assert_called_once()
