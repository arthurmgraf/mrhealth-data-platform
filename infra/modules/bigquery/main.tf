###############################################################################
# MR. HEALTH Data Platform - BigQuery Module
# Manages datasets (Bronze, Silver, Gold, Monitoring) and tables
###############################################################################

terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.20"
    }
  }
}

# ---------------------------------------------------------------------------
# Datasets
# ---------------------------------------------------------------------------
resource "google_bigquery_dataset" "datasets" {
  for_each = var.datasets

  dataset_id                 = each.value.id
  project                    = var.project_id
  location                   = var.location
  friendly_name              = each.value.friendly_name
  description                = each.value.description
  delete_contents_on_destroy = false

  labels = merge(var.common_labels, { layer = each.key })
}

# ---------------------------------------------------------------------------
# Bronze Tables (partitioned by _ingest_date)
# ---------------------------------------------------------------------------
resource "google_bigquery_table" "bronze_tables" {
  for_each = var.bronze_tables

  dataset_id          = google_bigquery_dataset.datasets["bronze"].dataset_id
  table_id            = each.key
  project             = var.project_id
  deletion_protection = false

  schema = file("${path.module}/schemas/${each.key}.json")

  dynamic "time_partitioning" {
    for_each = each.value.partition_field != "" ? [1] : []
    content {
      type  = "DAY"
      field = each.value.partition_field
    }
  }

  labels = merge(var.common_labels, { layer = "bronze", table = each.key })
}

# ---------------------------------------------------------------------------
# Monitoring Tables
# ---------------------------------------------------------------------------
resource "google_bigquery_table" "monitoring_tables" {
  for_each = var.monitoring_tables

  dataset_id          = google_bigquery_dataset.datasets["monitoring"].dataset_id
  table_id            = each.key
  project             = var.project_id
  deletion_protection = false

  schema = file("${path.module}/schemas/${each.key}.json")

  dynamic "time_partitioning" {
    for_each = each.value.partition_field != "" ? [1] : []
    content {
      type  = "DAY"
      field = each.value.partition_field
    }
  }

  labels = merge(var.common_labels, { layer = "monitoring", table = each.key })
}
