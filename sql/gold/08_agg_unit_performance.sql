-- MR. HEALTH Data Platform -- Gold Layer: Unit Performance Aggregation
-- =========================================================
--
-- Pre-aggregated unit-level KPIs for operations dashboard.
-- Ranks units by revenue and identifies performance leaders/laggards.
--
-- Grain: One row per unit
-- Refresh: Daily after Silver/Gold layer updates
--
-- Author: Arthur Graf -- MR. HEALTH Data Platform
-- Date: January 2026

CREATE OR REPLACE TABLE `{PROJECT_ID}.mrhealth_gold.agg_unit_performance` AS
SELECT
  -- Unit dimensions
  u.unit_key,
  u.unit_id,
  u.unit_name,
  u.state_name,
  u.country_name,

  -- Order counts
  COUNT(DISTINCT f.order_id) AS total_orders,
  COUNT(DISTINCT CASE WHEN f.order_type = 'ONLINE' THEN f.order_id END) AS online_orders,
  COUNT(DISTINCT CASE WHEN f.order_type = 'PHYSICAL' THEN f.order_id END) AS physical_orders,

  -- Revenue metrics
  ROUND(SUM(f.order_value), 2) AS total_revenue,
  ROUND(AVG(f.order_value), 2) AS avg_order_value,

  -- Item metrics
  SUM(f.total_items) AS total_items_sold,
  ROUND(AVG(f.total_items), 2) AS avg_items_per_order,

  -- Status distribution
  COUNT(DISTINCT CASE WHEN f.order_status = 'Finalizado' THEN f.order_id END) AS completed_orders,
  COUNT(DISTINCT CASE WHEN f.order_status = 'Cancelado' THEN f.order_id END) AS canceled_orders,

  -- Performance metrics
  ROUND(100.0 * COUNT(DISTINCT CASE WHEN f.order_status = 'Cancelado' THEN f.order_id END) /
    NULLIF(COUNT(DISTINCT f.order_id), 0), 2) AS cancellation_rate,
  ROUND(100.0 * COUNT(DISTINCT CASE WHEN f.order_type = 'ONLINE' THEN f.order_id END) /
    NULLIF(COUNT(DISTINCT f.order_id), 0), 2) AS online_pct,

  -- Date range
  MIN(f.order_date) AS first_order_date,
  MAX(f.order_date) AS last_order_date,
  DATE_DIFF(MAX(f.order_date), MIN(f.order_date), DAY) + 1 AS days_active,

  -- Ranking (calculated in outer query)
  RANK() OVER (ORDER BY SUM(f.order_value) DESC) AS revenue_rank,
  RANK() OVER (ORDER BY COUNT(DISTINCT f.order_id) DESC) AS order_volume_rank

FROM `{PROJECT_ID}.mrhealth_gold.dim_unit` u
LEFT JOIN `{PROJECT_ID}.mrhealth_gold.fact_sales` f
  ON u.unit_key = f.unit_key

GROUP BY
  u.unit_key, u.unit_id, u.unit_name, u.state_name, u.country_name

HAVING total_orders > 0  -- Only include units with orders

ORDER BY total_revenue DESC;
