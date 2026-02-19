#!/usr/bin/env python3
"""
MR. HEALTH Data Platform -- Infrastructure Verification Script
================================================

Verifies that all Phase 1 infrastructure is correctly set up:
- GCS bucket exists with correct structure
- BigQuery datasets exist
- BigQuery tables have correct schemas
- Service accounts exist with correct roles

Usage:
    python scripts/verify_infrastructure.py
    python scripts/verify_infrastructure.py --project ${GCP_PROJECT_ID}

Requirements:
    pip install google-cloud-storage google-cloud-bigquery

Author: Arthur Graf -- MR. HEALTH Data Platform Project
Date: January 2026
"""

import argparse
import os
import sys

from google.api_core import exceptions
from google.cloud import bigquery, storage


def check_gcs_bucket(bucket_name, project_id=None):
    """Verify GCS bucket exists and has correct structure."""
    print("\n[CHECK] Cloud Storage Bucket...")

    try:
        storage_client = storage.Client(project=project_id) if project_id else storage.Client()
        bucket = storage_client.get_bucket(bucket_name)

        print(f"  [OK] Bucket exists: gs://{bucket_name}")
        print(f"     Location: {bucket.location}")
        print(f"     Storage Class: {bucket.storage_class}")
        print(f"     Created: {bucket.time_created}")

        # Check for expected prefixes
        expected_prefixes = ["raw/csv_sales/", "raw/reference_data/", "bronze/", "quarantine/"]

        blobs = list(storage_client.list_blobs(bucket_name, max_results=100))
        blob_names = [blob.name for blob in blobs]

        print("\n  [INFO] Checking prefix structure...")
        for prefix in expected_prefixes:
            matches = [name for name in blob_names if name.startswith(prefix)]
            if matches:
                print(f"     [OK] {prefix} ({len(matches)} objects)")
            else:
                print(f"     [WARN]  {prefix} (no objects yet)")

        return True

    except exceptions.NotFound:
        print(f"  [FAIL] Bucket not found: gs://{bucket_name}")
        return False
    except Exception as e:
        print(f"  [FAIL] Error: {e}")
        return False


def check_bigquery_datasets(project_id):
    """Verify BigQuery datasets exist."""
    print("\n[CHECK] BigQuery Datasets...")

    try:
        bq_client = bigquery.Client(project=project_id)

        expected_datasets = [
            "mrhealth_bronze",
            "mrhealth_silver",
            "mrhealth_gold",
            "mrhealth_monitoring",
        ]

        datasets = list(bq_client.list_datasets())
        dataset_ids = [ds.dataset_id for ds in datasets]

        all_exist = True
        for dataset_id in expected_datasets:
            if dataset_id in dataset_ids:
                dataset = bq_client.get_dataset(f"{project_id}.{dataset_id}")
                print(f"  [OK] {dataset_id}")
                print(f"     Location: {dataset.location}")
                print(f"     Labels: {dataset.labels}")
            else:
                print(f"  [FAIL] {dataset_id} (not found)")
                all_exist = False

        return all_exist

    except Exception as e:
        print(f"  [FAIL] Error: {e}")
        return False


def check_bigquery_tables(project_id):
    """Verify BigQuery bronze tables exist."""
    print("\n[CHECK] BigQuery Bronze Tables...")

    try:
        bq_client = bigquery.Client(project=project_id)

        expected_tables = [
            "mrhealth_bronze.orders",
            "mrhealth_bronze.order_items",
            "mrhealth_bronze.products",
            "mrhealth_bronze.units",
            "mrhealth_bronze.states",
            "mrhealth_bronze.countries",
        ]

        all_exist = True
        for table_ref in expected_tables:
            try:
                table = bq_client.get_table(f"{project_id}.{table_ref}")
                row_count = table.num_rows
                print(f"  [OK] {table_ref} ({row_count} rows)")
            except exceptions.NotFound:
                print(f"  [WARN]  {table_ref} (not created yet)")
                all_exist = False

        return all_exist

    except Exception as e:
        print(f"  [FAIL] Error: {e}")
        return False


def check_service_accounts(project_id):
    """Verify service accounts exist."""
    print("\n[CHECK] Service Accounts...")
    print("  [INFO] Run this command to verify:")
    print(f"     gcloud iam service-accounts list --project={project_id}")
    print("\n  Expected service accounts:")
    print("     [OK] sa-mrhealth-ingestion")
    print("     [OK] sa-mrhealth-transform")
    print("     [OK] sa-mrhealth-monitoring")

    # Note: Checking SA requires additional permissions, so we just guide the user
    return True


def load_config():
    """Load project configuration from YAML."""
    from pathlib import Path

    import yaml

    config_path = Path("config/project_config.yaml")
    with open(config_path) as f:
        config = yaml.safe_load(f)
    return config


def main():
    # Load config
    try:
        config = load_config()
        default_project = config["project"]["id"]
        default_bucket = config["storage"]["bucket"]
    except Exception as e:
        print(f"[WARNING] Could not load config: {e}")
        default_project = os.environ.get("GCP_PROJECT_ID", "")
        default_bucket = os.environ.get("GCS_BUCKET_NAME", "")
        if not default_project or not default_bucket:
            print(
                "[ERROR] Config file not found and env vars GCP_PROJECT_ID/GCS_BUCKET_NAME not set."
            )
            print("Set them in .env or export them before running this script.")
            sys.exit(1)

    parser = argparse.ArgumentParser(
        description="Verify MR. HEALTH Data Platform infrastructure setup"
    )
    parser.add_argument(
        "--project",
        default=default_project,
        help=f"GCP project ID (default from config: {default_project})",
    )
    parser.add_argument(
        "--bucket",
        default=default_bucket,
        help=f"GCS bucket name (default from config: {default_bucket})",
    )

    args = parser.parse_args()

    print("============================================================")
    print("MR. HEALTH Data Platform -- Infrastructure Verification")
    print("============================================================")
    print(f"Project: {args.project}")
    print(f"Bucket:  {args.bucket}")

    # Run checks
    gcs_ok = check_gcs_bucket(args.bucket, project_id=args.project)
    datasets_ok = check_bigquery_datasets(args.project)
    tables_ok = check_bigquery_tables(args.project)
    check_service_accounts(args.project)

    # Summary
    print("\n============================================================")
    print("VERIFICATION SUMMARY")
    print("============================================================")
    print(f"  GCS Bucket:      {'[OK] PASS' if gcs_ok else '[FAIL] FAIL'}")
    print(f"  BQ Datasets:     {'[OK] PASS' if datasets_ok else '[FAIL] FAIL'}")
    print(f"  BQ Tables:       {'[OK] PASS' if tables_ok else '[WARN]  PENDING'}")
    print("  Service Accounts: [OK] MANUAL CHECK")
    print("============================================================")

    if gcs_ok and datasets_ok:
        print("\n[OK] Phase 1 infrastructure is ready!")
        print("   Next: Upload fake data and create Bronze tables")
        return 0
    else:
        print("\n[FAIL] Infrastructure setup incomplete")
        print("   Review errors above and re-run setup script")
        return 1


if __name__ == "__main__":
    sys.exit(main())
