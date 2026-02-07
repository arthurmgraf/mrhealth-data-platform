#!/usr/bin/env python3
"""
MR. HEALTH Data Platform -- Build KPI Aggregation Tables
==========================================================

Creates pre-aggregated tables for dashboard performance.
These tables power the Superset dashboards.

Usage:
    python scripts/build_aggregations.py
    python scripts/build_aggregations.py --project your-project-id

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


def verify_aggregations(
    client: bigquery.Client,
    project_id: str,
    dataset_id: str = "mrhealth_gold",
) -> dict[str, int | None]:
    print("\n" + "=" * 60)
    print("Aggregation Tables Verification")
    print("=" * 60)

    tables = ["agg_daily_sales", "agg_unit_performance", "agg_product_performance"]
    results: dict[str, int | None] = {}

    for table_name in tables:
        table_id = f"{project_id}.{dataset_id}.{table_name}"
        try:
            query = f"SELECT COUNT(*) as row_count FROM `{table_id}`"
            result = client.query(query).result()
            row_count = list(result)[0].row_count
            results[table_name] = row_count
            print(f"  {table_name:30} {row_count:>6} rows")
        except Exception as e:
            print(f"  {table_name:30} [ERROR] {e}")
            results[table_name] = None

    print("=" * 60)
    return results


def show_sample_data(
    client: bigquery.Client,
    project_id: str,
    dataset_id: str = "mrhealth_gold",
) -> None:
    print("\n" + "=" * 60)
    print("Sample Data - Daily Sales")
    print("=" * 60)

    sample_query = f"""
    SELECT
      order_date,
      total_orders,
      total_revenue,
      avg_order_value,
      online_pct,
      cancellation_rate
    FROM `{project_id}.{dataset_id}.agg_daily_sales`
    ORDER BY order_date DESC
    LIMIT 5
    """

    try:
        results = client.query(sample_query).result()

        header = f"{'Date':<12} {'Orders':>8} {'Revenue':>12} {'Avg Order':>10} {'Online %':>9} {'Cancel %':>9}"
        print(f"\n{header}")
        print("-" * 72)

        for row in results:
            print(
                f"{str(row.order_date):<12} {row.total_orders:>8} "
                f"{row.total_revenue:>12.2f} {row.avg_order_value:>10.2f} "
                f"{row.online_pct:>8.1f}% {row.cancellation_rate:>8.1f}%"
            )
    except Exception as e:
        print(f"[ERROR] Sample query failed: {e}")


def main() -> int:
    try:
        config = load_config()
        default_project = get_project_id(config)
        default_dataset = config["bigquery"]["datasets"]["gold"]
    except Exception as e:
        print(f"[ERROR] Failed to load config: {e}")
        return 1

    parser = argparse.ArgumentParser(description="Build KPI aggregation tables for dashboards")
    parser.add_argument("--project", default=default_project, help="GCP project ID")
    parser.add_argument("--dataset", default=default_dataset, help="Gold dataset")
    args = parser.parse_args()

    print("=" * 60)
    print("MR. HEALTH Data Platform -- Build KPI Aggregations")
    print("=" * 60)
    print(f"Project: {args.project}")
    print(f"Dataset: {args.dataset}")
    print(f"Time:    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    client = bigquery.Client(project=args.project)

    sql_dir = Path("sql/gold")
    sql_files = [
        (sql_dir / "07_agg_daily_sales.sql", "Daily sales aggregation"),
        (sql_dir / "08_agg_unit_performance.sql", "Unit performance aggregation"),
        (sql_dir / "09_agg_product_performance.sql", "Product performance aggregation"),
    ]

    print("\n" + "=" * 60)
    print("Executing Aggregation Queries")
    print("=" * 60)

    success_count = 0
    for sql_file, description in sql_files:
        if execute_sql_file(client, sql_file, description, project_id=args.project):
            success_count += 1

    if success_count == len(sql_files):
        verify_aggregations(client, args.project, args.dataset)
        show_sample_data(client, args.project, args.dataset)
        print("\n[SUCCESS] KPI aggregation tables built successfully!")
        return 0
    else:
        print(f"\n[ERROR] {len(sql_files) - success_count} aggregation(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
