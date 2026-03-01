###############################################################################
# MR. HEALTH Data Platform - GCS Module
# Manages the data lake bucket with lifecycle rules
###############################################################################

terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.21"
    }
  }
}

resource "google_storage_bucket" "datalake" {
  name          = var.bucket_name
  project       = var.project_id
  location      = var.location
  force_destroy = false
  storage_class = var.storage_class

  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  versioning {
    enabled = var.versioning_enabled
  }

  # Auto-delete raw CSV files after retention period
  dynamic "lifecycle_rule" {
    for_each = var.lifecycle_rules
    content {
      action {
        type          = lifecycle_rule.value.action_type
        storage_class = lookup(lifecycle_rule.value, "storage_class", null)
      }
      condition {
        age                   = lookup(lifecycle_rule.value, "age_days", null)
        matches_prefix        = lookup(lifecycle_rule.value, "prefix", null) != null ? [lifecycle_rule.value.prefix] : null
        with_state            = lookup(lifecycle_rule.value, "with_state", "ANY")
        num_newer_versions    = lookup(lifecycle_rule.value, "num_newer_versions", null)
      }
    }
  }

  labels = var.common_labels
}
