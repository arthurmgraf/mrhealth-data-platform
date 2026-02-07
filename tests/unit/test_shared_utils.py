"""Unit tests for scripts/utils/ shared utilities.

Tests config loader (env var substitution, error handling) and SQL executor.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest
import yaml


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------

class TestLoadConfig:
    def test_loads_yaml_with_env_substitution(self, sample_config_yaml, monkeypatch):
        monkeypatch.setenv("GCP_PROJECT_ID", "my-project-123")
        monkeypatch.setenv("GCP_REGION", "europe-west1")
        monkeypatch.setenv("GCS_BUCKET_NAME", "my-bucket")

        from scripts.utils.config import load_config

        config = load_config(sample_config_yaml)

        assert config["project"]["id"] == "my-project-123"
        assert config["project"]["region"] == "europe-west1"
        assert config["gcs"]["bucket_name"] == "my-bucket"

    def test_uses_default_when_env_var_unset(self, sample_config_yaml, monkeypatch):
        monkeypatch.delenv("GCP_REGION", raising=False)
        monkeypatch.delenv("GCS_BUCKET_NAME", raising=False)

        from scripts.utils.config import load_config

        config = load_config(sample_config_yaml)

        assert config["project"]["region"] == "us-central1"
        assert config["gcs"]["bucket_name"] == "test-bucket"

    def test_keeps_placeholder_when_no_default_and_no_env(self, tmp_path, monkeypatch):
        monkeypatch.delenv("MY_CUSTOM_VAR", raising=False)
        config_file = tmp_path / "config.yaml"
        config_file.write_text("key: ${MY_CUSTOM_VAR}\n", encoding="utf-8")

        from scripts.utils.config import load_config

        config = load_config(config_file)
        assert config["key"] == "${MY_CUSTOM_VAR}"

    def test_file_not_found_raises(self, tmp_path):
        from scripts.utils.config import load_config

        with pytest.raises(FileNotFoundError, match="Configuration file not found"):
            load_config(tmp_path / "nonexistent.yaml")

    def test_invalid_yaml_raises(self, tmp_path):
        config_file = tmp_path / "bad.yaml"
        config_file.write_text("key: [invalid\n", encoding="utf-8")

        from scripts.utils.config import load_config

        with pytest.raises(yaml.YAMLError):
            load_config(config_file)

    def test_multiple_placeholders_in_one_line(self, tmp_path, monkeypatch):
        monkeypatch.setenv("A", "alpha")
        monkeypatch.setenv("B", "beta")
        config_file = tmp_path / "config.yaml"
        config_file.write_text("value: ${A}-${B}\n", encoding="utf-8")

        from scripts.utils.config import load_config

        config = load_config(config_file)
        assert config["value"] == "alpha-beta"

    def test_default_with_special_chars(self, tmp_path, monkeypatch):
        monkeypatch.delenv("UNSET_VAR", raising=False)
        config_file = tmp_path / "config.yaml"
        config_file.write_text("url: ${UNSET_VAR:-https://example.com/path}\n", encoding="utf-8")

        from scripts.utils.config import load_config

        config = load_config(config_file)
        assert config["url"] == "https://example.com/path"


# ---------------------------------------------------------------------------
# get_project_id
# ---------------------------------------------------------------------------

class TestGetProjectId:
    def test_returns_config_value(self, sample_config_yaml, monkeypatch):
        monkeypatch.setenv("GCP_PROJECT_ID", "real-project")

        from scripts.utils.config import load_config, get_project_id

        config = load_config(sample_config_yaml)
        result = get_project_id(config)
        assert result == "real-project"

    def test_falls_back_to_env_when_placeholder(self, monkeypatch):
        monkeypatch.setenv("GCP_PROJECT_ID", "env-project")

        from scripts.utils.config import get_project_id

        config = {"project": {"id": "${GCP_PROJECT_ID}"}}
        result = get_project_id(config)
        assert result == "env-project"

    def test_falls_back_to_env_when_empty(self, monkeypatch):
        monkeypatch.setenv("GCP_PROJECT_ID", "env-project")

        from scripts.utils.config import get_project_id

        config = {"project": {"id": ""}}
        result = get_project_id(config)
        assert result == "env-project"

    def test_returns_empty_when_no_config_and_no_env(self, monkeypatch):
        monkeypatch.delenv("GCP_PROJECT_ID", raising=False)

        from scripts.utils.config import get_project_id

        config = {"project": {"id": ""}}
        result = get_project_id(config)
        assert result == ""

    def test_returns_hardcoded_value_from_config(self, monkeypatch):
        from scripts.utils.config import get_project_id

        config = {"project": {"id": "hardcoded-project-id"}}
        result = get_project_id(config)
        assert result == "hardcoded-project-id"

    def test_missing_project_key(self, monkeypatch):
        monkeypatch.setenv("GCP_PROJECT_ID", "fallback")

        from scripts.utils.config import get_project_id

        config = {}
        result = get_project_id(config)
        assert result == "fallback"


# ---------------------------------------------------------------------------
# execute_sql_file
# ---------------------------------------------------------------------------

class TestExecuteSqlFile:
    def test_executes_sql_successfully(self, tmp_path, mock_bq_client):
        from scripts.utils.sql_executor import execute_sql_file

        sql_file = tmp_path / "test.sql"
        sql_file.write_text("SELECT 1;", encoding="utf-8")

        result = execute_sql_file(mock_bq_client, sql_file, "Test query")

        assert result is True
        mock_bq_client.query.assert_called_once_with("SELECT 1;")

    def test_replaces_project_id_placeholder(self, tmp_path, mock_bq_client):
        from scripts.utils.sql_executor import execute_sql_file

        sql_file = tmp_path / "test.sql"
        sql_file.write_text(
            "SELECT * FROM `{PROJECT_ID}.mrhealth_gold.fact_sales`;",
            encoding="utf-8",
        )

        result = execute_sql_file(
            mock_bq_client, sql_file, "Test query", project_id="my-project"
        )

        assert result is True
        called_sql = mock_bq_client.query.call_args[0][0]
        assert "my-project" in called_sql
        assert "{PROJECT_ID}" not in called_sql

    def test_no_substitution_when_project_id_none(self, tmp_path, mock_bq_client):
        from scripts.utils.sql_executor import execute_sql_file

        sql_file = tmp_path / "test.sql"
        sql_file.write_text("SELECT * FROM `{PROJECT_ID}.dataset.table`;", encoding="utf-8")

        result = execute_sql_file(mock_bq_client, sql_file, "Test query")

        assert result is True
        called_sql = mock_bq_client.query.call_args[0][0]
        assert "{PROJECT_ID}" in called_sql

    def test_returns_false_on_query_error(self, tmp_path, mock_bq_client):
        from scripts.utils.sql_executor import execute_sql_file

        sql_file = tmp_path / "bad.sql"
        sql_file.write_text("INVALID SQL;", encoding="utf-8")

        mock_bq_client.query.side_effect = Exception("Syntax error")

        result = execute_sql_file(mock_bq_client, sql_file, "Bad query")

        assert result is False

    def test_returns_false_on_file_not_found(self, mock_bq_client):
        from scripts.utils.sql_executor import execute_sql_file

        result = execute_sql_file(
            mock_bq_client, Path("/nonexistent/test.sql"), "Missing file"
        )

        assert result is False
        mock_bq_client.query.assert_not_called()

    def test_prints_byte_statistics(self, tmp_path, mock_bq_client, capsys):
        from scripts.utils.sql_executor import execute_sql_file

        sql_file = tmp_path / "test.sql"
        sql_file.write_text("SELECT 1;", encoding="utf-8")
        mock_bq_client.query.return_value.total_bytes_processed = 2048
        mock_bq_client.query.return_value.total_bytes_billed = 1024

        execute_sql_file(mock_bq_client, sql_file, "Stats test")

        captured = capsys.readouterr()
        assert "2,048" in captured.out
        assert "1,024" in captured.out


# ---------------------------------------------------------------------------
# constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_product_catalog_has_30_items(self):
        from scripts.constants import PRODUCT_CATALOG

        assert len(PRODUCT_CATALOG) == 30

    def test_product_catalog_unique_ids(self):
        from scripts.constants import PRODUCT_CATALOG

        ids = [p["id"] for p in PRODUCT_CATALOG]
        assert len(set(ids)) == 30

    def test_product_catalog_all_have_required_keys(self):
        from scripts.constants import PRODUCT_CATALOG

        for product in PRODUCT_CATALOG:
            assert "id" in product
            assert "name" in product
            assert "price" in product
            assert product["price"] > 0

    def test_states_match_southern_brazil(self):
        from scripts.constants import STATES

        assert len(STATES) == 3
        names = {s["name"] for s in STATES}
        assert names == {"Rio Grande do Sul", "Santa Catarina", "Parana"}

    def test_cities_by_state_covers_all_states(self):
        from scripts.constants import CITIES_BY_STATE, STATES

        for state in STATES:
            assert state["id"] in CITIES_BY_STATE
            assert len(CITIES_BY_STATE[state["id"]]) > 0

    def test_status_choices(self):
        from scripts.constants import STATUS_CHOICES, STATUS_WEIGHTS

        assert len(STATUS_CHOICES) == 3
        assert len(STATUS_WEIGHTS) == 3
        assert abs(sum(STATUS_WEIGHTS) - 1.0) < 0.001

    def test_order_type_choices(self):
        from scripts.constants import ORDER_TYPE_CHOICES, ORDER_TYPE_WEIGHTS

        assert len(ORDER_TYPE_CHOICES) == 2
        assert abs(sum(ORDER_TYPE_WEIGHTS) - 1.0) < 0.001
