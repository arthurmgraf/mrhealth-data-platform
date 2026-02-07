-- MR. HEALTH Data Platform -- Gold Layer: Daily Sales Aggregation
-- ===================================================
--
-- Pre-aggregated daily sales KPIs for dashboard performance.
-- Powers the Executive and Operations dashboards.
--
-- Grain: One row per date
-- Refresh: Daily after Silver/Gold layer updates
--
-- Author: Arthur Graf -- MR. HEALTH Data Platform
-- Date: January 2026

CREATE OR REPLACE TABLE `{PROJECT_ID}.mrhealth_gold.agg_daily_sales` AS
SELECT
  -- Date dimension
  d.date_key,
  d.full_date AS order_date,
  d.year,
  d.month,
  d.month_name,
  d.year_month,
  d.day_of_week_name,
  d.is_weekend,

  -- Order counts by type
  COUNT(DISTINCT f.order_id) AS total_orders,
  COUNT(DISTINCT CASE WHEN f.order_type = 'ONLINE' THEN f.order_id END) AS online_orders,
  COUNT(DISTINCT CASE WHEN f.order_type = 'PHYSICAL' THEN f.order_id END) AS physical_orders,

  -- Revenue metrics
  ROUND(SUM(f.order_value), 2) AS total_revenue,
  ROUND(SUM(CASE WHEN f.order_type = 'ONLINE' THEN f.order_value ELSE 0 END), 2) AS online_revenue,
  ROUND(SUM(CASE WHEN f.order_type = 'PHYSICAL' THEN f.order_value ELSE 0 END), 2) AS physical_revenue,

  -- Average order value
  ROUND(AVG(f.order_value), 2) AS avg_order_value,

  -- Delivery metrics
  ROUND(SUM(f.delivery_fee), 2) AS total_delivery_fees,
  ROUND(AVG(f.delivery_fee), 2) AS avg_delivery_fee,

  -- Item metrics
  SUM(f.total_items) AS total_items_sold,
  ROUND(AVG(f.total_items), 2) AS avg_items_per_order,

  -- Unit metrics
  COUNT(DISTINCT f.unit_key) AS active_units,

  -- Status distribution
  COUNT(DISTINCT CASE WHEN f.order_status = 'Finalizado' THEN f.order_id END) AS completed_orders,
  COUNT(DISTINCT CASE WHEN f.order_status = 'Cancelado' THEN f.order_id END) AS canceled_orders,
  COUNT(DISTINCT CASE WHEN f.order_status = 'Pendente' THEN f.order_id END) AS pending_orders,

  -- Calculated percentages
  ROUND(100.0 * COUNT(DISTINCT CASE WHEN f.order_type = 'ONLINE' THEN f.order_id END) /
    NULLIF(COUNT(DISTINCT f.order_id), 0), 2) AS online_pct,
  ROUND(100.0 * COUNT(DISTINCT CASE WHEN f.order_status = 'Cancelado' THEN f.order_id END) /
    NULLIF(COUNT(DISTINCT f.order_id), 0), 2) AS cancellation_rate

FROM `{PROJECT_ID}.mrhealth_gold.dim_date` d
LEFT JOIN `{PROJECT_ID}.mrhealth_gold.fact_sales` f
  ON d.date_key = f.date_key

GROUP BY
  d.date_key, d.full_date, d.year, d.month, d.month_name,
  d.year_month, d.day_of_week_name, d.is_weekend

HAVING total_orders > 0  -- Only include dates with actual orders

ORDER BY d.full_date DESC;
