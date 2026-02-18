# MR. HEALTH Data Platform

Enterprise-grade data warehouse on GCP Free Tier ($0/month). Event-driven ingestion, Medallion architecture (Bronze/Silver/Gold), Kimball Star Schema, Apache Airflow orchestration, full observability stack.

Built for a 50-unit restaurant chain processing ~100 CSVs/day.

---

## Key Metrics

| Metric | Value |
|---|---|
| Monthly Cost | **$0.00** (GCP permanent Free Tier) |
| End-to-End Latency | < 3 minutes (CSV upload to dashboard) |
| Pipeline Availability | 99%+ (K3s self-healing) |
| Data Quality Checks | 6 automated (freshness, completeness, accuracy, uniqueness, referential, volume) |
| Airflow DAGs | 5 (daily pipeline, quality, retention, reference refresh, backfill monitor) |
| SQL Transformations | 15 scripts across Bronze/Silver/Gold |
| Dashboards | 4 Superset + 2 Grafana |

---

## Architecture

```
POS (50 Units)  ──CSV──>  GCS (Data Lake)  ──Eventarc──>  Cloud Function  ──>  BigQuery Bronze
                                                                                      |
PostgreSQL (K3s)  ──SSH Tunnel──>  Cloud Function  ──CSV──>  GCS  ──>          BigQuery Silver
                                                                                      |
                                                                               BigQuery Gold
                                                                            (Star Schema + Agg)
                                                                                      |
                                                                    ┌─────────────────┴─────────────────┐
                                                             Apache Superset              Grafana
                                                              (4 dashboards)          (2 dashboards)
```

### Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Ingestion** | Cloud Functions (2nd Gen) + Eventarc | Event-driven CSV processing, schema validation, dedup |
| **Storage** | Cloud Storage (GCS) | Data lake with raw/reference/quarantine prefixes |
| **Warehouse** | BigQuery (Bronze/Silver/Gold) | Medallion architecture, Kimball Star Schema |
| **Orchestration** | Apache Airflow 2.8 on K3s | 5 DAGs: pipeline, quality, retention, refresh, backfill |
| **Reference Data** | PostgreSQL 16 on K3s | Master data (products, units, states, countries) |
| **Visualization** | Apache Superset 4.0.2 | 4 dashboards: Executive, Unit, Product, Order Detail |
| **Monitoring** | Prometheus + Grafana 11.4 | K3s infrastructure + Airflow metrics dashboards |
| **Infrastructure** | K3s (single-node) | All services: PostgreSQL, Airflow, Superset, Grafana, Prometheus |

### Key Design Decisions

| Decision | Choice | Why |
|---|---|---|
| Ingestion pattern | Event-driven (Eventarc) | Zero polling, instant processing on upload |
| Warehouse | BigQuery | Serverless, 1 TB/mo free queries, native partitioning |
| Modeling | Kimball Star Schema | 4 dims + 2 facts + 3 aggs, optimal for BI queries |
| Orchestration | Airflow on K3s | Full DAG control, hostPath volumes, LocalExecutor |
| BI tool | Superset 4.0.2 | Open-source, BigQuery native, self-hosted on K3s |
| Config | Parameterized SQL (`{PROJECT_ID}`) | Environment-agnostic, single config source |

---

## Data Model

### Medallion Layers

| Layer | Dataset | Tables | Purpose |
|---|---|---|---|
| **Bronze** | `mrhealth_bronze` | 6 (orders, order_items, products, units, states, countries) | Schema-enforced raw data with ingestion metadata |
| **Silver** | `mrhealth_silver` | 6 (orders, order_items, products, units, states, countries) | Cleaned, deduplicated, type-normalized, date-enriched |
| **Gold** | `mrhealth_gold` | 9 (4 dims + 2 facts + 3 aggs) | Kimball Star Schema for analytics |
| **Monitoring** | `mrhealth_monitoring` | 3 (quality_log, pipeline_metrics, free_tier_usage) | Automated quality tracking |

### Star Schema (Gold)

```
                     dim_date
                        |
        dim_product --- fact_sales --- dim_unit --- dim_geography
                        |
                  fact_order_items

  Aggregations: agg_daily_sales, agg_unit_performance, agg_product_performance
```

| Table | Grain | Key Measures |
|---|---|---|
| `fact_sales` | One row per order | order_value, delivery_fee, total_items |
| `fact_order_items` | One row per line item | quantity, unit_price, total_item_value |
| `dim_date` | One row per date (2025-2027) | year, month, day_of_week, is_weekend |
| `dim_product` | One row per product | product_name (30 health food items) |
| `dim_unit` | One row per unit | unit_name, state_name, country_name |
| `dim_geography` | One row per state | state, country, region |

