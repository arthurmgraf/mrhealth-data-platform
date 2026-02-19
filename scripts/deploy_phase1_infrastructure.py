#!/usr/bin/env python3
"""
MR. HEALTH Data Platform -- Phase 1 Infrastructure Deployment
================================================

Creates BigQuery datasets and tables using Python SDK.
Reads project configuration from config/project_config.yaml.

Usage:
    python scripts/deploy_phase1_infrastructure.py

Requirements:
    pip install google-cloud-bigquery pyyaml

Prerequisites:
    gcloud auth application-default login

Author: Arthur Graf -- MR. HEALTH Data Platform Project
Date: January 2026
"""

import sys
from pathlib import Path

import yaml
from google.api_core import exceptions
from google.cloud import bigquery


def load_config():
    """Load project configuration from YAML."""
    config_path = Path("config/project_config.yaml")
    with open(config_path) as f:
        config = yaml.safe_load(f)
    return config


def create_bigquery_datasets(project_id, location="US"):
    """Create BigQuery datasets for Bronze, Silver, Gold, Monitoring."""
    print("\n" + "=" * 60)
    print("Creating BigQuery Datasets")
    print("=" * 60)

    try:
        client = bigquery.Client(project=project_id)

        datasets_config = [
            ("mrhealth_bronze", "Bronze layer: schema-enforced, deduplicated data", "bronze"),
            ("mrhealth_silver", "Silver layer: cleaned, enriched, normalized data", "silver"),
            ("mrhealth_gold", "Gold layer: star schema dimensional model", "gold"),
            ("mrhealth_monitoring", "Pipeline monitoring: logs and quality checks", "monitoring"),
        ]

        created_count = 0
        for dataset_id, description, layer in datasets_config:
            dataset_ref = f"{project_id}.{dataset_id}"
            dataset = bigquery.Dataset(dataset_ref)
            dataset.location = location
            dataset.description = description
            dataset.labels = {"environment": "mvp", "layer": layer}

            try:
                dataset = client.create_dataset(dataset, exists_ok=True)
                print(f"  [OK] Dataset created: {dataset_id}")
                created_count += 1
            except exceptions.Conflict:
                print(f"  [OK] Dataset already exists: {dataset_id}")
                created_count += 1
            except Exception as e:
                print(f"  [ERROR] Failed to create {dataset_id}: {e}")

        print(f"\n[SUMMARY] {created_count}/4 datasets ready")
        return created_count == 4

    except Exception as e:
        print(f"[ERROR] BigQuery client error: {e}")
        return False


