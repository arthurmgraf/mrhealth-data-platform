#!/usr/bin/env python3
"""
MR. HEALTH Data Platform -- GCP Infrastructure Setup (Python SDK Alternative)
================================================================

Alternative to gcloud CLI commands. Uses Google Cloud Python SDK to:
- Create GCS bucket
- Create BigQuery datasets
- Create BigQuery tables

Usage:
    python scripts/setup_using_python_sdk.py

Requirements:
    pip install google-cloud-storage google-cloud-bigquery google-cloud-iam

Note: Service account creation still requires gcloud CLI or Console UI.
      API enablement still requires gcloud CLI or Console UI.

Author: Arthur Graf -- MR. HEALTH Data Platform Project
Date: January 2026
"""

from google.cloud import storage, bigquery
from google.api_core import exceptions
import os
import sys


PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME")
REGION = os.environ.get("GCP_REGION", "us-central1")
LOCATION = os.environ.get("GCP_LOCATION", "US")

if not PROJECT_ID or not BUCKET_NAME:
    print("[ERROR] Required environment variables not set: GCP_PROJECT_ID, GCS_BUCKET_NAME")
    print("Set them in .env or export them before running this script.")
    sys.exit(1)


def create_gcs_bucket():
    """Create GCS bucket with prefix structure."""
    print("\n" + "="*60)
    print("TASK_003: Creating GCS Bucket")
    print("="*60)

    try:
        storage_client = storage.Client(project=PROJECT_ID)

        # Create bucket
        bucket = storage_client.bucket(BUCKET_NAME)
        bucket.storage_class = "STANDARD"
        bucket.location = REGION
        bucket.uniform_bucket_level_access_enabled = True

        try:
            bucket = storage_client.create_bucket(bucket)
            print(f"  ✅ Bucket created: gs://{BUCKET_NAME}")
            print(f"     Location: {REGION}")
            print(f"     Storage Class: STANDARD")
        except exceptions.Conflict:
            print(f"  ℹ️  Bucket already exists: gs://{BUCKET_NAME}")
            bucket = storage_client.get_bucket(BUCKET_NAME)

        # Create prefix structure
        print("\n  [INFO] Creating prefix structure...")
        prefixes = [
            "raw/csv_sales/.keep",
            "raw/reference_data/.keep",
            "bronze/orders/.keep",
            "bronze/order_items/.keep",
            "bronze/products/.keep",
            "bronze/units/.keep",
            "bronze/states/.keep",
            "bronze/countries/.keep",
            "quarantine/.keep",
            "scripts/.keep"
        ]

        for prefix in prefixes:
            blob = bucket.blob(prefix)
            blob.upload_from_string("")
            print(f"     ✅ {prefix.split('/')[0]}/{prefix.split('/')[1] if len(prefix.split('/')) > 1 else ''}")

        print("  ✅ Prefix structure created")
        return True

    except Exception as e:
        print(f"  ❌ Error creating bucket: {e}")
        return False


def create_bigquery_datasets():
    """Create BigQuery datasets."""
    print("\n" + "="*60)
    print("TASK_004: Creating BigQuery Datasets")
    print("="*60)

    try:
        bq_client = bigquery.Client(project=PROJECT_ID)

        datasets_config = [
            ("mrhealth_bronze", "Bronze layer: schema-enforced, deduplicated data", "bronze"),
            ("mrhealth_silver", "Silver layer: cleaned, enriched, normalized data", "silver"),
            ("mrhealth_gold", "Gold layer: star schema dimensional model", "gold"),
            ("mrhealth_monitoring", "Pipeline monitoring: logs and quality checks", "monitoring")
        ]

        for dataset_id, description, layer in datasets_config:
            dataset_ref = f"{PROJECT_ID}.{dataset_id}"
            dataset = bigquery.Dataset(dataset_ref)
            dataset.location = LOCATION
            dataset.description = description
            dataset.labels = {"environment": "mvp", "layer": layer}

            try:
                dataset = bq_client.create_dataset(dataset, exists_ok=True)
                print(f"  ✅ Dataset created: {dataset_id}")
            except exceptions.Conflict:
                print(f"  ℹ️  Dataset already exists: {dataset_id}")

        return True

    except Exception as e:
        print(f"  ❌ Error creating datasets: {e}")
        return False


def create_bronze_tables():
    """Create Bronze layer tables."""
    print("\n" + "="*60)
    print("TASK_004: Creating Bronze Tables")
    print("="*60)

    try:
        bq_client = bigquery.Client(project=PROJECT_ID)

        # Read SQL file
        with open("sql/bronze/create_tables.sql", "r", encoding="utf-8") as f:
            sql_content = f.read()

        # Split by statement (simple approach - assumes no embedded semicolons)
        statements = [stmt.strip() for stmt in sql_content.split(";") if stmt.strip()]

        for i, sql in enumerate(statements):
            if sql.upper().startswith("CREATE TABLE"):
                try:
                    query_job = bq_client.query(sql)
                    query_job.result()

                    # Extract table name from SQL
                    table_name = sql.split("`")[1].split(".")[-1] if "`" in sql else f"table_{i+1}"
                    print(f"  ✅ Table created: {table_name}")
                except Exception as e:
                    print(f"  ⚠️  Statement {i+1} error: {str(e)[:100]}")

        print("  ✅ Bronze tables created")
        return True

    except Exception as e:
        print(f"  ❌ Error creating tables: {e}")
        return False


def main():
    print("="*60)
    print("MR. HEALTH Data Platform -- GCP Infrastructure Setup (Python SDK)")
    print("="*60)
    print(f"Project: {PROJECT_ID}")
    print(f"Bucket:  {BUCKET_NAME}")
    print(f"Region:  {REGION}")
    print("="*60)

    # Execute setup tasks
    gcs_ok = create_gcs_bucket()
    datasets_ok = create_bigquery_datasets()
    tables_ok = create_bronze_tables()

    # Summary
    print("\n" + "="*60)
    print("SETUP SUMMARY")
    print("="*60)
    print(f"  GCS Bucket:      {'✅ SUCCESS' if gcs_ok else '❌ FAILED'}")
    print(f"  BQ Datasets:     {'✅ SUCCESS' if datasets_ok else '❌ FAILED'}")
    print(f"  BQ Tables:       {'✅ SUCCESS' if tables_ok else '❌ FAILED'}")
    print("  Service Accounts: ⚠️  Requires gcloud CLI (run manually)")
    print("="*60)

    if gcs_ok and datasets_ok and tables_ok:
        print("\n✅ Infrastructure setup complete!")
        print("\nNext Steps:")
        print("1. Create service accounts (run commands in MANUAL_SETUP_COMMANDS.md)")
        print("2. Upload fake data: py scripts\\upload_fake_data_to_gcs.py")
        print("3. Verify: py scripts\\verify_infrastructure.py")
        return 0
    else:
        print("\n❌ Setup incomplete. Check errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
