#!/usr/bin/env python3
"""
MR. HEALTH Data Platform -- Upload Fake Data to GCS
======================================

Uploads locally generated fake data to the GCS landing zone.
This simulates the daily upload process from the 50 units.

Usage:
    python scripts/upload_fake_data_to_gcs.py
    python scripts/upload_fake_data_to_gcs.py --bucket mrhealth-datalake-485810 --local-dir output

Requirements:
    pip install google-cloud-storage pyyaml

Author: Arthur Graf -- MR. HEALTH Data Platform Project
Date: January 2026
"""

import argparse
import os
from pathlib import Path

import yaml
from google.cloud import storage


def upload_directory_to_gcs(bucket_name, local_directory, gcs_prefix="", project_id=None):
    """
    Uploads a local directory structure to GCS, preserving the directory hierarchy.

    Args:
        bucket_name: GCS bucket name
        local_directory: Local directory path to upload
        gcs_prefix: GCS prefix (folder) to upload to
        project_id: GCP project ID (optional)
    """
    storage_client = storage.Client(project=project_id) if project_id else storage.Client()
    bucket = storage_client.bucket(bucket_name)

    local_path = Path(local_directory)
    uploaded_count = 0

    print(f"\n[INFO] Uploading from: {local_path}")
    print(f"[INFO] To bucket: gs://{bucket_name}/{gcs_prefix}")
    print("[INFO] Scanning files...\n")

    # Walk through all files in the directory
    for file_path in local_path.rglob("*"):
        if file_path.is_file():
            # Calculate relative path from local_directory
            relative_path = file_path.relative_to(local_path)

            # Construct GCS blob name
            if gcs_prefix:
                blob_name = f"{gcs_prefix}/{relative_path}".replace("\\", "/")
            else:
                blob_name = str(relative_path).replace("\\", "/")

            # Upload file
            blob = bucket.blob(blob_name)
            blob.upload_from_filename(str(file_path))

            uploaded_count += 1
            print(f"  [OK] {blob_name}")

    print(f"\n[COMPLETE] Uploaded {uploaded_count} files to gs://{bucket_name}/{gcs_prefix}")
    return uploaded_count


def load_config():
    """Load project configuration from YAML."""
    config_path = Path("config/project_config.yaml")
    with open(config_path) as f:
        config = yaml.safe_load(f)
    return config


def main():
    # Load config
    try:
        config = load_config()
        default_bucket = config["storage"]["bucket"]
        project_id = config["project"]["id"]
    except Exception as e:
        print(f"[WARNING] Could not load config: {e}")
        default_bucket = os.environ.get("GCS_BUCKET_NAME", "")
        project_id = os.environ.get("GCP_PROJECT_ID", "")
        if not default_bucket or not project_id:
            print(
                "[ERROR] Config file not found and env vars GCP_PROJECT_ID/GCS_BUCKET_NAME not set."
            )
            print("Set them in .env or export them before running this script.")
            return 1

    parser = argparse.ArgumentParser(description="Upload fake data to GCS landing zone")
    parser.add_argument(
        "--bucket",
        default=default_bucket,
        help=f"GCS bucket name (default from config: {default_bucket})",
    )
    parser.add_argument(
        "--local-dir",
        default="output",
        help="Local directory containing generated data (default: output)",
    )

    args = parser.parse_args()

    print(f"Using project: {project_id}")

    print("============================================================")
    print("MR. HEALTH Data Platform -- Upload Fake Data to GCS")
    print("============================================================")

    # Verify local directory exists
    if not os.path.exists(args.local_dir):
        print(f"[ERROR] Local directory not found: {args.local_dir}")
        print("[HINT] Run: python scripts/generate_fake_sales.py first")
        return 1

    # Upload reference data
    print("\n[STEP 1] Uploading reference data...")
    ref_count = upload_directory_to_gcs(
        args.bucket,
        os.path.join(args.local_dir, "reference_data"),
        "raw/reference_data",
        project_id=project_id,
    )

    # Upload sales CSV data
    print("\n[STEP 2] Uploading sales data...")
    sales_count = upload_directory_to_gcs(
        args.bucket,
        os.path.join(args.local_dir, "csv_sales"),
        "raw/csv_sales",
        project_id=project_id,
    )

    # Summary
    print("\n============================================================")
    print("UPLOAD SUMMARY")
    print("============================================================")
    print(f"  Reference data files: {ref_count}")
    print(f"  Sales data files:     {sales_count}")
    print(f"  Total uploaded:       {ref_count + sales_count}")
    print(f"\n  Bucket: gs://{args.bucket}")
    print("============================================================")
    print("\nNext: Verify upload with:")
    print(f"  gsutil ls -r gs://{args.bucket}/raw/")
    print("")

    return 0


if __name__ == "__main__":
    exit(main())
