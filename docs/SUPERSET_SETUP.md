# Apache Superset Setup Guide

> Dashboard configuration guide for the MR. HEALTH Data Platform - Superset 4.0.2 on K3s

---

## Overview

The MR. HEALTH Data Platform uses Apache Superset for data visualization and business intelligence dashboards.

**Stack:**
- Apache Superset 4.0.2 on K3s (NodePort 30188)
- PostgreSQL metadata database (shared with Airflow)
- BigQuery as the analytics data source (via sqlalchemy-bigquery)
- 4 production dashboards, 25 datasets, 25 charts, 9 native filters
- Custom CSS theme (mrhealth-green.css with #28a745)

**Access:**
- Production: `http://15.235.61.251:30188`
- Anonymous access enabled (Viewer role) for portfolio viewing

---

## Prerequisites

Before setting up Superset dashboards, ensure:

1. **Superset deployed on K3s**
   - Manifests: `k8s/superset/`
   - Namespace: `mrhealth-db`
   - PostgreSQL metadata database created (`superset_db`)

2. **BigQuery datasets populated**
   - Gold layer tables: `mrhealth_gold.dim_*`, `mrhealth_gold.fact_*`, `mrhealth_gold.agg_*`
   - Run: `python scripts/build_gold_layer.py` and `python scripts/build_aggregations.py`

3. **GCP credentials configured**
   - ADC credentials: `/home/arthur/mrhealth-data-platform/keys/gcp.json`
   - Environment variable: `GOOGLE_APPLICATION_CREDENTIALS` set in Superset deployment

4. **Dependencies installed**
   - `sqlalchemy-bigquery` driver (installed via initContainer in Superset manifest)
   - `packaging<24` (version conflict fix)

---

## Automated Setup

The fastest way to configure all dashboards is via the automated setup script:

```bash
# From project root
python scripts/setup_superset_dashboards_v2.py
```

**What the script does:**
1. Authenticates using session-based login (GET CSRF token -> POST login form)
2. Creates BigQuery database connection
3. Creates 25 datasets from Gold layer tables
4. Creates 25 charts with visualization configs
5. Creates 4 dashboards with chart layouts
6. Configures 9 native filters (cross-filter enabled)
7. Applies CSS theme (mrhealth-green.css)

**Script features:**
- Idempotent: safe to run multiple times (updates existing objects)
- Session-based auth: works with Superset 4.x (JWT broken)
- Structured logging: detailed progress output

---

## Dashboard Details

### 1. Executive Overview

**Purpose:** C-level KPIs and high-level trends

**Charts:**
- Total Revenue (Big Number): `agg_daily_revenue` SUM(total_revenue)
- Daily Revenue Trend (Line): `agg_daily_revenue` by order_date
- Order Volume (Bar): `agg_daily_revenue` SUM(order_count) by order_date
- Channel Mix (Pie): `agg_daily_revenue` by channel
- Status Breakdown (Donut): `agg_daily_revenue` by status

**Native Filters:**
- Date range (filter_time)
- State (filter_select)
- Order status (filter_select)

**URL:** `http://15.235.61.251:30188/superset/dashboard/executive-overview/`

---

### 2. Unit Performance

**Purpose:** Operations manager view - unit-level metrics

**Charts:**
- Revenue by Unit (Bar): `agg_unit_daily` SUM(total_revenue) by unit_name
- Cancellation Rate (Gauge): `agg_unit_daily` cancellation_rate %
- Online Order % (Bar): `agg_unit_daily` online_order_pct by unit_name
- Top 10 Units (Table): `agg_unit_daily` ranked by total_revenue

**Native Filters:**
- Date range (filter_time)
- Unit name (filter_select)
- State (filter_select)

**URL:** `http://15.235.61.251:30188/superset/dashboard/unit-performance/`

---

### 3. Product Analytics

**Purpose:** Product management insights - SKU performance

**Charts:**
- Revenue by Product (Horizontal Bar): `agg_product_daily` SUM(total_revenue) by product_name
- Volume Ranking (Table): `agg_product_daily` SUM(quantity_sold) ranked
- Unit Penetration Matrix (Heatmap): `fact_order_items` COUNT(DISTINCT unit_key) by product

**Native Filters:**
- Date range (filter_time)
- Product name (filter_select)

**URL:** `http://15.235.61.251:30188/superset/dashboard/product-analytics/`

---

### 4. Order Detail

**Purpose:** Drill-down analysis - order and item-level data

**Charts:**
- Order Table: `fact_sales` with columns: order_id, order_date, unit_name, order_value, status
- Item Breakdown (Table): `fact_order_items` with product_name, quantity, unit_price
- Order Value Distribution (Histogram): `fact_sales` order_value bins
- Delivery Fee Analysis (Bar): `fact_sales` AVG(delivery_fee) by channel

**Native Filters:**
- Date range (filter_time)
- Unit (filter_select)
- Status (filter_select)
- Order type (filter_select)

**URL:** `http://15.235.61.251:30188/superset/dashboard/order-detail/`

---

## Native Filters

Superset 4.x uses **native filters** instead of deprecated Filter Box component.

**Configured filters (9 total):**
- `date_range` (filter_time): Used in all dashboards
- `state_filter` (filter_select): Executive Overview, Unit Performance
- `status_filter` (filter_select): Executive Overview, Order Detail
- `unit_filter` (filter_select): Unit Performance, Order Detail
- `product_filter` (filter_select): Product Analytics
- `channel_filter` (filter_select): Order Detail

**Features:**
- Cross-filter enabled: filters apply across multiple charts
- Scoped to specific dashboards
- Persisted in dashboard JSON metadata

---

## BigQuery Connection

**Connection details:**
- **Type:** Google BigQuery
- **SQLAlchemy URI:** `bigquery://mrhealth-datalake-485810`
- **Authentication:** ADC (Application Default Credentials)
- **Driver:** `sqlalchemy-bigquery` (installed in initContainer)

**Manual connection creation:**
1. Navigate to: Settings > Database Connections > + Database
2. Select: Google BigQuery
3. Enter SQLAlchemy URI: `bigquery://mrhealth-datalake-485810`
4. Test connection
5. Save

---

## CSS Theme

**Custom theme:** `mrhealth-green.css`

**Colors:**
- Primary: `#28a745` (green)
- Secondary: `#6c757d` (gray)
- Success: `#28a745`
- Danger: `#dc3545`

**Applied globally via:**
- Superset CSS templates configuration
- `superset_config.py`: `EXTRA_CATEGORICAL_COLOR_SCHEMES`

---

## Known Issues & Solutions

### 1. JWT Authentication Broken (Superset 4.x)

**Issue:** JWT tokens don't properly set `g.user`, causing DatabaseFilter to return empty results.

**Solution:** Use session-based authentication instead.

```python
# GET CSRF token
response = session.get(f"{base_url}/login/")
csrf_token = extract_csrf_token(response.text)

# POST login form
session.post(f"{base_url}/login/", data={
    "username": "admin",
    "password": "admin",
    "csrf_token": csrf_token
})
```

### 2. Packaging Version Conflict

**Issue:** `packaging>=24` conflicts with other dependencies.

**Solution:** Install `packaging<24` BEFORE other dependencies in initContainer.

```yaml
command: ["/bin/sh", "-c"]
args:
  - |
    pip install --upgrade pip
    pip install packaging==23.2
    pip install sqlalchemy-bigquery
```

### 3. Apache Superset 4.1.0 Image Missing

**Issue:** `apache/superset:4.1.0` doesn't exist on Docker Hub.

**Solution:** Use `apache/superset:4.0.2` (latest stable).

### 4. Stale .local Packages

**Issue:** Old Python packages in `/app/superset_home/.local` cause import errors.

**Solution:** Clear stale packages in initContainer.

```bash
rm -rf /app/superset_home/.local
```

---

## Manual Dashboard Creation

If the automated script fails, create dashboards manually via Superset UI:

### Step 1: Create Database Connection
1. Navigate to: Settings > Database Connections > + Database
2. Select: Google BigQuery
3. Enter SQLAlchemy URI: `bigquery://mrhealth-datalake-485810`
4. Test connection and Save

### Step 2: Create Datasets
1. Navigate to: Datasets > + Dataset
2. Select database: BigQuery
3. Select schema: `mrhealth_gold`
4. Select table: `dim_product`, `fact_sales`, etc.
5. Save (repeat for 25 datasets)

### Step 3: Create Charts
1. Navigate to: Charts > + Chart
2. Select dataset and visualization type
3. Configure metrics, dimensions, filters
4. Save (repeat for 25 charts)

### Step 4: Create Dashboards
1. Navigate to: Dashboards > + Dashboard
2. Drag charts from sidebar to canvas
3. Arrange and resize
4. Configure native filters
5. Publish

---

## Verification

Verify the setup using the verification script:

```bash
python scripts/verify_superset_upgrade.py
```

**Expected output:**
```
✓ Database connection exists
✓ 25 datasets created
✓ 25 charts created
✓ 4 dashboards created
✓ Native filters configured
✓ CSS theme applied
✓ BigQuery connectivity OK
✓ Query execution successful
✓ Anonymous access enabled
```

**Tests:** 9/9 passing

---

## Maintenance

### Refresh Data
Dashboards automatically reflect BigQuery updates (no caching by default).

### Update Dashboards
Re-run setup script to update existing dashboards:
```bash
python scripts/setup_superset_dashboards_v2.py
```

### Clear Cache
If stale data appears:
1. Navigate to: Settings > Database Connections > BigQuery
2. Click: Clear Cache

### Backup Dashboards
Export dashboard JSON:
1. Navigate to: Dashboards > [Dashboard Name]
2. Click: ⋮ > Export
3. Save JSON file

---

## References

- **Superset Documentation:** https://superset.apache.org/docs/intro
- **BigQuery SQL Reference:** https://cloud.google.com/bigquery/docs/reference/standard-sql
- **Deployment Manifests:** `k8s/superset/`
- **Setup Script:** `scripts/setup_superset_dashboards_v2.py`
- **Verification Script:** `scripts/verify_superset_upgrade.py`

---

**Last Updated:** 2026-02-07 (Superset 4.0.2 upgrade)
