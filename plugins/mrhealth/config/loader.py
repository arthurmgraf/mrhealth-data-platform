"""
Centralized Config Loader
===========================
Loads project_config.yaml for all DAGs and operators.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

CONFIG_PATH = Path(
    os.environ.get("MRHEALTH_CONFIG_PATH", "/opt/airflow/config/project_config.yaml")
)

SQL_BASE = Path(
    os.environ.get("MRHEALTH_SQL_PATH", "/opt/airflow/sql")
)

_config_cache: dict[str, Any] | None = None


def load_config() -> dict[str, Any]:
    """Load and cache project configuration.

    Unlike @lru_cache, this approach does not permanently cache exceptions.
    If the config file is temporarily unavailable, the next call will retry.
    """
    global _config_cache
    if _config_cache is not None:
        return _config_cache
    with open(CONFIG_PATH, "r") as f:
        _config_cache = yaml.safe_load(f)
    return _config_cache


def get_project_id() -> str:
    config = load_config()
    project_id = config["project"]["id"]
    if isinstance(project_id, str) and project_id.startswith("${"):
        return os.environ.get("GCP_PROJECT_ID", "")
    return project_id


def get_sql_path(layer: str, filename: str) -> Path:
    return SQL_BASE / layer / filename
