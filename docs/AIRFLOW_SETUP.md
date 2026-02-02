# Airflow Setup Guide

Orchestrate the MR. Health Medallion pipeline (Bronze -> Silver -> Gold) using Apache Airflow running locally in Docker.

## Prerequisites

- Docker Desktop 24.x+ with Docker Compose V2
- GCP service account key with BigQuery and GCS permissions
- Existing Bronze layer data in BigQuery (from csv-processor Cloud Function)

## 1. Place GCP Credentials

Copy your service account JSON key into the `keys/` directory:

```bash
mkdir -p keys
cp /path/to/your-service-account.json keys/service-account.json
```

This directory is gitignored. The key is mounted into the Airflow container at `/opt/airflow/keys/service-account.json`.

## 2. Build the Airflow Image

```bash
docker compose -f docker-compose-airflow.yml build
```

This builds a custom image extending `apache/airflow:2.8-python3.11` with:
- `apache-airflow-providers-google` (GCS sensor, BigQuery operators)
- `google-cloud-bigquery` / `google-cloud-storage` (Python SDK)
- `pyyaml` (config loading)

## 3. Start Airflow

```bash
docker compose -f docker-compose-airflow.yml up -d
```

This starts 4 services:
1. **postgres** -- Airflow metadata database
2. **airflow-init** -- Runs database migration and creates admin user (exits after completion)
3. **airflow-webserver** -- Web UI at http://localhost:8080
4. **airflow-scheduler** -- Picks up and executes DAGs

Wait for all services to be healthy:

```bash
docker compose -f docker-compose-airflow.yml ps
```

Expected output shows `postgres`, `airflow-webserver`, and `airflow-scheduler` as healthy. `airflow-init` should show as exited (0).

## 4. Access the Airflow UI

Open http://localhost:8080 and login:

- **Username:** `admin`
- **Password:** `admin`

You should see the `mrhealth_daily_pipeline` DAG in the DAG list. It is unpaused by default.

## 5. DAG Overview

The `mrhealth_daily_pipeline` DAG runs daily at 02:00 BRT with 8 tasks:

```
sense_new_files -> validate_bronze -> build_silver
                                          |
                                    +-----+-----+
                                    |           |
                              build_dims   build_facts
                                    |           |
                                    +-----+-----+
                                          |
                                    build_aggs -> validate_gold -> notify_completion
```

| Task | Type | What it does |
|------|------|-------------|
| `sense_new_files` | GCS Sensor | Waits for CSV files in `raw/csv_sales/` (soft_fail: skips on timeout) |
| `validate_bronze` | BigQuery Check | Confirms Bronze `orders` table has rows |
| `build_silver` | Python | Executes `sql/silver/01-03` (reference tables, orders, order items) |
| `build_gold_dimensions` | Python | Executes `sql/gold/01-04` (date, product, unit, geography dims) |
| `build_gold_facts` | Python | Executes `sql/gold/05-06` (fact_sales, fact_order_items) |
| `build_aggregations` | Python | Executes `sql/gold/07-09` (daily sales, unit perf, product perf) |
| `validate_gold` | BigQuery Check | Confirms Gold `fact_sales` table has rows |
| `notify_completion` | Python | Logs row counts for key tables (runs even on partial failure) |

## 6. Trigger a Manual Run

1. In the Airflow UI, click the `mrhealth_daily_pipeline` DAG
2. Click the Play button (top right) -> "Trigger DAG"
3. Switch to Graph View to watch task execution
4. Green = success, yellow = running, red = failed, pink = skipped

The `sense_new_files` sensor will either find files in GCS and proceed, or timeout after 1 hour and skip (soft_fail). Downstream tasks still run using existing Bronze data.

## 7. Run DAG Integrity Tests

From the project root (requires `apache-airflow` installed locally):

```bash
pip install apache-airflow apache-airflow-providers-google pyyaml google-cloud-bigquery
pytest tests/unit/test_dag_integrity.py -v
```

These tests validate DAG structure (8 tasks, correct dependencies, tags, schedule) without requiring GCP credentials or a running Airflow instance.

## 8. Stop Airflow

```bash
docker compose -f docker-compose-airflow.yml down
```

To also remove the PostgreSQL data volume:

```bash
docker compose -f docker-compose-airflow.yml down -v
```

## 9. Troubleshooting

| Issue | Solution |
|-------|----------|
| DAG not visible in UI | Check logs: `docker compose -f docker-compose-airflow.yml logs airflow-scheduler` |
| Import error in DAG | Verify `config/project_config.yaml` exists and `keys/service-account.json` is in place |
| BigQuery auth failure | Check `GOOGLE_APPLICATION_CREDENTIALS` points to valid key: `docker compose -f docker-compose-airflow.yml exec airflow-scheduler env \| grep GOOGLE` |
| Port 8080 in use | Stop other services or change port in `docker-compose-airflow.yml` |
| Port 5432 conflict | If you have a local PostgreSQL, change the postgres port mapping or stop the local service |

## 10. Volume Mounts Reference

| Host Path | Container Path | Purpose |
|-----------|---------------|---------|
| `./dags/` | `/opt/airflow/dags/` | DAG definitions |
| `./scripts/` | `/opt/airflow/scripts/` | Build scripts (for future use) |
| `./sql/` | `/opt/airflow/sql/` | SQL transformation files |
| `./config/` | `/opt/airflow/config/` | Project configuration |
| `./keys/` | `/opt/airflow/keys/` | GCP credentials (gitignored) |
