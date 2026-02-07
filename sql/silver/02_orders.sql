-- MR. HEALTH Data Platform -- Silver Layer: Orders
-- =====================================
--
-- Source: mrhealth_bronze.orders
-- Transformations:
--   - Type normalization (ONLINE/PHYSICAL)
--   - Business rules for delivery addresses
--   - Date enrichment (year, month, day, day_of_week)
--   - Calculated fields (items_subtotal)
--   - Deduplication (latest ingestion per order_id)
--
-- Author: Arthur Graf -- MR. HEALTH Data Platform
-- Date: January 2026

CREATE OR REPLACE TABLE `{PROJECT_ID}.mrhealth_silver.orders` AS
SELECT
  -- Primary key
  o.id_pedido AS order_id,

  -- Dimensions
  o.id_unidade AS unit_id,
  CASE
    WHEN UPPER(o.tipo_pedido) LIKE '%ONLINE%' THEN 'ONLINE'
    WHEN UPPER(o.tipo_pedido) LIKE '%FISIC%' THEN 'PHYSICAL'
    ELSE 'UNKNOWN'
  END AS order_type,
  o.status AS order_status,

  -- Date fields
  o.data_pedido AS order_date,
  EXTRACT(YEAR FROM o.data_pedido) AS order_year,
  EXTRACT(MONTH FROM o.data_pedido) AS order_month,
  EXTRACT(DAY FROM o.data_pedido) AS order_day,
  FORMAT_DATE('%A', o.data_pedido) AS order_day_of_week,

  -- Monetary fields (rounded to 2 decimals)
  ROUND(o.vlr_pedido, 2) AS order_value,
  ROUND(o.taxa_entrega, 2) AS delivery_fee,
  ROUND(o.vlr_pedido - o.taxa_entrega, 2) AS items_subtotal,

  -- Delivery info (only for online orders with valid address)
  CASE
    WHEN o.tipo_pedido = 'Loja Online'
      AND (o.endereco_entrega IS NOT NULL AND TRIM(o.endereco_entrega) != '')
    THEN TRIM(o.endereco_entrega)
    ELSE NULL
  END AS delivery_address,

  -- Metadata
  o._source_file,
  o._ingest_timestamp,
  o._ingest_date

FROM `{PROJECT_ID}.mrhealth_bronze.orders` o

-- Deduplication: keep latest ingestion per order_id
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY o.id_pedido
  ORDER BY o._ingest_timestamp DESC
) = 1;
