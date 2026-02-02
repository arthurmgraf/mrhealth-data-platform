# Superset Setup Guide

Deploy Apache Superset locally via Docker to visualize the MR. Health Gold layer with 3 branded dashboards.

## Prerequisites

- Docker Desktop 24.x+ with Docker Compose V2
- GCP service account key with BigQuery read access to `case_ficticio_gold`
- Gold layer populated (run `python scripts/build_gold_layer.py` + `python scripts/build_aggregations.py` first)

## 1. Place GCP Credentials

```bash
mkdir -p keys
cp /path/to/your-service-account.json keys/service-account.json
```

This file is gitignored and mounted at `/app/keys/gcp.json` inside the container.

## 2. Build and Start Superset

```bash
docker compose -f docker-compose-superset.yml build
docker compose -f docker-compose-superset.yml up -d
```

First startup runs `superset-init` which:
1. Migrates the SQLite metadata database
2. Creates the admin user (admin/admin)
3. Initializes default roles

Wait for the health check to pass:

```bash
docker compose -f docker-compose-superset.yml ps
```

The `superset` service should show as healthy. `superset-init` will show as exited (0).

## 3. Login

Open http://localhost:8088

- **Username:** `admin`
- **Password:** `admin`

## 4. Add BigQuery Data Source

1. Go to **Settings** (gear icon) -> **Database Connections** -> **+ Database**
2. Select **Google BigQuery**
3. Set **SQLAlchemy URI:**
   ```
   bigquery://YOUR_PROJECT_ID
   ```
   Replace `YOUR_PROJECT_ID` with your GCP project ID (e.g., `sixth-foundry-485810-e5`)

4. Click **Advanced** -> **Secure Extra** and paste:
   ```json
   {
     "engine_params": {
       "credentials_path": "/app/keys/gcp.json"
     }
   }
   ```

5. Click **Test Connection** -> should show "Connection looks good!"
6. Click **Connect**

### Verify the Connection

Go to **SQL Lab** -> **SQL Editor** and run:

```sql
SELECT COUNT(*) AS row_count FROM case_ficticio_gold.agg_daily_sales
```

Should return a positive row count.

## 5. Create Datasets

Register these datasets from the BigQuery connection:

| Dataset Name | Source Table | Used By |
|-------------|-------------|---------|
| `agg_daily_sales` | `case_ficticio_gold.agg_daily_sales` | Executive Dashboard |
| `agg_unit_performance` | `case_ficticio_gold.agg_unit_performance` | Operations Dashboard |
| `agg_product_performance` | `case_ficticio_gold.agg_product_performance` | Product Dashboard |
| `fact_sales` | `case_ficticio_gold.fact_sales` | Operations drill-down |
| `fact_order_items` | `case_ficticio_gold.fact_order_items` | Product drill-down |

To add each: **Data** -> **Datasets** -> **+ Dataset** -> Select database, schema (`case_ficticio_gold`), and table.

## 6. Create Dashboards

### Dashboard 1: MR. Health -- Executive Overview

**Data:** `agg_daily_sales`

| # | Chart | Type | Metric | Color |
|---|-------|------|--------|-------|
| 1 | Total Revenue | Big Number with Trendline | `SUM(total_revenue)` | `#2f9e44` |
| 2 | Total Orders | Big Number with Trendline | `SUM(total_orders)` | `#4285F4` |
| 3 | Avg Order Value | Big Number | `AVG(avg_order_value)` | `#FBBC04` |
| 4 | Cancellation Rate | Big Number | `AVG(cancellation_rate)` | `#fa5252` |
| 5 | Revenue Trend | Mixed Time-Series | Revenue (line) + Orders (bar) by `order_date` | Green/Blue |
| 6 | Online vs Physical | Donut Chart | Custom SQL (see below) | Blue/Amber |
| 7 | Revenue by Day of Week | Bar Chart | `SUM(total_revenue)` by `day_of_week_name` | MR. Health palette |
| 8 | Weekend vs Weekday | Pivot Table | Orders + Revenue by `is_weekend` | -- |

**Donut Chart SQL Dataset:**

```sql
SELECT 'Online' AS channel, SUM(online_orders) AS orders
FROM case_ficticio_gold.agg_daily_sales
UNION ALL
SELECT 'Physical', SUM(physical_orders)
FROM case_ficticio_gold.agg_daily_sales
```

### Dashboard 2: MR. Health -- Operations & Unit Performance

**Data:** `agg_unit_performance`, `fact_sales`

| # | Chart | Type | Key Settings |
|---|-------|------|-------------|
| 1 | Unit Revenue Ranking | Horizontal Bar | Top 15 units by `total_revenue`, descending |
| 2 | State Performance | Pivot Table | Group by `state_name`: orders, revenue, avg_ticket, online_pct |
| 3 | Unit Scatter | Scatter Plot | X: `total_orders`, Y: `avg_order_value`, Size: `total_revenue` |
| 4 | Cancellation Leaderboard | Table | `unit_name` + `cancellation_rate`, sorted descending |
| 5 | Online Adoption | Stacked Bar | `online_orders` vs `physical_orders` per unit |

