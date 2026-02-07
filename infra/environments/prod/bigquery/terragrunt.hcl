###############################################################################
# MR. HEALTH Data Platform - BigQuery (Prod)
# Datasets: Bronze, Silver, Gold, Monitoring
# Tables: 6 Bronze + 3 Monitoring
###############################################################################

include "root" {
  path = find_in_parent_folders("terragrunt.hcl")
}

include "env" {
  path   = "${get_parent_terragrunt_dir()}/prod/terragrunt.hcl"
  expose = true
}

terraform {
  source = "../../../modules/bigquery"
}

inputs = {
  project_id = include.env.locals.project_id
  location   = "US"

  common_labels = include.env.locals.common_labels

  # ---------------------------------------------------------------------------
  # Datasets (4 Medallion layers)
  # ---------------------------------------------------------------------------
  datasets = {
    bronze = {
      id            = "mrhealth_bronze"
      friendly_name = "MR Health - Bronze Layer"
      description   = "Raw data ingested from CSV files and reference sources"
    }
    silver = {
      id            = "mrhealth_silver"
      friendly_name = "MR Health - Silver Layer"
      description   = "Cleaned, deduplicated, and enriched data"
    }
    gold = {
      id            = "mrhealth_gold"
      friendly_name = "MR Health - Gold Layer"
      description   = "Star schema dimensional model for analytics"
    }
    monitoring = {
      id            = "mrhealth_monitoring"
      friendly_name = "MR Health - Monitoring"
      description   = "Pipeline metrics, data quality logs, and free tier usage"
    }
  }

  # ---------------------------------------------------------------------------
  # Bronze Tables (6 tables, partitioned by _ingest_date)
  # ---------------------------------------------------------------------------
  bronze_tables = {
    orders = {
      partition_field = "_ingest_date"
    }
    order_items = {
      partition_field = "_ingest_date"
    }
    products = {
      partition_field = ""
    }
    units = {
      partition_field = ""
    }
    states = {
      partition_field = ""
    }
    countries = {
      partition_field = ""
    }
  }

  # ---------------------------------------------------------------------------
  # Monitoring Tables (3 tables)
  # ---------------------------------------------------------------------------
  monitoring_tables = {
    data_quality_log = {
      partition_field = "execution_date"
    }
    pipeline_metrics = {
      partition_field = "execution_date"
    }
    free_tier_usage = {
      partition_field = "snapshot_date"
    }
  }
}
