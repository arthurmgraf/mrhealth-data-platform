-- MR. HEALTH Data Platform - Monitoring Layer
-- Table: data_quality_log
-- Stores results from automated quality checks across all Medallion layers.

CREATE TABLE IF NOT EXISTS `{PROJECT_ID}.mrhealth_monitoring.data_quality_log` (
  check_id STRING NOT NULL,
  check_name STRING NOT NULL,
  check_category STRING NOT NULL,
  layer STRING NOT NULL,
  table_name STRING,
  check_sql STRING,
  result STRING NOT NULL,
  expected_value STRING,
  actual_value STRING,
  details STRING,
  execution_date DATE NOT NULL,
  execution_timestamp TIMESTAMP NOT NULL,
  dag_run_id STRING,
  duration_seconds FLOAT64
)
PARTITION BY execution_date
OPTIONS(
  description="Data quality check results across Bronze/Silver/Gold layers",
  labels=[("layer", "monitoring"), ("purpose", "quality")]
);
