-- MR. HEALTH Data Platform -- Gold Layer: Product Dimension
-- ==============================================
--
-- Product dimension with SCD Type 2 support (slowly changing dimension).
-- Currently implemented as Type 1 (overwrite), but structure allows future Type 2.
--
-- Grain: One row per product
-- Key: product_key (same as product_id for now)
--
-- Author: Arthur Graf -- MR. HEALTH Data Platform
-- Date: January 2026

CREATE OR REPLACE TABLE `{PROJECT_ID}.mrhealth_gold.dim_product` AS
SELECT
  -- Surrogate key
  product_id AS product_key,

  -- Natural key
  product_id,

  -- Attributes
  product_name,

  -- SCD Type 2 support (currently not used, but prepared for future)
  CURRENT_TIMESTAMP() AS _valid_from,
  TIMESTAMP('9999-12-31 23:59:59') AS _valid_to,
  TRUE AS is_current

FROM `{PROJECT_ID}.mrhealth_silver.products`;
