> Documentacao principal do case: [case_MrHealth.md](case_MrHealth.md)

# MR. HEALTH Data Platform

Enterprise-grade data warehouse on GCP with zero infrastructure cost.

Event-driven ingestion, Medallion architecture, Star Schema, Looker Studio dashboards.

---

## Overview

Zero-cost data warehouse built on GCP Free Tier. Processes daily sales CSVs from a 50-unit restaurant chain through an automated event-driven pipeline (GCS, Cloud Function, BigQuery Bronze/Silver/Gold, Looker Studio).

| Metric | Value |
|---|---|
| Monthly Cost | $0.00 (GCP Free Tier) |
| Data Latency | < 3 minutes end-to-end |
| Test Coverage | 97.2% (22 unit tests) |
| Scalability | 10x headroom within free tier |
| Development Time | ~8h (AI-assisted) |
| Strategic Score | 90/100 |

**Problem:** 50 units send 100 CSVs/day, consolidated manually in Excel (4-6h/day, 2-5% error rate, D+1 to D+3 latency).

**Solution:** Automated event-driven pipeline. Consolidation in < 3 minutes, near-zero errors, near real-time.

---

## Architecture

```mermaid
graph TB
    subgraph Sources["DATA SOURCES"]
        POS[50 Restaurant Units - POS CSV Exports]
        REF[Reference Data - Products / Units / Geography]
    end

    subgraph Ingestion["EVENT-DRIVEN INGESTION"]
        GCS[Cloud Storage - Data Lake]
        CF[Cloud Function - csv-processor]
    end

    subgraph Warehouse["MEDALLION LAYERS - BigQuery"]
        BRONZE[(Bronze - Raw + Schema)]
        SILVER[(Silver - Cleaned + Enriched)]
        GOLD[(Gold - Star Schema + Agg)]
    end

    subgraph BI["BUSINESS INTELLIGENCE"]
        EXEC[Executive Dashboard]
        OPS[Operations Dashboard]
        MON[Pipeline Monitor]
    end

    POS -->|Daily CSV Upload| GCS
    REF -->|Static CSV| GCS
    GCS -->|GCS Event Trigger| CF
    CF -->|Schema Validation + Dedup + Load| BRONZE
    BRONZE -->|SQL Transform| SILVER
    SILVER -->|Dimensional Model| GOLD
    GOLD --> EXEC
    GOLD --> OPS
    GOLD --> MON
```

### Key Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Ingestion | Cloud Functions (2nd gen) | Event-driven, serverless, $0 |
| Warehouse | BigQuery | Serverless analytics, 1 TB/mo free |
| Transformation | BigQuery SQL (13 scripts) | Familiar syntax, no external tools |
| Orchestration | GCS Event Triggers | Zero-polling, automatic on upload |
| Visualization | Looker Studio | Native GCP, unlimited free usage |
| Modeling | Kimball Star Schema | 4 dimensions + 2 facts + 3 aggregations |

---

## Data Model

```
CSV Files (POS) --> Bronze (Raw + Schema) --> Silver (Clean + Enriched) --> Gold (Star Schema)
```

| Layer | Tables | Purpose |
|---|---|---|
| Bronze | orders, order_items, products, units, states, countries | Schema-enforced raw data with ingestion metadata |
| Silver | orders, order_items, products, units, states, countries | Cleaned, deduplicated, type-normalized, date-enriched |
| Gold | 4 dimensions + 2 facts + 3 aggregations | Star schema for analytics and dashboards |

```
                 dim_date
                    |
    dim_product --- fact_sales --- dim_unit
                    |                |
                    |           dim_geography
              fact_order_items
```

---

## Repository Structure

```
mrhealth-data-platform/
├── cloud_functions/csv_processor/   # Event-driven CSV processor (GCS -> BigQuery Bronze)
├── config/project_config.yaml       # Centralized configuration
├── docs/                            # Technical documentation + portfolio
├── scripts/                         # Infrastructure and pipeline automation
│   ├── generate_fake_sales.py       # [1] Test data generator
│   ├── deploy_phase1_infrastructure.py # [2] BigQuery datasets + tables
│   ├── upload_fake_data_to_gcs.py   # [3] Upload CSVs to GCS
│   ├── load_reference_data.py       # [4] Load reference data to Bronze
│   ├── build_silver_layer.py        # [5] Silver SQL transformations
│   ├── build_gold_layer.py          # [6] Gold star schema
│   ├── build_aggregations.py        # [7] KPI aggregation tables
│   └── verify_infrastructure.py     # [8] Validate infrastructure + data
├── sql/                             # 13 ELT scripts (bronze/ silver/ gold/)
├── tests/unit/                      # 22 pytest cases, 97.2% coverage
├── requirements.txt
└── README.md
```

