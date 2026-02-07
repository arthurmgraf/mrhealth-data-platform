#!/usr/bin/env python3
"""
MR. HEALTH Data Platform -- Load Reference Data into BigQuery Bronze
=======================================================

Loads static reference data (products, units, states, countries) from GCS
into BigQuery Bronze layer tables.

Usage:
    python scripts/load_reference_data.py
    python scripts/load_reference_data.py --project ${PROJECT_ID}

Requirements:
    pip install google-cloud-bigquery pyyaml

Author: Arthur Graf -- MR. HEALTH Data Platform Project
Date: January 2026
"""

import argparse
import sys
import yaml
from pathlib import Path
from google.cloud import bigquery
from datetime import datetime


def load_config():
    """Load project configuration from YAML."""
    config_path = Path("config/project_config.yaml")
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config


# Mapping: CSV filename -> BigQuery table name
TABLE_MAPPING = {
    "produto.csv": "products",
    "unidade.csv": "units",
    "estado.csv": "states",
    "pais.csv": "countries",
}


def load_reference_tables(project_id, bucket_name, dataset_id="mrhealth_bronze"):
    """Load reference CSVs from GCS into BigQuery Bronze tables."""
    print("\n" + "="*60)
    print("Loading Reference Data into BigQuery Bronze")
    print("="*60)

    client = bigquery.Client(project=project_id)
    gcs_prefix = "raw/reference_data"

    loaded_count = 0
    total_rows = 0

    for csv_name, table_name in TABLE_MAPPING.items():
        table_id = f"{project_id}.{dataset_id}.{table_name}"
        uri = f"gs://{bucket_name}/{gcs_prefix}/{csv_name}"

        print(f"\n[LOADING] {csv_name} -> {table_name}")
        print(f"  Source: {uri}")

        # Configure load job
        job_config = bigquery.LoadJobConfig(
            skip_leading_rows=1,  # Skip header row
            source_format=bigquery.SourceFormat.CSV,
            field_delimiter=";",  # Brazilian CSV format
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,  # Replace existing data
            autodetect=True,  # Auto-detect schema from CSV
        )

        try:
            # Start load job
            load_job = client.load_table_from_uri(uri, table_id, job_config=job_config)
            load_job.result()  # Wait for completion

            # Get updated table info
            table = client.get_table(table_id)
            row_count = table.num_rows
            total_rows += row_count

            print(f"  [OK] Loaded {row_count} rows into {table_id}")

            # Try to add _ingest_timestamp if column doesn't exist
            try:
                alter_query = f"""
                    ALTER TABLE `{table_id}`
                    ADD COLUMN IF NOT EXISTS _ingest_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
                """
                alter_job = client.query(alter_query)
                alter_job.result()
                print(f"  [OK] Added _ingest_timestamp column")
            except Exception as alter_error:
                print(f"  [INFO] _ingest_timestamp column already exists or cannot be added")

            loaded_count += 1

        except Exception as e:
            print(f"  [ERROR] Failed to load {csv_name}: {e}")
            continue

    print("\n" + "="*60)
    print("LOAD SUMMARY")
    print("="*60)
    print(f"  Tables loaded:  {loaded_count}/{len(TABLE_MAPPING)}")
    print(f"  Total rows:     {total_rows}")
    print(f"  Dataset:        {dataset_id}")
    print("="*60)

    return loaded_count == len(TABLE_MAPPING)


def verify_reference_data(project_id, dataset_id="mrhealth_bronze"):
    """Verify reference data row counts in BigQuery."""
    print("\n" + "="*60)
    print("Verification - Reference Data Row Counts")
    print("="*60)

    client = bigquery.Client(project=project_id)

    for csv_name, table_name in TABLE_MAPPING.items():
        table_id = f"{project_id}.{dataset_id}.{table_name}"

        try:
            query = f"SELECT COUNT(*) as row_count FROM `{table_id}`"
            result = client.query(query).result()
            row_count = list(result)[0].row_count
            print(f"  {table_name:12} {row_count:>4} rows")
        except Exception as e:
            print(f"  {table_name:12} [ERROR] {e}")

    print("="*60)


def main():
    # Load config
    try:
        config = load_config()
        default_project = config['project']['id']
        default_bucket = config['storage']['bucket']
        default_dataset = config['bigquery']['datasets']['bronze']
    except Exception as e:
        print(f"[ERROR] Failed to load config: {e}")
        return 1

    parser = argparse.ArgumentParser(
        description="Load reference data from GCS to BigQuery Bronze"
    )
    parser.add_argument(
        "--project",
        default=default_project,
        help=f"GCP project ID (default from config: {default_project})"
    )
    parser.add_argument(
        "--bucket",
        default=default_bucket,
        help=f"GCS bucket name (default from config: {default_bucket})"
    )
    parser.add_argument(
        "--dataset",
        default=default_dataset,
        help=f"BigQuery dataset (default from config: {default_dataset})"
    )

    args = parser.parse_args()

    print("="*60)
    print("MR. HEALTH Data Platform -- Load Reference Data")
    print("="*60)
    print(f"Project: {args.project}")
    print(f"Bucket:  gs://{args.bucket}/")
    print(f"Dataset: {args.dataset}")

    # Load reference data
    success = load_reference_tables(args.project, args.bucket, args.dataset)

    if success:
        # Verify loaded data
        verify_reference_data(args.project, args.dataset)

        print("\n[SUCCESS] Reference data loaded into BigQuery Bronze!")
        print("\nNext: Deploy Cloud Function for CSV ingestion")
        return 0
    else:
        print("\n[ERROR] Reference data load incomplete")
        return 1


if __name__ == "__main__":
    sys.exit(main())
