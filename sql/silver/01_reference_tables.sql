-- MR. HEALTH Data Platform -- Silver Layer: Reference Tables
-- ===============================================
--
-- Cleans and normalizes reference data from Bronze layer.
-- Enriches units with state and country information via joins.
--
-- Author: Arthur Graf -- MR. HEALTH Data Platform
-- Date: January 2026

-- Silver Layer: Products
CREATE OR REPLACE TABLE `{PROJECT_ID}.mrhealth_silver.products` AS
SELECT
  id_produto AS product_id,
  TRIM(nome_produto) AS product_name,
  CURRENT_TIMESTAMP() AS _updated_at
FROM `{PROJECT_ID}.mrhealth_bronze.products`
WHERE id_produto IS NOT NULL;

-- Silver Layer: States
CREATE OR REPLACE TABLE `{PROJECT_ID}.mrhealth_silver.states` AS
SELECT
  id_estado AS state_id,
  id_pais AS country_id,
  TRIM(nome_estado) AS state_name,
  CURRENT_TIMESTAMP() AS _updated_at
FROM `{PROJECT_ID}.mrhealth_bronze.states`
WHERE id_estado IS NOT NULL;

-- Silver Layer: Countries
CREATE OR REPLACE TABLE `{PROJECT_ID}.mrhealth_silver.countries` AS
SELECT
  id_pais AS country_id,
  TRIM(nome_pais) AS country_name,
  CURRENT_TIMESTAMP() AS _updated_at
FROM `{PROJECT_ID}.mrhealth_bronze.countries`
WHERE id_pais IS NOT NULL;

-- Silver Layer: Units (enriched with state and country via joins)
CREATE OR REPLACE TABLE `{PROJECT_ID}.mrhealth_silver.units` AS
SELECT
  u.id_unidade AS unit_id,
  TRIM(u.nome_unidade) AS unit_name,
  s.id_estado AS state_id,
  TRIM(s.nome_estado) AS state_name,
  c.id_pais AS country_id,
  TRIM(c.nome_pais) AS country_name,
  CURRENT_TIMESTAMP() AS _updated_at
FROM `{PROJECT_ID}.mrhealth_bronze.units` u
LEFT JOIN `{PROJECT_ID}.mrhealth_bronze.states` s
  ON u.id_estado = s.id_estado
LEFT JOIN `{PROJECT_ID}.mrhealth_bronze.countries` c
  ON s.id_pais = c.id_pais
WHERE u.id_unidade IS NOT NULL;
