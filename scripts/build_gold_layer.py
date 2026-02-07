#!/usr/bin/env python3
"""
MR. HEALTH Data Platform -- Build Gold Layer (Star Schema)
===========================================================

Executes SQL transformations to build the Gold layer star schema from Silver data.
Creates dimension tables (date, product, unit, geography) and fact tables (sales, order_items).

Usage:
    python scripts/build_gold_layer.py
    python scripts/build_gold_layer.py --project your-project-id

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


def verify_gold_layer(
    client: bigquery.Client,
    project_id: str,
    dataset_id: str = "mrhealth_gold",
) -> dict[str, int | None]:
    print("\n" + "=" * 60)
    print("Gold Layer Verification")
    print("=" * 60)

    tables = {
        "Dimensions": ["dim_date", "dim_product", "dim_unit", "dim_geography"],
        "Facts": ["fact_sales", "fact_order_items"],
    }

    results: dict[str, int | None] = {}
    for category, table_list in tables.items():
        print(f"\n{category}:")
        for table_name in table_list:
            table_id = f"{project_id}.{dataset_id}.{table_name}"
            try:
                query = f"SELECT COUNT(*) as row_count FROM `{table_id}`"
                result = client.query(query).result()
                row_count = list(result)[0].row_count
                results[table_name] = row_count
                print(f"  {table_name:20} {row_count:>8} rows")
            except Exception as e:
                print(f"  {table_name:20} [ERROR] {e}")
                results[table_name] = None

    print("=" * 60)
    return results


def test_star_schema_join(
    client: bigquery.Client,
    project_id: str,
    dataset_id: str = "mrhealth_gold",
) -> bool:
    print("\n" + "=" * 60)
    print("Star Schema Join Test")
    print("=" * 60)

    test_query = f"""
    SELECT
      d.year_month,
      u.state_name,
      u.unit_name,
      COUNT(DISTINCT f.order_id) AS total_orders,
      SUM(f.order_value) AS total_revenue,
      ROUND(AVG(f.order_value), 2) AS avg_order_value
    FROM `{project_id}.{dataset_id}.fact_sales` f
    JOIN `{project_id}.{dataset_id}.dim_date` d
      ON f.date_key = d.date_key
    JOIN `{project_id}.{dataset_id}.dim_unit` u
      ON f.unit_key = u.unit_key
    GROUP BY d.year_month, u.state_name, u.unit_name
    ORDER BY total_revenue DESC
    LIMIT 10
    """

    try:
        print("Running sample analytics query...")
        results = client.query(test_query).result()

        header = f"{'Year-Month':<12} {'State':<15} {'Unit':<20} {'Orders':>8} {'Revenue':>12} {'Avg Order':>10}"
        print(f"\n{header}")
        print("-" * 90)

        row_count = 0
        for row in results:
            print(
                f"{row.year_month or 'N/A':<12} {row.state_name or 'N/A':<15} "
                f"{row.unit_name or 'N/A':<20} {row.total_orders:>8} "
                f"{row.total_revenue:>12.2f} {row.avg_order_value:>10.2f}"
            )
            row_count += 1

        if row_count == 0:
            print("(No data - tables are empty, awaiting Cloud Function ingestion)")

        print("=" * 60)
        print("[OK] Star schema join successful!")
        return True

    except Exception as e:
        print(f"[ERROR] Star schema join failed: {e}")
        return False


def main() -> int:
    try:
        config = load_config()
        default_project = get_project_id(config)
        default_dataset = config["bigquery"]["datasets"]["gold"]
    except Exception as e:
        print(f"[ERROR] Failed to load config: {e}")
        return 1

    parser = argparse.ArgumentParser(description="Build Gold layer star schema from Silver data")
    parser.add_argument("--project", default=default_project, help="GCP project ID")
    parser.add_argument("--dataset", default=default_dataset, help="Gold dataset")
    args = parser.parse_args()

    print("=" * 60)
    print("MR. HEALTH Data Platform -- Build Gold Layer (Star Schema)")
    print("=" * 60)
    print(f"Project: {args.project}")
    print(f"Dataset: {args.dataset}")
    print(f"Time:    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    client = bigquery.Client(project=args.project)

    sql_dir = Path("sql/gold")
    sql_files = [
        (sql_dir / "01_dim_date.sql", "Date dimension (2025-2027)"),
        (sql_dir / "02_dim_product.sql", "Product dimension"),
        (sql_dir / "03_dim_unit.sql", "Unit dimension with geography"),
        (sql_dir / "04_dim_geography.sql", "Geography dimension"),
        (sql_dir / "05_fact_sales.sql", "Sales fact table (order-level)"),
        (sql_dir / "06_fact_order_items.sql", "Order items fact table (line-level)"),
    ]

    print("\n" + "=" * 60)
    print("Executing Gold Layer Transformations")
    print("=" * 60)

    success_count = 0
    for sql_file, description in sql_files:
        if execute_sql_file(client, sql_file, description, project_id=args.project):
            success_count += 1

    if success_count == len(sql_files):
        verify_gold_layer(client, args.project, args.dataset)
        test_star_schema_join(client, args.project, args.dataset)
        print("\n[SUCCESS] Gold layer (star schema) built successfully!")
        return 0
    else:
        print(f"\n[ERROR] {len(sql_files) - success_count} transformation(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
