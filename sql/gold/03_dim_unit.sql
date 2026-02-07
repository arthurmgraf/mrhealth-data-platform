-- MR. HEALTH Data Platform -- Gold Layer: Unit Dimension
-- ===========================================
--
-- Unit (store location) dimension denormalized with geography hierarchy.
-- Includes state and country for simplified reporting.
--
-- Grain: One row per unit
-- Key: unit_key (same as unit_id)
--
-- Author: Arthur Graf -- MR. HEALTH Data Platform
-- Date: January 2026

CREATE OR REPLACE TABLE `{PROJECT_ID}.mrhealth_gold.dim_unit` AS
SELECT
  -- Surrogate key
  unit_id AS unit_key,

  -- Natural key
  unit_id,

  -- Unit attributes
  unit_name,

  -- Geography hierarchy (denormalized for performance)
  state_id,
  state_name,
  country_id,
  country_name,

  -- SCD Type 2 support (prepared for future use)
  CURRENT_TIMESTAMP() AS _valid_from,
  TIMESTAMP('9999-12-31 23:59:59') AS _valid_to,
  TRUE AS is_current

FROM `{PROJECT_ID}.mrhealth_silver.units`;
