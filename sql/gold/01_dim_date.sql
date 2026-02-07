-- MR. HEALTH Data Platform -- Gold Layer: Date Dimension
-- ===========================================
--
-- Generates a date spine from 2025-01-01 to 2027-12-31 (3 years).
-- This dimension supports time-based analysis and drill-down hierarchies.
--
-- Grain: One row per calendar date
-- Key: date_key (format: YYYYMMDD as string)
--
-- Author: Arthur Graf -- MR. HEALTH Data Platform
-- Date: January 2026

CREATE OR REPLACE TABLE `{PROJECT_ID}.mrhealth_gold.dim_date` AS
SELECT
  -- Primary key (surrogate)
  FORMAT_DATE('%Y%m%d', d) AS date_key,

  -- Natural key
  d AS full_date,

  -- Year hierarchy
  EXTRACT(YEAR FROM d) AS year,
  EXTRACT(QUARTER FROM d) AS quarter,
  FORMAT_DATE('%Y-Q%Q', d) AS year_quarter,

  -- Month hierarchy
  EXTRACT(MONTH FROM d) AS month,
  FORMAT_DATE('%B', d) AS month_name,
  FORMAT_DATE('%Y-%m', d) AS year_month,

  -- Week hierarchy
  EXTRACT(WEEK FROM d) AS week_of_year,
  EXTRACT(ISOWEEK FROM d) AS iso_week,

  -- Day attributes
  EXTRACT(DAY FROM d) AS day_of_month,
  EXTRACT(DAYOFWEEK FROM d) AS day_of_week_num,
  FORMAT_DATE('%A', d) AS day_of_week_name,
  FORMAT_DATE('%a', d) AS day_of_week_abbrev,
  EXTRACT(DAYOFYEAR FROM d) AS day_of_year,

  -- Business attributes
  CASE
    WHEN EXTRACT(DAYOFWEEK FROM d) IN (1, 7) THEN TRUE
    ELSE FALSE
  END AS is_weekend,

  CASE
    WHEN EXTRACT(DAYOFWEEK FROM d) BETWEEN 2 AND 6 THEN TRUE
    ELSE FALSE
  END AS is_weekday,

  -- Additional useful fields
  DATE_DIFF(d, DATE_TRUNC(d, MONTH), DAY) + 1 AS day_in_month,
  LAST_DAY(d, MONTH) AS last_day_of_month,
  DATE_TRUNC(d, MONTH) AS first_day_of_month

FROM UNNEST(
  GENERATE_DATE_ARRAY('2025-01-01', '2027-12-31', INTERVAL 1 DAY)
) AS d;
