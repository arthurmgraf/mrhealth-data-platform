-- MR. HEALTH Data Platform -- Silver Layer: Order Items
-- ==========================================
--
-- Source: mrhealth_bronze.order_items
-- Transformations:
--   - Calculated field: total_item_value = quantity * unit_price
--   - Type casting (quantity as INT64)
--   - Referential integrity (INNER JOIN with orders)
--   - Deduplication (latest ingestion per order_item_id)
--   - Observation field cleaning
--
-- Author: Arthur Graf -- MR. HEALTH Data Platform
-- Date: January 2026

CREATE OR REPLACE TABLE `{PROJECT_ID}.mrhealth_silver.order_items` AS
SELECT
  -- Primary key
  oi.id_item_pedido AS order_item_id,

  -- Foreign keys
  oi.id_pedido AS order_id,
  oi.id_produto AS product_id,

  -- Measures
  CAST(oi.qtd AS INT64) AS quantity,
  ROUND(oi.vlr_item, 2) AS unit_price,
  ROUND(CAST(oi.qtd AS INT64) * oi.vlr_item, 2) AS total_item_value,

  -- Descriptive (trim and null empty strings)
  CASE
    WHEN oi.observacao IS NOT NULL AND TRIM(oi.observacao) != ''
    THEN TRIM(oi.observacao)
    ELSE NULL
  END AS observation,

  -- Metadata
  oi._source_file,
  oi._ingest_timestamp,
  oi._ingest_date

FROM `{PROJECT_ID}.mrhealth_bronze.order_items` oi

-- Referential integrity: only include items that have matching orders
INNER JOIN `{PROJECT_ID}.mrhealth_bronze.orders` o
  ON oi.id_pedido = o.id_pedido

-- Deduplication: keep latest ingestion per order_item_id
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY oi.id_item_pedido
  ORDER BY oi._ingest_timestamp DESC
) = 1;
