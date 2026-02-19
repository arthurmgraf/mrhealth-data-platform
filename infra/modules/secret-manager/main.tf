###############################################################################
# MR. HEALTH Data Platform - Secret Manager Module
# Manages secret definitions (NOT values - those are set manually via CLI)
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
# Secret definitions
# Values are NOT managed by Terraform. Set them via:
#   gcloud secrets versions add SECRET_NAME --data-file=secret.txt
# ---------------------------------------------------------------------------
resource "google_secret_manager_secret" "secrets" {
  for_each = var.secrets

  secret_id = each.value.id
  project   = var.project_id

  replication {
    auto {}
  }

  labels = merge(var.common_labels, {
    secret  = each.key
    purpose = each.value.purpose
  })
}

# ---------------------------------------------------------------------------
# IAM bindings: grant accessor role to service accounts
# ---------------------------------------------------------------------------
resource "google_secret_manager_secret_iam_member" "accessors" {
  for_each = { for binding in local.secret_iam_bindings : "${binding.secret_key}-${binding.member}" => binding }

  project   = var.project_id
  secret_id = google_secret_manager_secret.secrets[each.value.secret_key].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = each.value.member
}

locals {
  secret_iam_bindings = flatten([
    for secret_key, secret in var.secrets : [
      for member in secret.accessor_members : {
        secret_key = secret_key
        member     = member
      }
    ]
  ])
}
