-- MR. HEALTH Data Platform - Monitoring Layer
-- Table: pipeline_metrics
-- Stores pipeline execution metrics (duration, rows processed, failures, SLA misses).

CREATE TABLE IF NOT EXISTS `{PROJECT_ID}.mrhealth_monitoring.pipeline_metrics` (
  metric_id STRING NOT NULL,
  dag_id STRING NOT NULL,
  dag_run_id STRING,
  task_id STRING,
  metric_name STRING NOT NULL,
  metric_value FLOAT64 NOT NULL,
  metric_unit STRING,
  execution_date DATE NOT NULL,
  execution_timestamp TIMESTAMP NOT NULL,
  details STRING
)
PARTITION BY execution_date
OPTIONS(
  description="Pipeline execution metrics for Airflow DAGs",
  labels=[("layer", "monitoring"), ("purpose", "pipeline")]
);
