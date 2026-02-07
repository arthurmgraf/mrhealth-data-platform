-- MR. HEALTH Data Platform -- Gold Layer: Geography Dimension
-- ================================================
--
-- Geography dimension with state-country hierarchy.
-- Provides normalized geography lookup separate from units.
--
-- Grain: One row per state
-- Key: geography_key (same as state_id)
--
-- Author: Arthur Graf -- MR. HEALTH Data Platform
-- Date: January 2026

CREATE OR REPLACE TABLE `{PROJECT_ID}.mrhealth_gold.dim_geography` AS
SELECT
  -- Surrogate key
  s.state_id AS geography_key,

  -- State attributes
  s.state_id,
  s.state_name,

  -- Country attributes
  c.country_id,
  c.country_name

FROM `{PROJECT_ID}.mrhealth_silver.states` s
JOIN `{PROJECT_ID}.mrhealth_silver.countries` c
  ON s.country_id = c.country_id;
