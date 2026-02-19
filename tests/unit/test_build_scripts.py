"""Unit tests for build scripts (Silver, Gold, Aggregations).

Tests the main() function and helper functions of each build script
with mocked BigQuery client.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch


class TestBuildSilverLayer:
    @patch("scripts.build_silver_layer.bigquery.Client")
    @patch("scripts.build_silver_layer.execute_sql_file")
    @patch("scripts.build_silver_layer.load_config")
    @patch("scripts.build_silver_layer.get_project_id")
    def test_main_success(self, mock_pid, mock_config, mock_exec, mock_bq_cls):
        from scripts.build_silver_layer import main

        mock_config.return_value = {
            "bigquery": {"datasets": {"silver": "mrhealth_silver"}},
        }
        mock_pid.return_value = "test-project"
        mock_exec.return_value = True

        with patch("sys.argv", ["build_silver_layer.py"]):
            result = main()

        assert result == 0
        assert mock_exec.call_count == 3

    @patch("scripts.build_silver_layer.bigquery.Client")
    @patch("scripts.build_silver_layer.execute_sql_file")
    @patch("scripts.build_silver_layer.load_config")
    @patch("scripts.build_silver_layer.get_project_id")
    def test_main_partial_failure(self, mock_pid, mock_config, mock_exec, mock_bq_cls):
        from scripts.build_silver_layer import main

        mock_config.return_value = {
            "bigquery": {"datasets": {"silver": "mrhealth_silver"}},
        }
        mock_pid.return_value = "test-project"
        mock_exec.side_effect = [True, False, True]

        with patch("sys.argv", ["build_silver_layer.py"]):
            result = main()

        assert result == 1

    @patch("scripts.build_silver_layer.bigquery.Client")
    def test_verify_silver_tables(self, mock_bq_cls):
        from scripts.build_silver_layer import verify_silver_tables

        client = MagicMock()
        mock_bq_cls.return_value = client

        row = MagicMock()
        row.row_count = 100
        job = MagicMock()
        job.result.return_value = [row]
        client.query.return_value = job

        results = verify_silver_tables(client, "test-project")

        assert len(results) == 6
        assert all(v == 100 for v in results.values())


class TestBuildGoldLayer:
    @patch("scripts.build_gold_layer.bigquery.Client")
    @patch("scripts.build_gold_layer.execute_sql_file")
    @patch("scripts.build_gold_layer.load_config")
    @patch("scripts.build_gold_layer.get_project_id")
    def test_main_success(self, mock_pid, mock_config, mock_exec, mock_bq_cls):
        from scripts.build_gold_layer import main

        mock_config.return_value = {
            "bigquery": {"datasets": {"gold": "mrhealth_gold"}},
        }
        mock_pid.return_value = "test-project"
        mock_exec.return_value = True

        with patch("sys.argv", ["build_gold_layer.py"]):
            result = main()

        assert result == 0


class TestBuildAggregations:
    @patch("scripts.build_aggregations.bigquery.Client")
    @patch("scripts.build_aggregations.execute_sql_file")
    @patch("scripts.build_aggregations.load_config")
    @patch("scripts.build_aggregations.get_project_id")
    def test_main_success(self, mock_pid, mock_config, mock_exec, mock_bq_cls):
        from scripts.build_aggregations import main

        mock_config.return_value = {
            "bigquery": {"datasets": {"gold": "mrhealth_gold"}},
        }
        mock_pid.return_value = "test-project"
        mock_exec.return_value = True

        with patch("sys.argv", ["build_aggregations.py"]):
            result = main()

        assert result == 0


class TestDeployPhase1:
    @patch("scripts.deploy_phase1_infrastructure.bigquery.Client")
    @patch("scripts.deploy_phase1_infrastructure.load_config")
    def test_create_datasets(self, mock_config, mock_bq_cls):
        from scripts.deploy_phase1_infrastructure import create_bigquery_datasets

        client = MagicMock()
        mock_bq_cls.return_value = client

        result = create_bigquery_datasets("test-project")

        assert result is True
        assert client.create_dataset.call_count == 4

    @patch("scripts.deploy_phase1_infrastructure.bigquery.Client")
    @patch("scripts.deploy_phase1_infrastructure.load_config")
    def test_create_bronze_tables(self, mock_config, mock_bq_cls):
        from scripts.deploy_phase1_infrastructure import create_bronze_tables

        client = MagicMock()
        mock_bq_cls.return_value = client

        result = create_bronze_tables("test-project")

        assert result is True
        assert client.create_table.call_count == 6
