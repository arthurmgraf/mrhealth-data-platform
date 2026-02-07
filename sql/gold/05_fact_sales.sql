-- MR. HEALTH Data Platform -- Gold Layer: Sales Fact Table
-- =============================================
--
-- Order-level fact table for sales analysis.
-- Aggregates item-level details to order grain.
--
-- Grain: One row per order
-- Partitioning: By order_date for performance
-- Clustering: By unit_key and order_type
--
-- Author: Arthur Graf -- MR. HEALTH Data Platform
-- Date: January 2026

CREATE OR REPLACE TABLE `{PROJECT_ID}.mrhealth_gold.fact_sales`
PARTITION BY order_date
CLUSTER BY unit_key, order_type
AS
SELECT
  -- Primary key
  o.order_id,

  -- Foreign keys to dimensions
  FORMAT_DATE('%Y%m%d', o.order_date) AS date_key,
  o.order_date,
  o.unit_id AS unit_key,

  -- Degenerate dimensions (dimensions stored in fact table)
  o.order_type,
  o.order_status,

  -- Additive measures (can be summed across dimensions)
  o.order_value,
  o.delivery_fee,
  o.items_subtotal,

  -- Aggregated item metrics
  COALESCE(item_agg.total_items, 0) AS total_items,
  COALESCE(item_agg.distinct_products, 0) AS distinct_products,
  COALESCE(item_agg.total_quantity, 0) AS total_quantity,

  -- Non-additive attributes
  o.delivery_address,

  -- Metadata
  o._ingest_date

FROM `{PROJECT_ID}.mrhealth_silver.orders` o

LEFT JOIN (
  SELECT
    order_id,
    COUNT(*) AS total_items,
    COUNT(DISTINCT product_id) AS distinct_products,
    SUM(quantity) AS total_quantity
  FROM `{PROJECT_ID}.mrhealth_silver.order_items`
  GROUP BY order_id
) item_agg
  ON o.order_id = item_agg.order_id;
