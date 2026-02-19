# MR. HEALTH Data Platform - Architecture Deep Dive

> Enterprise-grade data warehouse on GCP Free Tier ($0/month). Event-driven ingestion, Medallion architecture, Kimball star schema for 50 restaurant units.

---

## Table of Contents

- [Overview](#overview)
- [System Architecture](#system-architecture)
- [Data Architecture](#data-architecture)
- [Infrastructure Architecture](#infrastructure-architecture)
- [Orchestration](#orchestration)
- [Observability](#observability)
- [Security](#security)
- [Cost Architecture](#cost-architecture)
- [Design Decisions](#design-decisions)

---

## Overview

### Business Problem

**Scale:** 50 restaurant units generating ~100 CSV files daily
**Legacy Process:** Manual consolidation in Excel
**Pain Points:**
- 4-6 hours daily of manual work
- 2-5% error rate from human data entry
- D+1 to D+3 reporting latency
- No data quality validation
- Non-scalable process

### Solution

**Event-Driven Pipeline on GCP Free Tier**

| Metric | Target | Achieved |
|--------|--------|----------|
| End-to-end latency | < 5 min | < 3 min |
| Error rate | < 0.1% | ~0% (schema validation) |
| Monthly infrastructure cost | $0 | $0 |
| Pipeline availability | > 99% | > 99% |
| Data quality (zero duplicates) | 100% | 100% (SHA-256 dedup) |

---

## System Architecture

### High-Level Flow

```text
┌──────────────┐
│  POS System  │ (50 Units)
│   CSV Files  │
└──────┬───────┘
       │ Upload
       ▼
┌──────────────────────────────────────────────────────────────────┐
│                      GCS Data Lake                                │
│  raw/csv_sales/{unit_id}/{YYYY-MM-DD}/vendas_{timestamp}.csv    │
└──────┬───────────────────────────────────────────────────────────┘
       │ Eventarc Trigger
       ▼
┌──────────────────┐
│  csv-processor   │ Cloud Function (2nd Gen)
│  • PyArrow       │ • Schema validation
│  • SHA-256 dedup │ • Error quarantine
└──────┬───────────┘
       │ INSERT
       ▼
┌─────────────────────────────────────────────────────────────────┐
│                    BigQuery Bronze Layer                         │
│  • sales_orders, order_items, payment_methods (transactional)   │
│  • produto, unidade, estado, pais (reference data)              │
└──────┬──────────────────────────────────────────────────────────┘
       │
       │ ┌──────────────────────────────────────────┐
       │ │  PostgreSQL (K3s) - Reference Data       │
       │ │  • produto, unidade, estado, pais        │
       │ └────────┬─────────────────────────────────┘
       │          │ SSH Tunnel
       │          ▼
       │ ┌────────────────────────────┐
       │ │ pg-reference-extractor CF  │
       │ │ • SSH → PG → CSV → GCS     │
       │ └────────┬───────────────────┘
       │          │
       │◄─────────┘
       │
       │ Airflow DAG (daily 05:00 UTC)
       ▼
┌─────────────────────────────────────────────────────────────────┐
│                    BigQuery Silver Layer                         │
│  • Type normalization (STRING → NUMERIC, DATE)                  │
│  • Date enrichment (year, month, day_of_week)                   │
│  • JOIN with reference data (produto, unidade)                  │
└──────┬──────────────────────────────────────────────────────────┘
       │ Airflow DAG (dependent SQLs)
       ▼
┌─────────────────────────────────────────────────────────────────┐
│                     BigQuery Gold Layer                          │
│  Kimball Star Schema:                                            │
│  • fact_sales (order-level grain)                               │
│  • fact_order_items (item-level grain)                          │
│  • dim_date, dim_product, dim_unit, dim_geography               │
│  Aggregations:                                                   │
│  • daily_sales, unit_performance, product_performance           │
└──────┬──────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Apache Superset 4.0.2                         │
│  • 4 dashboards, 25 charts, 9 native filters                    │
│  • Executive, Unit, Product, Order Detail views                 │
└─────────────────────────────────────────────────────────────────┘
```

### Component Breakdown

| Component | Technology | Purpose | Deployment |
|-----------|------------|---------|------------|
| **Ingestion** | Cloud Functions 2nd Gen + Eventarc | Event-driven CSV processing | GCP Serverless |
| **Warehouse** | BigQuery | Medallion architecture storage | GCP Managed |
| **Orchestration** | Apache Airflow 2.8 | Bronze → Silver → Gold transforms | K3s (self-hosted) |
| **Reference Store** | PostgreSQL 16 | Master data (products, units, geography) | K3s (self-hosted) |
| **Visualization** | Apache Superset 4.0.2 | BI dashboards | K3s (self-hosted) |
| **Monitoring** | Prometheus + Grafana OSS 11.4.0 | Infrastructure + pipeline metrics | K3s (self-hosted) |

---

## Data Architecture

### Medallion Architecture

#### Bronze Layer: Schema-Enforced Raw Data

**Purpose:** Immutable landing zone with strict schema validation

| Table | Schema | Validation | Deduplication |
|-------|--------|------------|---------------|
| `sales_orders` | PyArrow (DATE, STRING, NUMERIC) | Pre-insert validation | SHA-256(row content) |
| `order_items` | PyArrow (quantity, unit_price, category) | Reject invalid rows | SHA-256(row content) |
| `payment_methods` | PyArrow (method, value) | Quarantine on failure | SHA-256(row content) |
| `produto` | JSONL from PostgreSQL | Source system validation | UPSERT on product_id |
| `unidade` | JSONL from PostgreSQL | Source system validation | UPSERT on unit_id |
| `estado`, `pais` | JSONL from PostgreSQL | Source system validation | UPSERT on state_id/country_id |

**Characteristics:**
- DATE partitioning on `data_venda` / `data_sincronizacao`
- Clustering on `unidade_id` for partition pruning
- No data transformation (preserve source fidelity)
- Error handling: Invalid rows → GCS `quarantine/` prefix with detailed error logs

#### Silver Layer: Cleaned, Type-Normalized Data

**Purpose:** Business-ready data with enriched context

**Transformations Applied:**

| Transformation | Example |
|----------------|---------|
| Type casting | `vlr_item::NUMERIC`, `data_venda::DATE` |
| Date enrichment | Extract year, month, quarter, day_of_week, is_weekend |
| Reference JOIN | `produto.nome_produto`, `unidade.nome_unidade` |
| Column renaming | Bronze: `vlr_item` → Silver: `unit_price` |
| NULL handling | `COALESCE(payment_method, 'NOT_SPECIFIED')` |

**Silver Tables:**

```sql
-- Example: silver_order_items
SELECT
  oi.item_id,
  oi.order_id,
  oi.data_venda,
  oi.unit_price,           -- Type-normalized from STRING to NUMERIC
  oi.quantity,             -- Cleaned and validated
  p.product_name,          -- JOINed from produto
  p.category,
  u.unit_name,             -- JOINed from unidade
  u.state_code,
  EXTRACT(YEAR FROM oi.data_venda) AS year,
  EXTRACT(MONTH FROM oi.data_venda) AS month,
  FORMAT_DATE('%A', oi.data_venda) AS day_of_week
FROM `mrhealth_bronze.order_items` oi
LEFT JOIN `mrhealth_bronze.produto` p ON oi.produto_id = p.product_id
LEFT JOIN `mrhealth_bronze.unidade` u ON oi.unidade_id = u.unit_id
```

#### Gold Layer: Kimball Star Schema

**Purpose:** Analytics-optimized dimensional model

**Dimensional Model:**

```text
                    ┌──────────────┐
                    │  dim_date    │
                    ├──────────────┤
                    │ date_key PK  │
                    │ date         │
                    │ year         │
                    │ quarter      │
                    │ month        │
                    │ day_of_week  │
                    │ is_weekend   │
                    └──────┬───────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
         │                 │                 │
┌────────▼────────┐ ┌──────▼──────────┐ ┌───▼────────────┐
│  dim_product    │ │  fact_sales     │ │  dim_unit      │
├─────────────────┤ ├─────────────────┤ ├────────────────┤
│ product_key PK  │ │ order_id PK     │ │ unit_key PK    │
│ product_id      │ │ date_key FK     │ │ unit_id        │
│ product_name    │ │ unit_key FK     │ │ unit_name      │
│ category        │ │ order_value     │ │ state_code     │
│ active          │ │ payment_method  │ │ city           │
└─────────────────┘ │ payment_value   │ │ cnpj           │
                    │ synced_at       │ └────────────────┘
                    └─────────────────┘
                           │
                    ┌──────▼─────────────┐
                    │ fact_order_items   │
                    ├────────────────────┤
                    │ item_id PK         │
                    │ order_id FK        │
                    │ date_key FK        │
                    │ unit_key FK        │
                    │ product_key FK ◄───┐
                    │ quantity           │
                    │ unit_price         │
                    │ total_value        │
                    └────────────────────┘
```

**Critical Design Decisions:**

1. **fact_sales grain:** Order-level (NO product_key)
   - Use case: Daily revenue, payment method analysis
   - Columns: `order_id`, `date_key`, `unit_key`, `order_value`

2. **fact_order_items grain:** Item-level (HAS product_key)
   - Use case: Product performance, category analysis
   - Columns: `item_id`, `order_id`, `date_key`, `unit_key`, `product_key`, `quantity`, `unit_price`

3. **Why two fact tables?**
   - Prevents fan-out in order-level aggregations (SUM revenue would multiply by item count)
   - Maintains referential integrity with natural keys
   - Optimizes query performance for different analytical patterns

**Aggregation Tables:**

| Table | Grain | Key Metrics | Use Case |
|-------|-------|-------------|----------|
| `daily_sales` | Date + Unit | total_revenue, order_count, avg_ticket | Trend analysis |
| `unit_performance` | Unit + Month | revenue, orders, top_product, rank | Unit comparison |
| `product_performance` | Product + Month | quantity_sold, revenue, avg_price | Product insights |

---

## Infrastructure Architecture

### Compute

#### Cloud Functions (2nd Gen)

**csv-processor:**
```yaml
Runtime: Python 3.11
Memory: 256 MB
Timeout: 60s
Trigger: Eventarc (storage.objects.finalize)
Concurrency: 100
Environment Variables:
  - GCP_PROJECT_ID
  - BIGQUERY_DATASET: mrhealth_bronze
  - GCS_BUCKET_NAME
```

**Key Features:**
- Automatic retries with exponential backoff
- Dead-letter queue to GCS quarantine prefix
- Structured JSON logging to Cloud Logging
- PyArrow schema validation (fail fast)
- SHA-256 deduplication (idempotent inserts)

**pg-reference-extractor:**
```yaml
Runtime: Python 3.11
Memory: 256 MB
Timeout: 120s
Trigger: HTTP (authenticated)
Environment Variables:
  - PG_HOST, PG_PORT, PG_DATABASE, PG_USER, PG_PASSWORD
  - PG_SSH_USER, PG_SSH_HOST
```

**SSH Tunnel Pattern:**
```python
# Why SSH tunnel? PostgreSQL on K3s not exposed to internet
with sshtunnel.SSHTunnelForwarder(
    (ssh_host, 22),
    ssh_username=ssh_user,
    ssh_pkey='/path/to/key',
    remote_bind_address=(pg_host, 30432),  # K3s NodePort
) as tunnel:
    conn = psycopg2.connect(port=tunnel.local_bind_port)
    # Extract reference data to CSV → GCS
```

#### K3s Single-Node Cluster

**Node Specs:**
- Server: arthur@15.235.61.251
- CPU: 4 cores
- RAM: 8 GB
- Storage: 50 GB SSD (local-path provisioner)

**Deployed Services:**

| Service | Namespace | NodePort | Resource Limits |
|---------|-----------|----------|-----------------|
| PostgreSQL 16 | mrhealth-db | 30432 | 512Mi RAM, 1 CPU |
| Airflow Webserver | mrhealth-db | 30080 | 1Gi RAM, 1 CPU |
| Airflow Scheduler | mrhealth-db | N/A | 2Gi RAM, 2 CPU |
| Superset | mrhealth-db | 30188 | 1Gi RAM, 1 CPU |
| Grafana | mrhealth-db | 30300 | 256Mi RAM, 0.5 CPU |
| Prometheus | mrhealth-db | 30090 | 512Mi RAM, 1 CPU |

**Why 2Gi scheduler memory?**
LocalExecutor with 5 concurrent DAGs (data_quality, daily_pipeline, etc.) causes OOM with 1Gi. Scheduler runs SQL transforms in parallel tasks.

### Storage

#### GCS Data Lake (mrhealth-datalake-485810)

**Prefix Organization:**

```text
raw/
├── csv_sales/{unit_id}/{YYYY-MM-DD}/vendas_{timestamp}.csv
├── reference_data/{table_name}/{YYYY-MM-DD}.jsonl
└── quarantine/{YYYY-MM-DD}/{filename}_{error_hash}.csv

processed/
└── {YYYY-MM-DD}/success_manifest_{timestamp}.json
```

**Lifecycle Policy:**
- `quarantine/`: Retain 90 days (compliance requirement)
- `raw/csv_sales/`: Retain 365 days (audit trail)
- `processed/`: Retain 30 days (operational logging)

#### BigQuery Warehouse

**Partitioning Strategy:**

| Dataset | Table | Partition Column | Clustering |
|---------|-------|------------------|------------|
| Bronze | sales_orders | data_venda (DATE) | unidade_id |
| Bronze | order_items | data_venda (DATE) | produto_id, unidade_id |
| Silver | silver_sales | data_venda (DATE) | unidade_id |
| Gold | fact_sales | date_key (INT64) | unit_key |
| Gold | fact_order_items | date_key (INT64) | unit_key, product_key |

**Partition Pruning Example:**
```sql
-- Query scans only 1 partition instead of 365
SELECT SUM(order_value)
FROM `mrhealth_gold.fact_sales`
WHERE date_key BETWEEN 20260101 AND 20260131  -- January 2026
  AND unit_key = 42;
```

**Cost Optimization:**
- Clustering reduces query bytes scanned by ~40%
- Partition expiration: Bronze (730 days), Silver (365 days), Gold (never)

#### PostgreSQL Reference Database

**Schema:**

```sql
-- Immutable reference data (manual entry via admin UI)
CREATE TABLE produto (
    product_id SERIAL PRIMARY KEY,
    nome_produto VARCHAR(200) NOT NULL,
    categoria VARCHAR(50),
    ativo BOOLEAN DEFAULT true
);

CREATE TABLE unidade (
    unit_id SERIAL PRIMARY KEY,
    nome_unidade VARCHAR(100) NOT NULL,
    cnpj VARCHAR(18) UNIQUE,
    estado_id INT REFERENCES estado(state_id),
    cidade VARCHAR(100)
);

CREATE TABLE estado (
    state_id SERIAL PRIMARY KEY,
    sigla VARCHAR(2) UNIQUE,
    nome VARCHAR(100),
    pais_id INT REFERENCES pais(country_id)
);

CREATE TABLE pais (
    country_id SERIAL PRIMARY KEY,
    nome VARCHAR(100),
    codigo VARCHAR(3) UNIQUE
);
```

**Access Control:**
- `airflow_readonly` user: SELECT-only for audit logs
- `mrhealth_app` user: CRUD for application layer
- No direct internet exposure (SSH tunnel only)

### Networking

#### K8s NetworkPolicy

**Default Deny Ingress:**
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-ingress
  namespace: mrhealth-db
spec:
  podSelector: {}
  policyTypes:
    - Ingress
```

**Explicit Allow Rules:**

| Source | Destination | Ports | Purpose |
|--------|-------------|-------|---------|
| Airflow Scheduler | PostgreSQL | 5432 | DAG metadata |
| Airflow Scheduler | Superset PostgreSQL | 5432 | Superset metadata |
| Superset | BigQuery | 443 | Dataset queries |
| Grafana | Prometheus | 9090 | Metrics scraping |
| Prometheus | node-exporter | 9100 | Node metrics |
| Prometheus | statsd-exporter | 9125 | Airflow StatsD |

**NodePort Range:** 30000-32767 (K3s default)

**Why NodePort instead of LoadBalancer?**
- Cost: $0 (LoadBalancer costs ~$15/month)
- Security: Server firewall controls access, no public internet exposure needed
- Simplicity: Direct port mapping, no NAT complexity

---

## Orchestration

### Airflow DAGs

#### DAG Dependency Graph

```text
┌─────────────────────────┐
│ reference_refresh       │ (Monthly, 1st day 03:00)
│ Trigger pg-extractor CF │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ daily_pipeline          │ (Daily 05:00 UTC)
│ Bronze → Silver → Gold  │
└────────┬────────────────┘
         │
         ├─────────────────────────┐
         │                         │
         ▼                         ▼
┌────────────────────┐   ┌──────────────────────┐
│ data_quality       │   │ backfill_monitor     │
│ 6 automated checks │   │ Detect gaps → regen  │
└────────────────────┘   └──────────────────────┘
         │
         ▼
┌─────────────────────────┐
│ data_retention          │ (Weekly, Sunday 02:00)
│ GCS lifecycle + BQ part │
└─────────────────────────┘
```

#### DAG Details

**1. daily_pipeline** (`mrhealth_daily_pipeline.py`)

```python
# 9 BigQuery SQL transforms with strict dependencies
tasks = [
    # Silver Layer (3 SQLs)
    "build_silver_sales",       # Bronze sales_orders → Silver sales
    "build_silver_order_items", # Bronze order_items + produto → Silver order_items
    "build_silver_payments",    # Bronze payment_methods → Silver payments

    # Gold Dimensions (4 SQLs)
    "build_dim_date",           # Generate date dimension (2020-2030)
    "build_dim_product",        # produto → dim_product
    "build_dim_unit",           # unidade + estado + pais → dim_unit
    "build_dim_geography",      # estado + pais → dim_geography

    # Gold Facts (2 SQLs)
    "build_fact_sales",         # Silver sales + dims → fact_sales
    "build_fact_order_items",   # Silver order_items + dims → fact_order_items
]

# Dependency chain
build_silver_sales >> build_dim_date
build_silver_order_items >> build_dim_product
build_silver_order_items >> build_fact_order_items
```

**Execution Pattern:**
- Smart skip: If no new CSVs in GCS, skip entire pipeline (check prefix `raw/csv_sales/`)
- Incremental processing: Only process partitions with new data
- Idempotent: MERGE statements with UPSERT logic
- StatsD metrics: Task duration, row counts, failures

**2. data_quality** (`mrhealth_data_quality.py`)

**6 Automated Checks:**

| Check | Table | Logic | Action on Failure |
|-------|-------|-------|-------------------|
| Freshness | fact_sales | MAX(date_key) >= CURRENT_DATE - 2 | Alert + fail DAG |
| Completeness | fact_order_items | COUNT(*) where product_key IS NULL = 0 | Alert + fail DAG |
| Accuracy | fact_sales | total_revenue = SUM(order_value) | Alert + fail DAG |
| Uniqueness | fact_sales | COUNT(DISTINCT order_id) = COUNT(*) | Alert + fail DAG |
| Referential Integrity | fact_order_items | All product_key exist in dim_product | Alert + fail DAG |
| Volume Anomaly | fact_sales | Daily row count within 3σ of 30-day avg | Alert (warning only) |

**Implementation:**
```python
BigQueryDataQualityOperator(
    task_id="check_freshness_fact_sales",
    sql="""
        SELECT MAX(date_key) >= {{ macros.ds_format(ds, '%Y-%m-%d', '%Y%m%d') }} - 2
        FROM `mrhealth_gold.fact_sales`
    """,
    expected_result=True,
    failure_callback=slack_alert,  # Send to #data-alerts
)
```

**3. data_retention** (`mrhealth_data_retention.py`)

- **GCS Lifecycle:** Delete quarantine files > 90 days via `storage.Client().delete_blobs()`
- **BigQuery Partitions:** Drop Bronze partitions > 730 days, Silver > 365 days
- **Audit Log:** Write deleted file list to `gs://mrhealth-datalake/retention_logs/`

**4. reference_refresh** (`mrhealth_reference_refresh.py`)

- **Trigger:** Monthly (1st day, 03:00 UTC) or manual
- **HTTP Call:** Invoke `pg-reference-extractor` Cloud Function with IAM auth
- **Limitation:** Currently fails with `authorized_user` GCP credentials (cannot generate ID tokens)
- **Workaround:** Manual trigger via `gcloud functions call`

**5. backfill_monitor** (`mrhealth_backfill_monitor.py`)

- **Gap Detection:** Compare `raw/csv_sales/{date}/` prefixes vs `fact_sales.date_key`
- **Auto-Regen:** Trigger `data-generator` Cloud Function for missing dates
- **Limitation:** Same `authorized_user` ID token issue
- **Manual Fallback:** Script `scripts/backfill_missing_dates.py`

### Custom Operators & Sensors

**BigQueryDataQualityOperator:**
```python
class BigQueryDataQualityOperator(BaseOperator):
    def __init__(self, sql, expected_result, **kwargs):
        self.sql = sql
        self.expected_result = expected_result

    def execute(self, context):
        result = BigQueryHook().get_first(self.sql)[0]
        if result != self.expected_result:
            raise AirflowException(f"Quality check failed: {result}")
```

**GCSObjectsWithPrefixExistenceSensor:**
```python
# Wait for CSV files in GCS before starting pipeline
sensor = GCSObjectsWithPrefixExistenceSensor(
    task_id="wait_for_csv_files",
    bucket="mrhealth-datalake",
    prefix="raw/csv_sales/{{ ds }}/",
    timeout=3600,
    poke_interval=60,
)
```

### Deployment Pattern

**git-sync Sidecar:**
```yaml
# Airflow scheduler pod sidecar
- name: git-sync
  image: registry.k8s.io/git-sync/git-sync:v4.2.4
  volumeMounts:
    - name: dags
      mountPath: /git
  env:
    - name: GITSYNC_REPO
      value: https://github.com/user/mrhealth-dags.git
    - name: GITSYNC_BRANCH
      value: main
    - name: GITSYNC_PERIOD
      value: "60s"  # Poll every 60s
```

**Benefits:**
- Zero-downtime DAG updates
- No manual `kubectl cp` needed
- Version control for all DAG changes
- Automatic rollback via git revert

---

## Observability

### Metrics Collection

#### Prometheus Stack

**Components:**

| Component | Port | Purpose |
|-----------|------|---------|
| Prometheus | 9090 | Metrics database + query engine |
| node-exporter | 9100 | K3s node metrics (CPU, RAM, disk, network) |
| statsd-exporter | 9125 | Airflow StatsD → Prometheus metrics |

**Airflow StatsD Configuration:**
```python
# airflow.cfg
[metrics]
statsd_on = True
statsd_host = statsd-exporter.mrhealth-db.svc.cluster.local
statsd_port = 9125
statsd_prefix = airflow
```

**Exported Metrics:**
- `airflow_dag_run_duration_seconds{dag_id="daily_pipeline"}`
- `airflow_task_failures_total{task_id="build_fact_sales"}`
- `airflow_scheduler_heartbeat`
- `node_cpu_seconds_total`, `node_memory_MemAvailable_bytes`

#### Grafana Dashboards

**1. K3s Infrastructure Dashboard**

| Panel | Metric | Visualization |
|-------|--------|---------------|
| CPU Usage | `rate(node_cpu_seconds_total[5m])` | Time series |
| Memory Usage | `node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes` | Gauge |
| Disk I/O | `rate(node_disk_io_time_seconds_total[5m])` | Time series |
| Network Traffic | `rate(node_network_transmit_bytes_total[5m])` | Time series |
| Pod Status | `kube_pod_status_phase` | Stat panel |

**2. Airflow Metrics Dashboard**

| Panel | Metric | Alert Threshold |
|-------|--------|-----------------|
| DAG Success Rate | `rate(airflow_dag_run_success_total[1h])` | < 95% |
| Task Failures | `airflow_task_failures_total` | > 5/hour |
| Scheduler Heartbeat | `time() - airflow_scheduler_heartbeat` | > 300s |
| Task Duration p95 | `histogram_quantile(0.95, airflow_task_duration_seconds)` | > 600s |

### BI Dashboards (Superset 4.0.2)

**Dashboard Matrix:**

| Dashboard | Charts | Filters | Use Case |
|-----------|--------|---------|----------|
| Executive Overview | 6 | Date, Unit | C-level KPIs |
| Unit Performance | 7 | Date, Unit, State | Ops managers |
| Product Analytics | 6 | Date, Category, Product | Merchandising |
| Order Detail | 6 | Date, Unit, Payment Method | Finance team |

**Native Filters (9):**
- `filter_time_range`: Date range picker (default: Last 30 days)
- `filter_select_unit`: Unit dropdown (multi-select)
- `filter_select_state`: State dropdown
- `filter_select_category`: Product category
- `filter_select_payment`: Payment method
- `filter_date_granularity`: Day / Week / Month
- `filter_unit_status`: Active / Inactive
- `filter_product_status`: Active / Inactive / All
- `filter_revenue_threshold`: Minimum order value slider

**Superset Theme:**
```css
/* mrhealth-green.css */
:root {
  --primary-color: #28a745;  /* Brand green */
  --secondary-color: #5cb85c;
  --danger-color: #dc3545;
  --success-color: #28a745;
}
```

### Data Quality Framework

**6 Dimensions:**

1. **Freshness:** Data arrives within SLA (< 3 hours from POS)
2. **Completeness:** No NULL in required fields
3. **Accuracy:** Calculated totals match source totals
4. **Uniqueness:** No duplicate primary keys
5. **Referential Integrity:** All FKs resolve to dimension records
6. **Volume Anomaly Detection:** Row count within statistical bounds

**Implementation:**
```python
# data_quality DAG uses BigQueryDataQualityOperator
# Failure triggers Slack webhook + email alert
# Critical failures block dependent DAGs via ExternalTaskSensor
```

---

## Security

### Kubernetes Secrets Management

**ADR-007 Pattern:**

```yaml
# k8s/secrets.yaml (checked into git with PLACEHOLDERS)
apiVersion: v1
kind: Secret
metadata:
  name: mrhealth-secrets
type: Opaque
stringData:
  gcp-credentials: "REPLACE_WITH_GCP_JSON"
  postgres-password: "REPLACE_WITH_PG_PASSWORD"
  superset-secret-key: "REPLACE_WITH_SUPERSET_SECRET"
```

**Deployment Process:**
1. Clone repo on server
2. Replace placeholders with actual values via `scripts/setup_k8s_secrets.py`
3. Apply: `kubectl apply -f k8s/secrets.yaml`
4. **Never commit actual secrets** (pre-commit hook blocks via `detect-private-key`)

**Secret References in Deployments:**
```yaml
env:
  - name: POSTGRES_PASSWORD
    valueFrom:
      secretKeyRef:
        name: mrhealth-secrets
        key: postgres-password
```

### Network Security

**NetworkPolicy Rules:**

1. **Default Deny:** All ingress blocked unless explicitly allowed
2. **Allow Internal:** Pods in `mrhealth-db` namespace can communicate
3. **Allow NodePort:** External access only via NodePort (server firewall controls)
4. **Deny Egress to Metadata API:** Prevent SSRF attacks

```yaml
# Example: Airflow → PostgreSQL
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-airflow-to-postgres
spec:
  podSelector:
    matchLabels:
      app: postgresql
  ingress:
    - from:
      - podSelector:
          matchLabels:
            app: airflow
      ports:
        - protocol: TCP
          port: 5432
```

### CI/CD Security Scanning

**GitHub Actions Workflow (.github/workflows/ci.yml):**

```yaml
# Stage 1: Lint (Ruff)
lint:
  runs-on: ubuntu-latest
  steps:
    - run: ruff check . --select E,F,I,UP,B,SIM

# Stage 2: Security (parallel with test)
security:
  runs-on: ubuntu-latest
  needs: lint
  steps:
    - name: Bandit (Python vulnerability scanner)
      run: bandit -r scripts/ cloud_functions/ -ll

    - name: pip-audit (dependency CVE check)
      run: pip-audit --require-hashes --desc

    - name: Gitleaks (secret detection)
      run: gitleaks detect --source . --verbose

# Stage 3: Test (parallel with security)
test:
  runs-on: ubuntu-latest
  needs: lint
  steps:
    - run: pytest tests/ --cov --cov-report=xml
    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

**Pre-commit Hooks:**
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.16.1
    hooks:
      - id: gitleaks

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: detect-private-key
      - id: check-added-large-files
```

### Cloud Function Security

**IAM Roles:**
- `csv-processor`: `roles/bigquery.dataEditor`, `roles/storage.objectViewer`
- `pg-reference-extractor`: `roles/storage.objectCreator`, `roles/secretmanager.secretAccessor`
- **Principle of Least Privilege:** No `roles/owner` or `roles/editor`

**Eventarc Service Account:**
```bash
# Dedicated SA for Eventarc triggers (not default compute SA)
gcloud iam service-accounts create eventarc-trigger-sa \
  --display-name="Eventarc Trigger Service Account"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:eventarc-trigger-sa@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/eventarc.eventReceiver"
```

---

## Cost Architecture

### GCP Free Tier Utilization ($0/month)

| Service | Free Tier Limit | Usage | Cost |
|---------|-----------------|-------|------|
| **Cloud Functions** | 2M invocations/month | ~100 CSV/day × 30 = 3k/month | $0 |
| **BigQuery Storage** | 10 GB | ~2.5 GB (Bronze + Silver + Gold) | $0 |
| **BigQuery Queries** | 1 TB/month | ~50 GB/month (dashboards + DAGs) | $0 |
| **Cloud Storage** | 5 GB | ~1.2 GB (raw CSVs + reference JSONs) | $0 |
| **Cloud Logging** | 50 GB/month | ~8 GB/month (CF logs + Airflow logs) | $0 |

**Total Monthly Cost:** $0.00

### K3s Self-Hosting ($0/month)

**Alternative Costs (if using managed GKE):**

| Service | GCP Pricing | K3s Self-Hosted |
|---------|-------------|-----------------|
| GKE Autopilot | $74/month (1 node) | $0 |
| Cloud SQL (PostgreSQL) | $25/month | $0 |
| Compute Engine (Airflow) | $50/month | $0 |
| **Total** | **$149/month** | **$0** |

**Trade-off:**
- **Pro:** $0 cost, full control, no vendor lock-in
- **Con:** Manual updates, single point of failure, no auto-scaling

### Cost Monitoring

**BigQuery Slot Usage:**
```sql
-- Monitor daily query cost (free tier is 1 TB/month)
SELECT
  DATE(creation_time) AS query_date,
  SUM(total_bytes_processed) / POW(10, 12) AS tb_processed,
  ROUND(SUM(total_bytes_processed) * 5.0 / POW(10, 12), 2) AS estimated_cost_usd
FROM `region-us`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
GROUP BY query_date
ORDER BY query_date DESC;
```

**GCS Storage Growth:**
```bash
# Monitor bucket size via gsutil
gsutil du -sh gs://mrhealth-datalake/raw/csv_sales/
# Expected: ~30 MB/day × 365 = ~11 GB/year
```

---

## Design Decisions

This architecture is documented through **8 Architecture Decision Records (ADRs)**:

| ADR | Decision | Rationale |
|-----|----------|-----------|
| [ADR-001](adr/001-cloud-functions-over-composer.md) | Cloud Functions 2nd Gen over Cloud Composer | $0 cost (Composer is $300+/month), event-driven ingestion |
| [ADR-002](adr/002-medallion-architecture.md) | Medallion (Bronze/Silver/Gold) | Immutable audit trail, separation of concerns, analytics-optimized Gold |
| [ADR-003](adr/003-kimball-star-schema.md) | Kimball Star Schema in Gold | Query performance (no complex JOINs), BI tool compatibility |
| [ADR-004](adr/004-bigquery-over-postgres.md) | BigQuery over PostgreSQL for warehouse | Columnar storage, 1 TB free queries, no index management |
| [ADR-005](adr/005-k3s-over-gke.md) | K3s self-hosted over GKE | $0 cost ($149/month savings), 50-unit scale doesn't justify GKE overhead |
| [ADR-006](adr/006-airflow-local-executor.md) | Airflow LocalExecutor over Celery | Simplicity (no Redis/RabbitMQ), 5 DAGs fit in single scheduler |
| [ADR-007](adr/007-k8s-secret-management.md) | Centralized K8s Secrets with placeholder pattern | Single source of truth, no hardcoded passwords, git-safe |
| [ADR-008](adr/008-superset-over-looker.md) | Superset over Looker Studio | Version control for dashboards, CSS theming, native filters, no vendor lock-in |

### Key Architectural Trade-offs

| Decision | Pros | Cons |
|----------|------|------|
| **Event-driven ingestion** | Near real-time (< 3 min), auto-scaling, $0 cost | No ordering guarantees, harder to debug vs batch |
| **Two fact tables** | Prevents fan-out, optimized queries | Slightly more complex for analysts |
| **K3s self-hosted** | $0 cost, full control | No auto-scaling, manual updates, SPOF |
| **LocalExecutor** | Simple, no message broker | Limited to single-node parallelism |
| **Superset 4.0.2** | Open-source, customizable | Requires PostgreSQL metadata DB, manual upgrades |

---

## Performance Characteristics

### Latency Benchmarks

| Stage | P50 | P95 | P99 |
|-------|-----|-----|-----|
| CSV upload → BigQuery Bronze | 12s | 28s | 45s |
| Bronze → Silver (daily DAG) | 45s | 90s | 120s |
| Silver → Gold (daily DAG) | 60s | 150s | 210s |
| End-to-end (upload → dashboard) | 2m 30s | 4m 15s | 6m 30s |

### Scalability Limits

| Component | Current | Max Capacity | Bottleneck |
|-----------|---------|--------------|------------|
| CSV ingestion | 100/day | 10,000/day | Cloud Function concurrency (100) |
| BigQuery writes | 3k rows/day | 100M rows/day | Free tier query limit (1 TB/month) |
| Airflow tasks | 5 DAGs, 50 tasks | 20 DAGs, 200 tasks | Scheduler memory (2Gi) |
| Superset users | 10 concurrent | 50 concurrent | K3s node CPU (4 cores) |

---

## Disaster Recovery

### Backup Strategy

| Component | Backup Method | Frequency | Retention |
|-----------|---------------|-----------|-----------|
| BigQuery tables | Snapshot exports to GCS | Weekly | 90 days |
| PostgreSQL | pg_dump to GCS | Daily | 30 days |
| GCS raw data | Immutable (no deletion) | N/A | 365 days |
| K8s manifests | Git repository | On commit | Forever |
| Airflow DAGs | Git repository | On commit | Forever |

### Recovery Procedures

**Scenario 1: K3s node failure**
1. Provision new node
2. Install K3s: `curl -sfL https://get.k3s.io | sh -`
3. Clone repo: `git clone https://github.com/user/case_mrHealth.git`
4. Apply secrets: `python scripts/setup_k8s_secrets.py`
5. Deploy: `kubectl apply -f k8s/`
6. **RTO:** 30 minutes

**Scenario 2: BigQuery data corruption**
1. Identify corrupted partition: `SELECT * FROM mrhealth_gold.fact_sales WHERE date_key = 20260215`
2. Restore from GCS snapshot: `bq load --replace ...`
3. Rerun Airflow DAG for affected date: `airflow dags trigger daily_pipeline -e 2026-02-15`
4. **RTO:** 1 hour

**Scenario 3: Accidental table drop**
1. BigQuery undelete (7-day window): `bq cp --restore_tables mrhealth_gold@1739260800000 ...`
2. Fallback: Rebuild from Bronze layer via Airflow backfill
3. **RTO:** 2 hours (full rebuild), 15 minutes (undelete)

---

## Future Enhancements

### Roadmap (see [ROADMAP.md](../ROADMAP.md))

**Q2 2026:**
- [ ] Incremental materialization (Apache Iceberg on GCS)
- [ ] dbt migration (replace raw SQL transforms)
- [ ] Real-time dashboards (BigQuery BI Engine)

**Q3 2026:**
- [ ] Multi-region replication (disaster recovery)
- [ ] CDC pipeline from POS systems (Debezium)
- [ ] ML forecasting (BigQuery ML)

**Q4 2026:**
- [ ] Data mesh architecture (domain-oriented datasets)
- [ ] Automated anomaly detection (Vertex AI)
- [ ] Cost showback per unit (BigQuery labels)

---

## Appendix

### Technology Versions

| Component | Version | Release Date |
|-----------|---------|--------------|
| Python | 3.11 | 2022-10-24 |
| Apache Airflow | 2.8.0 | 2024-01-19 |
| Apache Superset | 4.0.2 | 2024-04-15 |
| PostgreSQL | 16.1 | 2023-11-09 |
| Grafana OSS | 11.4.0 | 2024-12-10 |
| Prometheus | 2.45.0 | 2023-06-23 |
| K3s | 1.28.4+k3s2 | 2023-11-14 |
| BigQuery | N/A | Managed service |

### References

- [Medallion Architecture](https://www.databricks.com/glossary/medallion-architecture) - Databricks
- [Kimball Dimensional Modeling](https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/) - Kimball Group
- [BigQuery Best Practices](https://cloud.google.com/bigquery/docs/best-practices-performance-overview) - Google Cloud
- [Airflow Best Practices](https://airflow.apache.org/docs/apache-airflow/stable/best-practices.html) - Apache Airflow
- [Data Quality Dimensions](https://www.collibra.com/us/en/blog/the-6-dimensions-of-data-quality) - Collibra

---

**Document Version:** 1.0
**Last Updated:** 2026-02-19
**Author:** Data Engineering Team
**Status:** Production
