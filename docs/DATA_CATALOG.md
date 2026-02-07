# MR. HEALTH - Data Catalog

> Complete catalog of all data assets with lineage, schemas, and SLAs.
> Last updated: 2026-02-07

---

## Data Lineage

```
POS Systems (50 units)
    |
    v  (CSV upload: pedido.csv, item_pedido.csv)
GCS Bucket  (gs://mrhealth-datalake-*/raw/csv_sales/)
    |
    v  [Cloud Function: csv-processor (Eventarc trigger)]
BigQuery Bronze  (mrhealth_bronze: orders, order_items)
    |
    v  [Airflow DAG: mrhealth_daily_pipeline (SQL transforms)]
BigQuery Silver  (mrhealth_silver: orders, order_items, products, units, states, countries)
    |
    v  [Airflow DAG: mrhealth_daily_pipeline (SQL transforms)]
BigQuery Gold  (mrhealth_gold: dim_*, fact_*, agg_*)
    |
    v
Apache Superset  (4 dashboards)

PostgreSQL (K3s)  ---[Cloud Function: pg-reference-extractor]--->  GCS (raw/reference_data/)
                                                                      |
                                                                      v [csv-processor]
                                                              BigQuery Bronze (products, units, states, countries)
```

---

## Bronze Layer (`mrhealth_bronze`)

Schema-enforced raw data with ingestion metadata. Partitioned by `_ingest_date`.

| Table | Source | Grain | Columns | Refresh |
|-------|--------|-------|---------|---------|
| `orders` | GCS CSV (pedido.csv) | 1 row per order | id_unidade, id_pedido, tipo_pedido, data_pedido, vlr_pedido, endereco_entrega, taxa_entrega, status, _source_file, _ingest_timestamp, _ingest_date | Event-driven (<3 min) |
| `order_items` | GCS CSV (item_pedido.csv) | 1 row per line item | id_pedido, id_item_pedido, id_produto, qtd, vlr_item, observacao, _source_file, _ingest_timestamp, _ingest_date | Event-driven (<3 min) |
| `products` | PostgreSQL (produto) | 1 row per product | id_produto, nome_produto, _ingest_timestamp | Daily (01:00 UTC) |
| `units` | PostgreSQL (unidade) | 1 row per unit | id_unidade, nome_unidade, id_estado, _ingest_timestamp | Daily (01:00 UTC) |
| `states` | PostgreSQL (estado) | 1 row per state | id_estado, id_pais, nome_estado, _ingest_timestamp | Daily (01:00 UTC) |
| `countries` | PostgreSQL (pais) | 1 row per country | id_pais, nome_pais, _ingest_timestamp | Daily (01:00 UTC) |

---

## Silver Layer (`mrhealth_silver`)

Cleaned, deduplicated, type-normalized, date-enriched data.

| Table | Source | Key Transformations |
|-------|--------|---------------------|
| `orders` | bronze.orders | Dedup by id_pedido, type casting, date enrichment (year/month/day_of_week), status normalization |
| `order_items` | bronze.order_items | Dedup by id_item_pedido, calculated total (unit_price * quantity), join with orders for date |
| `products` | bronze.products | Trim whitespace, English column names (product_name) |
| `units` | bronze.units | English column names (unit_name), join with states for state_name |
| `states` | bronze.states | English column names (state_name), join with countries |
| `countries` | bronze.countries | English column names (country_name) |

---

## Gold Layer (`mrhealth_gold`)

Kimball Star Schema optimized for analytics.

### Dimensions

| Table | Grain | Key | Columns |
|-------|-------|-----|---------|
| `dim_date` | 1 row per day (2025-2027) | date_key (YYYYMMDD) | full_date, year, month, day, day_of_week, day_name, month_name, quarter, is_weekend |
| `dim_product` | 1 row per product | product_key (hash) | product_name, effective_from, effective_to, is_current (SCD2 scaffolding) |
| `dim_unit` | 1 row per unit | unit_key (hash) | unit_name, state_name, country_name |
| `dim_geography` | 1 row per state | geography_key (hash) | state_name, country_name |

### Facts

| Table | Grain | Key Measures |
|-------|-------|-------------|
| `fact_sales` | 1 row per order | order_id, date_key, unit_key, order_value, delivery_fee, total_items, order_type, status |
| `fact_order_items` | 1 row per line item | item_id, order_id, date_key, unit_key, product_key, quantity, unit_price, total_item_value |

### Aggregations

| Table | Grain | Key Measures |
|-------|-------|-------------|
| `agg_daily_sales` | 1 row per date | total_orders, total_revenue, avg_order_value, total_items |
| `agg_unit_performance` | 1 row per unit per date | total_orders, total_revenue, online_pct, cancellation_rate |
| `agg_product_performance` | 1 row per product per date | total_quantity, total_revenue, avg_price, unit_count |

---

## Monitoring (`mrhealth_monitoring`)

| Table | Purpose | Grain |
|-------|---------|-------|
| `data_quality_log` | Results from 6 automated quality checks | 1 row per check per DAG run |
| `pipeline_metrics` | SLA miss, task failure, quality failure events | 1 row per metric event |
| `free_tier_usage` | GCP Free Tier consumption tracking | 1 row per check |

---

## Data Quality Checks

| Check | Target Table | Pass Condition | Frequency |
|-------|-------------|----------------|-----------|
| Freshness | fact_sales | Data from today exists | Every DAG run |
| Completeness | fact_sales | All 50 units reported | Every DAG run |
| Accuracy | fact_sales vs silver.orders | Revenue totals match within 1% | Every DAG run |
| Uniqueness | fact_sales | 0 duplicate order_ids | Every DAG run |
| Referential Integrity | fact_order_items | 0 orphan product_keys | Every DAG run |
| Volume Anomaly | agg_daily_sales | z-score < 3.0 | Every DAG run |

---

## Data Owners

| Domain | Owner | Contact |
|--------|-------|---------|
| Sales Pipeline | Data Engineering | data-team@mrhealth.com |
| Reference Data | Operations | ops@mrhealth.com |
| Dashboards | Analytics | analytics@mrhealth.com |
| Infrastructure | Platform | platform@mrhealth.com |

---

## Glossary

| Term | Definition |
|------|-----------|
| POS | Point of Sale system in each restaurant unit |
| Medallion | Bronze (raw) -> Silver (clean) -> Gold (business) architecture |
| Star Schema | Dimensional model with fact tables at center, dimensions as points |
| SCD Type 2 | Slowly Changing Dimension that preserves history with effective_from/to |
| Quarantine | GCS prefix (`quarantine/`) for files that failed validation |
| Eventarc | GCP service that triggers Cloud Functions on GCS object creation |