**State Performance SQL:**

```sql
SELECT
  state_name,
  COUNT(*) AS units,
  SUM(total_orders) AS orders,
  ROUND(SUM(total_revenue), 2) AS revenue,
  ROUND(AVG(avg_order_value), 2) AS avg_ticket,
  ROUND(AVG(online_pct), 2) AS avg_online_pct,
  ROUND(AVG(cancellation_rate), 2) AS avg_cancel_rate
FROM case_ficticio_gold.agg_unit_performance
GROUP BY state_name
ORDER BY revenue DESC
```

### Dashboard 3: MR. Health -- Product Analytics

**Data:** `agg_product_performance`, `fact_order_items`

| # | Chart | Type | Key Settings |
|---|-------|------|-------------|
| 1 | Product Revenue | Treemap | `product_name` sized by `total_revenue` |
| 2 | Top 10 Products | Horizontal Bar | Top 10 by `total_revenue` |
| 3 | Price vs Volume | Scatter | X: `avg_unit_price`, Y: `total_quantity_sold` |
| 4 | Revenue Over Time | Area Chart | Stacked, top 5 products from `fact_order_items` |
| 5 | ABC Classification | Pie Chart | A/B/C classes (see SQL below) |

**ABC Classification SQL:**

```sql
SELECT
  product_name,
  total_revenue,
  total_quantity_sold,
  avg_unit_price,
  revenue_rank,
  CASE
    WHEN SUM(total_revenue) OVER (ORDER BY total_revenue DESC
      ROWS UNBOUNDED PRECEDING) / SUM(total_revenue) OVER () <= 0.80 THEN 'A'
    WHEN SUM(total_revenue) OVER (ORDER BY total_revenue DESC
      ROWS UNBOUNDED PRECEDING) / SUM(total_revenue) OVER () <= 0.95 THEN 'B'
    ELSE 'C'
  END AS abc_class
FROM case_ficticio_gold.agg_product_performance
ORDER BY revenue_rank ASC
```

## 7. Apply Dark Theme

For each of the 3 dashboards:

1. Open the dashboard
2. Click **Edit Dashboard** (pencil icon)
3. Click **...** (three dots) -> **Edit CSS**
4. Paste the following CSS:

```css
.dashboard { background-color: #1e1e2e !important; }
.dashboard-component-tabs { background-color: #1e1e2e !important; }

.dashboard-component-chart-holder {
  background-color: #2a2a3e !important;
  border-radius: 8px !important;
  border: 1px solid #3a3a4e !important;
}

.header-title, .dashboard-title { color: #e0e0e0 !important; }
.chart-header .header-title span { color: #e0e0e0 !important; }

.dashboard-component-tabs .ant-tabs-tab { color: #868e96 !important; }
.dashboard-component-tabs .ant-tabs-tab-active { color: #4285F4 !important; }

.filter-bar { background-color: #2a2a3e !important; }

.superset-legacy-chart-big-number .header-line { font-weight: 700 !important; }

.table-condensed th { color: #e0e0e0 !important; background-color: #3a3a4e !important; }
.table-condensed td { color: #c0c0c0 !important; }
```

5. Click **Save**

## 8. Take Portfolio Screenshots

Once all 3 dashboards are created and themed:

1. Set browser to full-screen (F11)
2. Navigate to each dashboard
3. Use browser screenshot tool or Snipping Tool
4. Save as high-quality PNG files

Recommended naming:
- `screenshots/superset_executive_dashboard.png`
- `screenshots/superset_operations_dashboard.png`
- `screenshots/superset_product_dashboard.png`

## 9. Stop Superset

```bash
docker compose -f docker-compose-superset.yml down
```

To preserve dashboard data across restarts, the `superset-data` named volume persists automatically. To fully reset:

```bash
docker compose -f docker-compose-superset.yml down -v
```

## 10. Troubleshooting

| Issue | Solution |
|-------|----------|
| `sqlalchemy.dialects:bigquery` not found | Rebuild image: `docker compose -f docker-compose-superset.yml build --no-cache` |
| Connection failed on BigQuery | Verify `keys/service-account.json` exists and has BigQuery permissions |
| Charts show "No data" | Run Gold layer build first: `python scripts/build_aggregations.py` |
| Container restart loop | Check init logs: `docker compose -f docker-compose-superset.yml logs superset-init` |
| Slow dashboard loading | Ensure charts use `agg_*` tables, not `fact_*` tables |
| Port 8088 in use | Change port in `docker-compose-superset.yml` or stop conflicting service |
| gevent/threading errors | Verify `--worker-class gthread` is set in docker-compose command |

## Color Reference

| Role | Hex | Usage |
|------|-----|-------|
| Primary | `#4285F4` | Online metrics, main KPI |
| Success | `#2f9e44` | Revenue, growth |
| Warning | `#FBBC04` | Averages, physical store |
| Danger | `#fa5252` | Cancellations, alerts |
| Neutral | `#868e96` | Secondary data |
| Background | `#1e1e2e` | Dashboard background |
| Card | `#2a2a3e` | Chart card background |
| Text | `#e0e0e0` | Headers and labels |