def create_bronze_tables(project_id):
    """Create Bronze layer tables."""
    print("\n" + "=" * 60)
    print("Creating Bronze Tables")
    print("=" * 60)

    try:
        client = bigquery.Client(project=project_id)

        # Define table schemas
        tables = {
            "orders": [
                bigquery.SchemaField("id_unidade", "INTEGER", mode="REQUIRED"),
                bigquery.SchemaField("id_pedido", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("tipo_pedido", "STRING"),
                bigquery.SchemaField("data_pedido", "DATE"),
                bigquery.SchemaField("vlr_pedido", "NUMERIC"),
                bigquery.SchemaField("endereco_entrega", "STRING"),
                bigquery.SchemaField("taxa_entrega", "NUMERIC"),
                bigquery.SchemaField("status", "STRING"),
                bigquery.SchemaField("_source_file", "STRING"),
                bigquery.SchemaField("_ingest_timestamp", "TIMESTAMP"),
                bigquery.SchemaField("_ingest_date", "DATE"),
            ],
            "order_items": [
                bigquery.SchemaField("id_pedido", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("id_item_pedido", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("id_produto", "INTEGER"),
                bigquery.SchemaField("qtd", "INTEGER"),
                bigquery.SchemaField("vlr_item", "NUMERIC"),
                bigquery.SchemaField("observacao", "STRING"),
                bigquery.SchemaField("_source_file", "STRING"),
                bigquery.SchemaField("_ingest_timestamp", "TIMESTAMP"),
                bigquery.SchemaField("_ingest_date", "DATE"),
            ],
            "products": [
                bigquery.SchemaField("id_produto", "INTEGER", mode="REQUIRED"),
                bigquery.SchemaField("nome_produto", "STRING"),
                bigquery.SchemaField("_ingest_timestamp", "TIMESTAMP"),
            ],
            "units": [
                bigquery.SchemaField("id_unidade", "INTEGER", mode="REQUIRED"),
                bigquery.SchemaField("nome_unidade", "STRING"),
                bigquery.SchemaField("id_estado", "INTEGER"),
                bigquery.SchemaField("_ingest_timestamp", "TIMESTAMP"),
            ],
            "states": [
                bigquery.SchemaField("id_estado", "INTEGER", mode="REQUIRED"),
                bigquery.SchemaField("id_pais", "INTEGER"),
                bigquery.SchemaField("nome_estado", "STRING"),
                bigquery.SchemaField("_ingest_timestamp", "TIMESTAMP"),
            ],
            "countries": [
                bigquery.SchemaField("id_pais", "INTEGER", mode="REQUIRED"),
                bigquery.SchemaField("nome_pais", "STRING"),
                bigquery.SchemaField("_ingest_timestamp", "TIMESTAMP"),
            ],
        }

        created_count = 0
        for table_name, schema in tables.items():
            table_ref = f"{project_id}.mrhealth_bronze.{table_name}"
            table = bigquery.Table(table_ref, schema=schema)

            # Partition by _ingest_date for orders and order_items
            if table_name in ["orders", "order_items"]:
                table.time_partitioning = bigquery.TimePartitioning(
                    type_=bigquery.TimePartitioningType.DAY, field="_ingest_date"
                )

            try:
                table = client.create_table(table, exists_ok=True)
                print(f"  [OK] Table created: {table_name}")
                created_count += 1
            except exceptions.Conflict:
                print(f"  [OK] Table already exists: {table_name}")
                created_count += 1
            except Exception as e:
                print(f"  [ERROR] Failed to create {table_name}: {e}")

        print(f"\n[SUMMARY] {created_count}/6 Bronze tables ready")
        return created_count == 6

    except Exception as e:
        print(f"[ERROR] BigQuery client error: {e}")
        return False


def main():
    print("=" * 60)
    print("MR. HEALTH Data Platform -- Phase 1 Infrastructure Deployment")
    print("=" * 60)

    # Load configuration
    try:
        config = load_config()
        project_id = config["project"]["id"]
        bucket_name = config["storage"]["bucket"]
        location = config["bigquery"]["location"]

        print(f"Project:  {project_id}")
        print(f"Bucket:   gs://{bucket_name}/")
        print(f"Location: {location}")
    except Exception as e:
        print(f"[ERROR] Failed to load config: {e}")
        return 1

    # Execute infrastructure setup
    datasets_ok = create_bigquery_datasets(project_id, location)
    tables_ok = create_bronze_tables(project_id)

    # Summary
    print("\n" + "=" * 60)
    print("DEPLOYMENT SUMMARY")
    print("=" * 60)
    print(f"  BigQuery Datasets: {'[OK]' if datasets_ok else '[FAILED]'}")
    print(f"  Bronze Tables:     {'[OK]' if tables_ok else '[FAILED]'}")
    print("=" * 60)

    if datasets_ok and tables_ok:
        print("\n[SUCCESS] Phase 1 infrastructure deployed!")
        print("\nNext Steps:")
        print("  1. Upload data: py scripts\\upload_fake_data_to_gcs.py")
        print("  2. Verify: py scripts\\verify_infrastructure.py")
        return 0
    else:
        print("\n[ERROR] Deployment incomplete")
        return 1


if __name__ == "__main__":
    sys.exit(main())