---

## Getting Started

Full step-by-step guide: [docs/SETUP_GUIDE.md](docs/SETUP_GUIDE.md)

### Prerequisites

- GCP account with billing enabled (stays within free tier)
- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install)
- Python 3.11+

### Quick Setup

```bash
# 1. Clone and configure
git clone <repository-url>
cd mrhealth-data-platform
pip install -r requirements.txt

# 2. Authenticate with GCP
gcloud auth login
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID

# 3. Enable required APIs
gcloud services enable storage.googleapis.com bigquery.googleapis.com \
  cloudfunctions.googleapis.com eventarc.googleapis.com run.googleapis.com

# 4. Create infrastructure
python scripts/deploy_phase1_infrastructure.py

# 5. Generate and upload test data
python scripts/generate_fake_sales.py
python scripts/upload_fake_data_to_gcs.py
python scripts/load_reference_data.py

# 6. Deploy Cloud Function
cd cloud_functions/csv_processor
gcloud functions deploy csv-processor \
  --gen2 --runtime=python311 --region=us-central1 --source=. \
  --entry-point=process_csv \
  --trigger-event-filters="type=google.cloud.storage.object.v1.finalized" \
  --trigger-event-filters="bucket=YOUR_BUCKET_NAME" \
  --memory=256MB --timeout=300s \
  --set-env-vars="PROJECT_ID=YOUR_PROJECT_ID,BUCKET_NAME=YOUR_BUCKET_NAME,BQ_DATASET=case_ficticio_bronze"
cd ../..

# 7. Build transformation layers
python scripts/build_silver_layer.py
python scripts/build_gold_layer.py
python scripts/build_aggregations.py

# 8. Verify everything
python scripts/verify_infrastructure.py
```

Then create dashboards following [docs/LOOKER_STUDIO_SETUP.md](docs/LOOKER_STUDIO_SETUP.md).

---

## Testing

```bash
pytest tests/unit/ -v --cov=scripts --cov-report=term-missing
```

22 unit tests, 97.2% coverage. Validates schema integrity, business rules, referential consistency, and statistical distributions.

---

## Cost Analysis

| Service | Free Tier Limit | Actual Usage | Utilization |
|---|---|---|---|
| Cloud Storage | 5 GB | ~1 MB | 0.02% |
| BigQuery Storage | 10 GB | ~2 MB | 0.02% |
| BigQuery Queries | 1 TB/month | ~10 GB | 1% |
| Cloud Functions | 2M invocations/month | ~3K | 0.15% |
| Looker Studio | Unlimited | 3 dashboards | N/A |

Monthly cost: $0.00. All services use GCP's permanent Free Tier (not a trial).

Production upgrade path: ~$50-75/month with Dataproc + Datastream CDC. No architecture refactoring required.

---

## Scope

Functional MVP with running code. Production-only features (PostgreSQL CDC via Datastream, automated alerts, Dataform orchestration, CI/CD pipeline) are designed in [STRATEGIC_PLAN.md](docs/STRATEGIC_PLAN.md).

---

## Documentation

| Document | Description |
|---|---|
| [Setup Guide](docs/SETUP_GUIDE.md) | Step-by-step replication guide with all GCP commands |
| [Architecture](docs/ARCHITECTURE.md) | Technical deep-dive: layers, data models, security, DR |
| [Dashboard Guide](docs/LOOKER_STUDIO_SETUP.md) | Looker Studio dashboard creation walkthrough |
| [Strategic Plan](docs/STRATEGIC_PLAN.md) | Strategic assessment, product backlog, risk analysis |
| [Portfolio](docs/MR_HEALTH_Data_Platform_Portfolio.html) | Interactive project showcase with diagrams and details |

---

## Author

Arthur Maia Graf

[Portfolio](docs/MR_HEALTH_Data_Platform_Portfolio.html) | [GitHub](https://github.com) | [LinkedIn](https://linkedin.com)