---

## Airflow Orchestration

5 production DAGs running on K3s with LocalExecutor:

| DAG | Schedule | Tasks | Purpose |
|---|---|---|---|
| `mrhealth_daily_pipeline` | `0 2 * * *` | 10 | Full Medallion: sense files → Silver → Gold dims/facts → Aggs → Quality |
| `mrhealth_data_quality` | `0 3 * * *` | 8 | 6 parallel quality checks + save results + alert |
| `mrhealth_data_retention` | `0 4 * * 0` | 5 | Archive Bronze > 90d, cleanup GCS > 60d, Free Tier usage |
| `mrhealth_reference_refresh` | `0 1 * * *` | 3 | Trigger PostgreSQL → GCS extraction |
| `mrhealth_backfill_monitor` | `0 6 * * 1` | 3 | Detect missing dates, trigger regeneration |

### Custom Components

- **`BigQueryDataQualityOperator`**: Executes SQL quality checks, records to monitoring
- **`GCSObjectsWithPrefixExistenceSensor`**: Soft-fail sensor for CSV detection
- **`DataQualityChecker`**: 6-check framework (freshness, completeness, accuracy, uniqueness, referential, volume)
- **Alert callbacks**: SLA miss, task failure, quality failure → BigQuery metrics

---

## Observability

### Apache Superset (4 dashboards)

| Dashboard | Key Charts | Filters |
|---|---|---|
| Executive Overview | Total revenue, order trends, channel mix | Date range, state, status |
| Unit Performance | Revenue ranking, cancellation rate, online % | Date range, unit, state |
| Product Analytics | Product revenue, volume ranking, unit penetration | Date range, product |
| Order Detail | Order-level drill-down with item breakdown | Date range, unit, status |

### Grafana (2 dashboards)

| Dashboard | Data Source | Panels |
|---|---|---|
| K3s Infrastructure | Prometheus | CPU, memory, disk, pod status, network |
| Airflow Metrics | Prometheus (StatsD) | DAG runs, task duration, success rate |

### Prometheus Stack

- **Prometheus** (`:30090`): Metrics collection
- **Node Exporter** (`:9100`): Host metrics
- **StatsD Exporter** (`:9125`): Airflow metrics bridge

---

## Repository Structure

```
mrhealth-data-platform/
├── cloud_functions/                 # 3 Cloud Functions (deployed to GCP)
│   ├── csv_processor/               # Event-driven CSV → BigQuery Bronze
│   ├── data_generator/              # HTTP-triggered fake data generator
│   └── pg_reference_extractor/      # PostgreSQL → GCS via SSH tunnel
├── config/
│   └── project_config.yaml          # Centralized configuration (all settings)
├── dags/                            # 5 Airflow DAGs
│   ├── mrhealth_daily_pipeline.py   # Bronze → Silver → Gold → Agg → Quality
│   ├── mrhealth_data_quality.py     # 6 automated quality checks
│   ├── mrhealth_data_retention.py   # Storage cleanup + Free Tier monitoring
│   ├── mrhealth_reference_refresh.py # PostgreSQL extraction trigger
│   └── mrhealth_backfill_monitor.py # Gap detection + regeneration
├── plugins/mrhealth/                # Airflow custom components
│   ├── callbacks/alerts.py          # SLA miss, failure, quality callbacks
│   ├── config/loader.py             # Centralized config loader
│   ├── operators/bigquery_quality.py # Custom quality check operator
│   ├── quality/checks.py           # 6-check data quality framework
│   └── sensors/                     # Custom sensors
├── scripts/                         # Operational scripts (run locally)
│   ├── utils/                       # Shared utilities (DRY)
│   │   ├── config.py                # Config loader with env var substitution
│   │   └── sql_executor.py          # BigQuery SQL file executor
│   ├── constants.py                 # Shared constants (product catalog, etc.)
│   ├── generate_fake_sales.py       # Synthetic data generator (Faker)
│   ├── deploy_phase1_infrastructure.py
│   ├── build_silver_layer.py
│   ├── build_gold_layer.py
│   ├── build_aggregations.py
│   └── verify_infrastructure.py
├── sql/                             # 15 SQL scripts by Medallion layer
│   ├── bronze/                      # 1 DDL (6 tables)
│   ├── silver/                      # 3 transforms
│   ├── gold/                        # 9 (4 dims + 2 facts + 3 aggs)
│   └── monitoring/                  # 3 monitoring tables
├── k8s/                             # Kubernetes manifests
│   ├── airflow/                     # Webserver, scheduler, configmap
│   ├── grafana/                     # Dashboards, datasources, deployment
│   ├── postgresql/                  # Deployment, service, PVC, secret
│   ├── prometheus/                  # Prometheus + exporters
│   └── superset/                    # Deployment, service, config
├── infra/                           # Terraform IaC
│   ├── modules/                     # Reusable modules (bigquery, gcs, cf, iam, monitoring, scheduler)
│   └── environments/prod/           # Production Terragrunt config
├── tests/
│   ├── unit/                        # Unit tests (pytest)
│   └── integration/                 # PostgreSQL connectivity tests
├── docs/                            # Technical documentation
├── diagrams/                        # Architecture diagrams (Excalidraw)
├── superset/                        # Superset Dockerfile (4.0.2)
├── airflow/                         # Airflow Dockerfile (2.8-python3.11)
├── pyproject.toml                   # Python config (Ruff, pytest)
└── requirements.txt                 # Python dependencies
```

