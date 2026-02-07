-- MR. HEALTH Data Platform - Monitoring Layer
-- Table: free_tier_usage
-- Weekly snapshots of GCP Free Tier consumption (GCS storage, BQ storage, BQ queries).

CREATE TABLE IF NOT EXISTS `{PROJECT_ID}.mrhealth_monitoring.free_tier_usage` (
  snapshot_id STRING NOT NULL,
  snapshot_date DATE NOT NULL,
  snapshot_timestamp TIMESTAMP NOT NULL,
  gcs_storage_bytes INT64,
  gcs_storage_gb FLOAT64,
  gcs_limit_gb FLOAT64,
  gcs_usage_pct FLOAT64,
  bq_storage_bytes INT64,
  bq_storage_gb FLOAT64,
  bq_limit_gb FLOAT64,
  bq_usage_pct FLOAT64,
  bq_query_bytes_month INT64,
  bq_query_tb_month FLOAT64,
  bq_query_limit_tb FLOAT64,
  bq_query_usage_pct FLOAT64,
  details STRING
)
PARTITION BY snapshot_date
OPTIONS(
  description="Weekly GCP Free Tier usage snapshots for FinOps monitoring",
  labels=[("layer", "monitoring"), ("purpose", "finops")]
);
