# MR. HEALTH - Data Catalog

> Complete catalog of all data assets. Includes table descriptions, lineage, owners, and SLAs.
> Last updated: 2026-02-07

---

## Data Lineage Overview

```
POS Systems (50 units)
    |
    v
GCS Bucket (raw CSVs)
    |
    v [Cloud Function: csv-processor]
BigQuery Bronze (raw_sales, raw_products, ...)
    |
    v [Airflow DAG: bronze_to_silver]
BigQuery Silver (clean_sales, clean_products, ...)
    |
    v [Airflow DAG: silver_to_gold]
BigQuery Gold (dim_*, fact_*, agg_*)
    |
    v
Superset / Looker Studio (Dashboards)
```

---

## Bronze Layer (mrhealth_bronze)

Raw data as received. No transformations applied.

| Table | Source | Grain | Refresh | SLA |
|-------|--------|-------|---------|-----|
| raw_sales | GCS CSV upload | 1 row per CSV row | Event-driven | <3 min |
| raw_products | PostgreSQL | 1 row per product | Daily | <5 min |
| raw_stores | PostgreSQL | 1 row per store | Daily | <5 min |
| raw_customers | PostgreSQL | 1 row per customer | Daily | <5 min |
| quarantine | csv-processor | 1 row per invalid record | Event-driven | N/A |

---

## Silver Layer (mrhealth_silver)

Cleaned, deduplicated, validated data.

| Table | Source | Transformations |
|-------|--------|-----------------|
| clean_sales | raw_sales | Dedup by content_hash, null handling, type casting, date normalization |
| clean_products | raw_products | Trim whitespace, standardize names, remove test data |
| clean_stores | raw_stores | Geocoding validation, status normalization |
| clean_customers | raw_customers | Email normalization, duplicate merge |

---

## Gold Layer (mrhealth_gold)

### Dimensions

| Table | Grain | SCD Type | Key |
|-------|-------|----------|-----|
| dim_customer | 1 row per customer | Type 1 | customer_sk |
| dim_store | 1 row per store | Type 1 | store_sk |
| dim_product | 1 row per product version | Type 2 (scaffolding) | product_sk |
| dim_date | 1 row per day | Generated | date_key |

### Facts

| Table | Grain | Measures |
|-------|-------|----------|
| fact_transactions | 1 row per line item | quantity, unit_price, total_amount, discount_amount |
| fact_fraud_alerts | 1 row per alert | severity, rule_name, affected_records |

### Aggregations

| Table | Grain | Refresh |
|-------|-------|---------|
| agg_hourly_sales | Store per hour | Every DAG run |
| agg_daily_fraud | Per day | Every DAG run |
| agg_store_performance | Store per day | Every DAG run |

---

## Data Quality Checks

| Check | Table | Threshold | Frequency |
|-------|-------|-----------|-----------|
| Freshness | raw_sales | FAIL if >24h stale | Every DAG run |
| Completeness | clean_sales | FAIL if NULL rate >5% | Every DAG run |
| Accuracy | fact_transactions | WARN if amount outlier | Every DAG run |
| Uniqueness | clean_sales | FAIL if duplicates >0 | Every DAG run |
| Referential Integrity | fact_transactions | FAIL if orphan FKs | Every DAG run |
| Anomaly Detection | agg_hourly_sales | WARN if z-score >3 | Every DAG run |

---

## Data Owners

| Domain | Owner | Contact |
|--------|-------|---------|
| Sales Data | Data Engineering | data-team@mrhealth.com |
| Reference Data | Operations | ops@mrhealth.com |
| Dashboards | Analytics | analytics@mrhealth.com |

---

## Glossary

| Term | Definition |
|------|-----------|
| POS | Point of Sale system in each restaurant unit |
| Medallion | Bronze (raw) -> Silver (clean) -> Gold (business) architecture |
| Star Schema | Dimensional model with fact tables at center, dimensions as points |
| SCD Type 2 | Slowly Changing Dimension that preserves history |
| Quarantine | Table for records that failed validation |
| Content Hash | SHA-256 hash for deduplication |
