"""Shared test fixtures for MR. HEALTH Data Platform."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def _set_test_env(monkeypatch):
    """Set standard environment variables for all tests."""
    monkeypatch.setenv("GCP_PROJECT_ID", "test-project-id")
    monkeypatch.setenv("PROJECT_ID", "test-project-id")
    monkeypatch.setenv("BUCKET_NAME", "test-bucket")
    monkeypatch.setenv("BQ_DATASET", "mrhealth_bronze")
    monkeypatch.setenv("GCP_REGION", "us-central1")
    monkeypatch.setenv("GCS_BUCKET_NAME", "test-bucket")


@pytest.fixture
def project_root() -> Path:
    """Return the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def sample_config_yaml(tmp_path: Path) -> Path:
    """Create a sample project_config.yaml for testing."""
    config_content = """\
project:
  id: ${GCP_PROJECT_ID}
  region: ${GCP_REGION:-us-central1}

gcs:
  bucket_name: ${GCS_BUCKET_NAME:-test-bucket}

bigquery:
  datasets:
    bronze: mrhealth_bronze
    silver: mrhealth_silver
    gold: mrhealth_gold
    monitoring: mrhealth_monitoring
"""
    config_file = tmp_path / "project_config.yaml"
    config_file.write_text(config_content, encoding="utf-8")
    return config_file


@pytest.fixture
def mock_bq_client():
    """Create a mock BigQuery client."""
    client = MagicMock()
    job = MagicMock()
    job.result.return_value = []
    job.total_bytes_processed = 1024
    job.total_bytes_billed = 0
    client.query.return_value = job
    return client