---

## Getting Started

### Prerequisites

- GCP account (free tier, no credit card required for BigQuery/GCS)
- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install)
- Python 3.11+
- K3s cluster (for Airflow/Superset/Grafana)

### Quick Setup

```bash
# Clone and configure
git clone <repository-url>
cd mrhealth-data-platform
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Edit .env with your GCP project ID and bucket name

# Authenticate with GCP
gcloud auth login
gcloud auth application-default login
gcloud config set project $GCP_PROJECT_ID

# Create BigQuery infrastructure
python scripts/deploy_phase1_infrastructure.py

# Generate and upload test data
python scripts/generate_fake_sales.py
python scripts/upload_fake_data_to_gcs.py
python scripts/load_reference_data.py

# Deploy Cloud Function
cd cloud_functions/csv_processor
gcloud functions deploy csv-processor \
  --gen2 --runtime=python311 --region=us-central1 --source=. \
  --entry-point=process_csv \
  --trigger-event-filters="type=google.cloud.storage.object.v1.finalized" \
  --trigger-event-filters="bucket=$GCS_BUCKET_NAME" \
  --memory=256MB --timeout=300s \
  --set-env-vars="PROJECT_ID=$GCP_PROJECT_ID,BUCKET_NAME=$GCS_BUCKET_NAME,BQ_DATASET=mrhealth_bronze"
cd ../..

# Build transformation layers
python scripts/build_silver_layer.py
python scripts/build_gold_layer.py
python scripts/build_aggregations.py

# Verify
python scripts/verify_infrastructure.py
```

### K3s Services

```bash
# Apply Kubernetes manifests
kubectl apply -f k8s/postgresql/
kubectl apply -f k8s/airflow/
kubectl apply -f k8s/superset/
kubectl apply -f k8s/grafana/
kubectl apply -f k8s/prometheus/
```

| Service | Port | URL |
|---|---|---|
| Airflow Webserver | 30080 | `http://<server-ip>:30080` |
| Apache Superset | 30188 | `http://<server-ip>:30188` |
| Grafana | 30300 | `http://<server-ip>:30300` |
| Prometheus | 30090 | `http://<server-ip>:30090` |
| PostgreSQL | 30432 | `psql -h <server-ip> -p 30432 -U mrhealth_admin -d mrhealth` |

---

## Testing

```bash
pytest tests/ -v --cov=scripts --cov-report=term-missing
```

---

## Cost Analysis

| Service | Free Tier Limit | Actual Usage | Utilization |
|---|---|---|---|
| Cloud Storage | 5 GB | ~1 MB | 0.02% |
| BigQuery Storage | 10 GB | ~2 MB | 0.02% |
| BigQuery Queries | 1 TB/month | ~10 GB | 1% |
| Cloud Functions | 2M invocations/month | ~3K | 0.15% |
| K3s (self-hosted) | Unlimited | All services | $0 |

**Total: $0.00/month.** All GCP services use permanent Free Tier (not a trial).

---

## Documentation

| Document | Description |
|---|---|
| [Setup Guide](docs/SETUP_GUIDE.md) | Step-by-step replication guide |
| [Architecture](docs/ARCHITECTURE.md) | Technical deep-dive: layers, data models, security |
| [Data Catalog](docs/DATA_CATALOG.md) | Table schemas, lineage, refresh schedules |
| [Dashboard Guide](docs/SUPERSET_SETUP.md) | Apache Superset dashboard configuration |

---

## Author

**Arthur Maia Graf**

[LinkedIn](https://linkedin.com) | [GitHub](https://github.com)
