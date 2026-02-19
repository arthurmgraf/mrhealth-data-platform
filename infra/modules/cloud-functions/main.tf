###############################################################################
# MR. HEALTH Data Platform - Cloud Functions Module (2nd Gen)
# Manages event-driven and HTTP-triggered Cloud Functions
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
# Cloud Functions (2nd Gen)
# ---------------------------------------------------------------------------
resource "google_cloudfunctions2_function" "functions" {
  for_each = var.functions

  name     = each.value.name
  location = var.region
  project  = var.project_id

  build_config {
    runtime     = each.value.runtime
    entry_point = each.value.entry_point

    source {
      storage_source {
        bucket = each.value.source_bucket
        object = each.value.source_object
      }
    }
  }

  service_config {
    max_instance_count    = each.value.max_instances
    min_instance_count    = each.value.min_instances
    available_memory      = each.value.memory
    timeout_seconds       = each.value.timeout_seconds
    service_account_email = each.value.service_account_email

    environment_variables = each.value.environment_variables

    dynamic "secret_environment_variables" {
      for_each = each.value.secret_env_vars
      content {
        key        = secret_environment_variables.value.env_var
        project_id = var.project_id
        secret     = secret_environment_variables.value.secret_name
        version    = secret_environment_variables.value.version
      }
    }
  }

  # Event trigger (for GCS-triggered functions like csv-processor)
  dynamic "event_trigger" {
    for_each = each.value.event_trigger != null ? [each.value.event_trigger] : []
    content {
      trigger_region        = var.region
      event_type            = event_trigger.value.event_type
      retry_policy          = event_trigger.value.retry_policy
      service_account_email = each.value.service_account_email

      dynamic "event_filters" {
        for_each = event_trigger.value.event_filters
        content {
          attribute = event_filters.value.attribute
          value     = event_filters.value.value
          operator  = lookup(event_filters.value, "operator", null)
        }
      }
    }
  }

  labels = merge(var.common_labels, {
    function = each.key
    runtime  = each.value.runtime
  })
}
