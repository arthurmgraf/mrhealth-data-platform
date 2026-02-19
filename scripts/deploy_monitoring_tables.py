"""
Deploy Monitoring Tables
=========================
Creates the 3 monitoring tables in BigQuery dataset mrhealth_monitoring.
Reads SQL files from sql/monitoring/ and executes them.

Usage:
    python scripts/deploy_monitoring_tables.py
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from google.cloud import bigquery

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = PROJECT_ROOT / "sql" / "monitoring"
CONFIG_PATH = PROJECT_ROOT / "config" / "project_config.yaml"


def get_project_id() -> str:
    project_id = os.environ.get("GCP_PROJECT_ID")
    if not project_id:
        import yaml

        with open(CONFIG_PATH) as f:
            config = yaml.safe_load(f)
        project_id = config["project"]["id"]
        if project_id.startswith("${"):
            raise ValueError("GCP_PROJECT_ID not set. Export it or set in .env file.")
    return project_id


def main() -> None:
    project_id = get_project_id()
    client = bigquery.Client(project=project_id)

    dataset_id = f"{project_id}.mrhealth_monitoring"
    dataset = bigquery.Dataset(dataset_id)
    dataset.location = "US"
    dataset.description = "Pipeline metrics and data quality logs"
    dataset.labels = {"layer": "monitoring", "managed_by": "script"}
    client.create_dataset(dataset, exists_ok=True)
    print(f"Dataset ready: {dataset_id}")

    sql_files = sorted(SQL_DIR.glob("*.sql"))
    if not sql_files:
        print(f"No SQL files found in {SQL_DIR}")
        return

    for sql_file in sql_files:
        print(f"Executing: {sql_file.name}")
        sql = sql_file.read_text(encoding="utf-8")
        sql = re.sub(r"\{PROJECT_ID\}", project_id, sql)
        job = client.query(sql)
        job.result()
        print(f"  OK: {sql_file.name}")

    print(f"\nAll {len(sql_files)} monitoring tables created successfully.")


if __name__ == "__main__":
    main()
