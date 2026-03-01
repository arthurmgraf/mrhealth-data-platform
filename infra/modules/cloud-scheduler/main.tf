###############################################################################
# MR. HEALTH Data Platform - Cloud Scheduler Module
# Manages cron-based HTTP triggers for Cloud Functions
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

resource "google_cloud_scheduler_job" "jobs" {
  for_each = var.scheduler_jobs

  name      = each.value.name
  project   = var.project_id
  region    = var.region
  schedule  = each.value.schedule
  time_zone = each.value.timezone

  description      = each.value.description
  attempt_deadline = each.value.attempt_deadline

  retry_config {
    retry_count          = each.value.retry_count
    max_retry_duration   = each.value.max_retry_duration
    min_backoff_duration = each.value.min_backoff_duration
    max_backoff_duration = each.value.max_backoff_duration
    max_doublings        = each.value.max_doublings
  }

  http_target {
    http_method = each.value.http_method
    uri         = each.value.target_uri

    dynamic "oidc_token" {
      for_each = each.value.oidc_service_account != null ? [1] : []
      content {
        service_account_email = each.value.oidc_service_account
        audience              = each.value.target_uri
      }
    }

    headers = each.value.headers
    body    = each.value.body != null ? base64encode(each.value.body) : null
  }
}
