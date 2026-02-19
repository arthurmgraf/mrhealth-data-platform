###############################################################################
# MR. HEALTH Data Platform - IAM Module
# Service accounts, role bindings, and Workload Identity Federation
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
# Service Accounts
# ---------------------------------------------------------------------------
resource "google_service_account" "accounts" {
  for_each = var.service_accounts

  account_id   = each.value.account_id
  display_name = each.value.display_name
  description  = each.value.description
  project      = var.project_id
}

# ---------------------------------------------------------------------------
# Project-level IAM bindings (roles per service account)
# ---------------------------------------------------------------------------
resource "google_project_iam_member" "bindings" {
  for_each = { for binding in local.iam_bindings : "${binding.account_key}-${binding.role}" => binding }

  project = var.project_id
  role    = each.value.role
  member  = "serviceAccount:${google_service_account.accounts[each.value.account_key].email}"
}

locals {
  iam_bindings = flatten([
    for account_key, account in var.service_accounts : [
      for role in account.roles : {
        account_key = account_key
        role        = role
      }
    ]
  ])
}

# ---------------------------------------------------------------------------
# Workload Identity Federation (for GitHub Actions CI/CD)
# ---------------------------------------------------------------------------
resource "google_iam_workload_identity_pool" "github" {
  count = var.wif_config != null ? 1 : 0

  workload_identity_pool_id = var.wif_config.pool_id
  display_name              = var.wif_config.pool_display_name
  description               = var.wif_config.pool_description
  project                   = var.project_id
}

resource "google_iam_workload_identity_pool_provider" "github" {
  count = var.wif_config != null ? 1 : 0

  workload_identity_pool_id          = google_iam_workload_identity_pool.github[0].workload_identity_pool_id
  workload_identity_pool_provider_id = var.wif_config.provider_id
  display_name                       = var.wif_config.provider_display_name
  project                            = var.project_id

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.actor"      = "assertion.actor"
    "attribute.repository" = "assertion.repository"
  }

  attribute_condition = "assertion.repository == '${var.wif_config.github_repo}'"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# Allow GitHub Actions SA to impersonate via WIF
resource "google_service_account_iam_member" "wif_binding" {
  count = var.wif_config != null ? 1 : 0

  service_account_id = google_service_account.accounts[var.wif_config.service_account_key].name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github[0].name}/attribute.repository/${var.wif_config.github_repo}"
}
