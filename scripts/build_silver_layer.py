#!/usr/bin/env python3
"""
MR. HEALTH Data Platform -- Build Silver Layer
================================================

Executes SQL transformations to build the Silver layer from Bronze data.
Silver layer applies data cleaning, normalization, enrichment, and deduplication.

Usage:
    python scripts/build_silver_layer.py
    python scripts/build_silver_layer.py --project your-project-id

Author: Arthur Graf -- MR. HEALTH Data Platform
Date: January 2026
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from google.cloud import bigquery

from scripts.utils.config import load_config, get_project_id
from scripts.utils.sql_executor import execute_sql_file


def verify_silver_tables(
    client: bigquery.Client,
    project_id: str,
    dataset_id: str = "mrhealth_silver",
) -> dict[str, int | None]:
    print("\n" + "=" * 60)
    print("Silver Layer Verification")
    print("=" * 60)

    tables = ["products", "units", "states", "countries", "orders", "order_items"]
    results: dict[str, int | None] = {}

    for table_name in tables:
        table_id = f"{project_id}.{dataset_id}.{table_name}"
        try:
            query = f"SELECT COUNT(*) as row_count FROM `{table_id}`"
            result = client.query(query).result()
            row_count = list(result)[0].row_count
            results[table_name] = row_count
            print(f"  {table_name:15} {row_count:>6} rows")
        except Exception as e:
            print(f"  {table_name:15} [ERROR] {e}")
            results[table_name] = None

    print("=" * 60)
    return results


def compare_bronze_silver(client: bigquery.Client, project_id: str) -> None:
    print("\n" + "=" * 60)
    print("Bronze vs Silver Comparison")
    print("=" * 60)

    comparison_query = f"""
    SELECT 'orders' as table_name,
           (SELECT COUNT(*) FROM `{project_id}.mrhealth_bronze.orders`) as bronze_rows,
           (SELECT COUNT(*) FROM `{project_id}.mrhealth_silver.orders`) as silver_rows
    UNION ALL
    SELECT 'order_items',
           (SELECT COUNT(*) FROM `{project_id}.mrhealth_bronze.order_items`),
           (SELECT COUNT(*) FROM `{project_id}.mrhealth_silver.order_items`)
    UNION ALL
    SELECT 'products',
           (SELECT COUNT(*) FROM `{project_id}.mrhealth_bronze.products`),
           (SELECT COUNT(*) FROM `{project_id}.mrhealth_silver.products`)
    UNION ALL
    SELECT 'units',
           (SELECT COUNT(*) FROM `{project_id}.mrhealth_bronze.units`),
           (SELECT COUNT(*) FROM `{project_id}.mrhealth_silver.units`)
    """

    try:
        results = client.query(comparison_query).result()
        print(f"  {'Table':<15} {'Bronze':>8} {'Silver':>8} {'Change':>8}")
        print(f"  {'-' * 15} {'-' * 8} {'-' * 8} {'-' * 8}")

        for row in results:
            diff = row.silver_rows - row.bronze_rows
            diff_str = f"{diff:+d}" if diff != 0 else "0"
            print(f"  {row.table_name:<15} {row.bronze_rows:>8} {row.silver_rows:>8} {diff_str:>8}")

        print("=" * 60)
    except Exception as e:
        print(f"  [ERROR] Comparison failed: {e}")


def main() -> int:
    try:
        config = load_config()
        default_project = get_project_id(config)
        default_dataset = config["bigquery"]["datasets"]["silver"]
    except Exception as e:
        print(f"[ERROR] Failed to load config: {e}")
        return 1

    parser = argparse.ArgumentParser(description="Build Silver layer from Bronze data")
    parser.add_argument("--project", default=default_project, help="GCP project ID")
    parser.add_argument("--dataset", default=default_dataset, help="Silver dataset")
    args = parser.parse_args()

    print("=" * 60)
    print("MR. HEALTH Data Platform -- Build Silver Layer")
    print("=" * 60)
    print(f"Project: {args.project}")
    print(f"Dataset: {args.dataset}")
    print(f"Time:    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    client = bigquery.Client(project=args.project)

    sql_dir = Path("sql/silver")
    sql_files = [
        (sql_dir / "01_reference_tables.sql", "Reference tables (products, units, states, countries)"),
        (sql_dir / "02_orders.sql", "Orders with date enrichment and normalization"),
        (sql_dir / "03_order_items.sql", "Order items with calculated totals"),
    ]

    print("\n" + "=" * 60)
    print("Executing Silver Layer Transformations")
    print("=" * 60)

    success_count = 0
    for sql_file, description in sql_files:
        if execute_sql_file(client, sql_file, description, project_id=args.project):
            success_count += 1

    if success_count == len(sql_files):
        verify_silver_tables(client, args.project, args.dataset)
        compare_bronze_silver(client, args.project)
        print("\n[SUCCESS] Silver layer built successfully!")
        return 0
    else:
        print(f"\n[ERROR] {len(sql_files) - success_count} transformation(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
