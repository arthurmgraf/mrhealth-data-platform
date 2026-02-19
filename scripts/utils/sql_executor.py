"""Shared SQL execution utilities for BigQuery.

Replaces the execute_sql_file() function duplicated identically across
build_silver_layer.py, build_gold_layer.py, and build_aggregations.py.

Provides a single, well-typed implementation with optional {PROJECT_ID}
placeholder substitution for SQL files that reference the project directly.
"""

from __future__ import annotations

from pathlib import Path

from google.cloud import bigquery


def execute_sql_file(
    client: bigquery.Client,
    sql_file_path: Path,
    description: str,
    project_id: str | None = None,
) -> bool:
    """Execute a SQL file in BigQuery with optional project ID substitution.

    Reads the SQL file, optionally replaces {PROJECT_ID} placeholders with the
    actual project ID, executes the query, and prints status with byte statistics.

    Args:
        client: An initialized BigQuery client.
        sql_file_path: Path to the .sql file to execute.
        description: Human-readable description for console output.
        project_id: If provided, replaces {PROJECT_ID} in the SQL text.

    Returns:
        True if the query executed successfully, False otherwise.
    """
    print(f"\n[EXECUTING] {description}")
    print(f"  File: {sql_file_path.name}")

    try:
        with open(sql_file_path, encoding="utf-8") as f:
            sql = f.read()

        if project_id:
            sql = sql.replace("{PROJECT_ID}", project_id)

        query_job = client.query(sql)
        query_job.result()

        bytes_processed = query_job.total_bytes_processed or 0
        bytes_billed = query_job.total_bytes_billed or 0

        print("  [OK] Query completed")
        print(f"       Bytes processed: {bytes_processed:,}")
        print(f"       Bytes billed: {bytes_billed:,}")
        return True

    except Exception as e:
        print(f"  [ERROR] Query failed: {e}")
        return False
