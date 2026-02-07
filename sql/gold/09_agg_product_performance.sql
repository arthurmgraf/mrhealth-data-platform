-- MR. HEALTH Data Platform -- Gold Layer: Product Performance Aggregation
-- ============================================================
--
-- Pre-aggregated product-level KPIs for operations dashboard.
-- Identifies best-selling products and revenue contributors.
--
-- Grain: One row per product
-- Refresh: Daily after Silver/Gold layer updates
--
-- Author: Arthur Graf -- MR. HEALTH Data Platform
-- Date: January 2026

CREATE OR REPLACE TABLE `{PROJECT_ID}.mrhealth_gold.agg_product_performance` AS
SELECT
  -- Product dimensions
  p.product_key,
  p.product_id,
  p.product_name,

  -- Order and item counts
  COUNT(DISTINCT fi.order_id) AS total_orders,
  COUNT(DISTINCT fi.item_id) AS total_line_items,

  -- Quantity metrics
  SUM(fi.quantity) AS total_quantity_sold,
  ROUND(AVG(fi.quantity), 2) AS avg_quantity_per_order,

  -- Revenue metrics
  ROUND(SUM(fi.total_item_value), 2) AS total_revenue,
  ROUND(AVG(fi.unit_price), 2) AS avg_unit_price,
  ROUND(AVG(fi.total_item_value), 2) AS avg_line_value,

  -- Distribution metrics
  COUNT(DISTINCT fi.unit_key) AS units_selling_product,
  ROUND(100.0 * COUNT(DISTINCT fi.unit_key) /
    (SELECT COUNT(*) FROM `{PROJECT_ID}.mrhealth_gold.dim_unit`), 2) AS unit_penetration_pct,

  -- Date range
  MIN(fi.order_date) AS first_sold_date,
  MAX(fi.order_date) AS last_sold_date,

  -- Rankings
  RANK() OVER (ORDER BY SUM(fi.total_item_value) DESC) AS revenue_rank,
  RANK() OVER (ORDER BY SUM(fi.quantity) DESC) AS volume_rank

FROM `{PROJECT_ID}.mrhealth_gold.dim_product` p
LEFT JOIN `{PROJECT_ID}.mrhealth_gold.fact_order_items` fi
  ON p.product_key = fi.product_key

GROUP BY
  p.product_key, p.product_id, p.product_name

HAVING total_orders > 0  -- Only include products that have been sold

ORDER BY total_revenue DESC;
