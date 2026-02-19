"""Centralized configuration loader for MR. HEALTH scripts.

Replaces the load_config() function duplicated across 7+ scripts
(build_silver_layer.py, build_gold_layer.py, build_aggregations.py,
deploy_phase1_infrastructure.py, verify_infrastructure.py,
upload_fake_data_to_gcs.py, load_reference_data.py).

Key improvement over the duplicated versions:
- Resolves ${VAR} and ${VAR:-default} placeholders from environment variables
  (the raw YAML contains placeholders like ${GCP_PROJECT_ID} that were not
  being substituted, causing issues documented in MEMORY.md).
- Handles missing config file gracefully with a clear error message.
- Provides get_project_id() to centralize the fallback logic for project ID.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

_DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "project_config.yaml"


def load_config(config_path: Path | None = None) -> dict[str, Any]:
    """Load project configuration from YAML with environment variable substitution.

    Reads config/project_config.yaml and resolves placeholders:
      - ${VAR}          -> value of environment variable VAR (kept as-is if unset)
      - ${VAR:-default} -> value of VAR, or "default" if VAR is unset

    Args:
        config_path: Optional override for the YAML config file location.
                     Defaults to <project_root>/config/project_config.yaml.

    Returns:
        Parsed configuration dictionary.

    Raises:
        FileNotFoundError: If the config file does not exist.
        yaml.YAMLError: If the YAML is malformed.
    """
    path = config_path or _DEFAULT_CONFIG_PATH

    if not path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {path}\nExpected at: {path.resolve()}"
        )

    with open(path, encoding="utf-8") as f:
        raw = f.read()

    def _replace_env(match: re.Match) -> str:
        var_expr = match.group(1)
        if ":-" in var_expr:
            var_name, default = var_expr.split(":-", 1)
            return os.environ.get(var_name, default)
        return os.environ.get(var_expr, match.group(0))

    resolved = re.sub(r"\$\{([^}]+)\}", _replace_env, raw)
    return yaml.safe_load(resolved)


def get_project_id(config: dict[str, Any] | None = None) -> str:
    """Get GCP project ID from config or environment variable.

    Resolution order:
      1. config["project"]["id"] (if not a placeholder)
      2. GCP_PROJECT_ID environment variable
      3. Empty string (caller should handle)

    Args:
        config: Pre-loaded config dict. If None, loads from default path.

    Returns:
        The resolved GCP project ID string.
    """
    if config is None:
        config = load_config()

    project_id = config.get("project", {}).get("id", "")

    if not project_id or (isinstance(project_id, str) and project_id.startswith("${")):
        return os.environ.get("GCP_PROJECT_ID", "")

    return project_id
