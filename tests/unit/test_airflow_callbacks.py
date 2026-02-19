"""Unit tests for Airflow alert callbacks and config loader plugin."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Alert Callbacks
# ---------------------------------------------------------------------------


class TestOnSlaMiss:
    @patch("plugins.mrhealth.callbacks.alerts._save_metric")
    def test_logs_sla_miss(self, mock_save):
        from plugins.mrhealth.callbacks.alerts import on_sla_miss

        dag = MagicMock()
        dag.dag_id = "mrhealth_daily_pipeline"
        task1 = MagicMock()
        task1.task_id = "build_silver"
        task2 = MagicMock()
        task2.task_id = "build_gold_facts"

        on_sla_miss(dag, [task1], [task2], None, None)

        mock_save.assert_called_once()
        call_kwargs = mock_save.call_args[1]
        assert call_kwargs["metric_name"] == "sla_miss"
        assert call_kwargs["dag_id"] == "mrhealth_daily_pipeline"

    @patch("plugins.mrhealth.callbacks.alerts._save_metric")
    def test_handles_none_dag(self, mock_save):
        from plugins.mrhealth.callbacks.alerts import on_sla_miss

        on_sla_miss(None, [], [], None, None)

        call_kwargs = mock_save.call_args[1]
        assert call_kwargs["dag_id"] == "unknown"

    @patch("plugins.mrhealth.callbacks.alerts._save_metric", side_effect=Exception("BQ down"))
    def test_handles_save_error_gracefully(self, mock_save):
        from plugins.mrhealth.callbacks.alerts import on_sla_miss

        on_sla_miss(MagicMock(dag_id="test"), [], [], None, None)


class TestOnTaskFailure:
    @patch("plugins.mrhealth.callbacks.alerts._save_metric")
    def test_logs_task_failure(self, mock_save):
        from plugins.mrhealth.callbacks.alerts import on_task_failure

        ti = MagicMock()
        ti.dag_id = "mrhealth_daily_pipeline"
        ti.task_id = "build_silver"
        context = {
            "task_instance": ti,
            "exception": ValueError("test error"),
            "run_id": "test__2026-02-05",
        }

        on_task_failure(context)

        mock_save.assert_called_once()
        call_kwargs = mock_save.call_args[1]
        assert call_kwargs["metric_name"] == "task_failure"
        assert call_kwargs["task_id"] == "build_silver"

    @patch("plugins.mrhealth.callbacks.alerts._save_metric")
    def test_handles_missing_task_instance(self, mock_save):
        from plugins.mrhealth.callbacks.alerts import on_task_failure

        on_task_failure({})

        call_kwargs = mock_save.call_args[1]
        assert call_kwargs["dag_id"] == "unknown"


class TestOnQualityFailure:
    @patch("plugins.mrhealth.callbacks.alerts._save_metric")
    def test_logs_quality_failures(self, mock_save):
        from plugins.mrhealth.callbacks.alerts import on_quality_failure

        failure1 = MagicMock(check_name="freshness", expected_value=">0", actual_value="0")
        failure2 = MagicMock(check_name="uniqueness", expected_value="0 dupes", actual_value="5")

        dag = MagicMock()
        dag.dag_id = "mrhealth_data_quality"
        context = {"dag": dag, "run_id": "test_run"}

        on_quality_failure([failure1, failure2], context)

        call_kwargs = mock_save.call_args[1]
        assert call_kwargs["metric_name"] == "quality_failure"
        assert call_kwargs["metric_value"] == 2.0


class TestSaveMetric:
    @patch("plugins.mrhealth.callbacks.alerts.bigquery.Client")
    def test_inserts_row_to_monitoring(self, mock_bq_cls):
        from plugins.mrhealth.callbacks.alerts import _save_metric

        client = MagicMock()
        mock_bq_cls.return_value = client
        client.insert_rows_json.return_value = []

        _save_metric(
            project_id="test-project",
            dag_id="test_dag",
            metric_name="test_metric",
            metric_value=1.0,
            metric_unit="event",
        )

        client.insert_rows_json.assert_called_once()
        table_id = client.insert_rows_json.call_args[0][0]
        assert "mrhealth_monitoring.pipeline_metrics" in table_id


# ---------------------------------------------------------------------------
# Config Loader Plugin
# ---------------------------------------------------------------------------


class TestPluginConfigLoader:
    def test_load_config_caches(self, tmp_path, monkeypatch):
        import plugins.mrhealth.config.loader as loader

        config_file = tmp_path / "project_config.yaml"
        config_file.write_text("project:\n  id: test-id\n", encoding="utf-8")

        monkeypatch.setattr(loader, "CONFIG_PATH", config_file)
        loader._config_cache = None

        config1 = loader.load_config()
        config2 = loader.load_config()
        assert config1 is config2
        assert config1["project"]["id"] == "test-id"

        loader._config_cache = None

    def test_load_config_retries_after_failure(self, tmp_path, monkeypatch):
        import plugins.mrhealth.config.loader as loader

        monkeypatch.setattr(loader, "CONFIG_PATH", tmp_path / "missing.yaml")
        loader._config_cache = None

        with pytest.raises(FileNotFoundError):
            loader.load_config()

        assert loader._config_cache is None

        config_file = tmp_path / "missing.yaml"
        config_file.write_text("project:\n  id: recovered\n", encoding="utf-8")
        monkeypatch.setattr(loader, "CONFIG_PATH", config_file)

        config = loader.load_config()
        assert config["project"]["id"] == "recovered"

        loader._config_cache = None

    def test_get_project_id_from_config(self, tmp_path, monkeypatch):
        import plugins.mrhealth.config.loader as loader

        config_file = tmp_path / "project_config.yaml"
        config_file.write_text("project:\n  id: my-real-project\n", encoding="utf-8")

        monkeypatch.setattr(loader, "CONFIG_PATH", config_file)
        loader._config_cache = None

        result = loader.get_project_id()
        assert result == "my-real-project"

        loader._config_cache = None

    def test_get_project_id_falls_back_to_env(self, tmp_path, monkeypatch):
        import plugins.mrhealth.config.loader as loader

        config_file = tmp_path / "project_config.yaml"
        config_file.write_text("project:\n  id: ${GCP_PROJECT_ID}\n", encoding="utf-8")

        monkeypatch.setattr(loader, "CONFIG_PATH", config_file)
        monkeypatch.setenv("GCP_PROJECT_ID", "env-project")
        loader._config_cache = None

        result = loader.get_project_id()
        assert result == "env-project"

        loader._config_cache = None

    def test_get_sql_path(self):
        import plugins.mrhealth.config.loader as loader

        result = loader.get_sql_path("gold", "dim_date.sql")
        assert result.name == "dim_date.sql"
        assert "gold" in str(result)
