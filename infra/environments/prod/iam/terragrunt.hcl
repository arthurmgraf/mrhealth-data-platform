###############################################################################
# MR. HEALTH Data Platform - IAM (Prod)
# 7 Service Accounts + Workload Identity Federation for GitHub Actions
###############################################################################

include "root" {
  path = find_in_parent_folders("terragrunt.hcl")
}

include "env" {
  path   = "${get_parent_terragrunt_dir()}/prod/terragrunt.hcl"
  expose = true
}

terraform {
  source = "../../../modules/iam"
}

inputs = {
  project_id = include.env.locals.project_id

  # ---------------------------------------------------------------------------
  # Service Accounts (7)
  # ---------------------------------------------------------------------------
  service_accounts = {
    csv_processor = {
      account_id   = "csv-processor-sa"
      display_name = "CSV Processor Cloud Function"
      description  = "Service account for the csv-processor Cloud Function (event-driven CSV ingestion)"
      roles = [
        "roles/bigquery.dataEditor",
        "roles/bigquery.jobUser",
        "roles/storage.objectViewer",
        "roles/eventarc.eventReceiver",
        "roles/run.invoker",
      ]
    }

    data_generator = {
      account_id   = "data-generator-sa"
      display_name = "Data Generator Cloud Function"
      description  = "Service account for the data-generator Cloud Function (synthetic data)"
      roles = [
        "roles/storage.objectCreator",
        "roles/run.invoker",
      ]
    }

    pg_extractor = {
      account_id   = "pg-extractor-sa"
      display_name = "PostgreSQL Reference Extractor"
      description  = "Service account for pg-reference-extractor Cloud Function (SSH tunnel to K3s PostgreSQL)"
      roles = [
        "roles/storage.objectCreator",
        "roles/storage.objectViewer",
        "roles/secretmanager.secretAccessor",
        "roles/run.invoker",
      ]
    }

    airflow = {
      account_id   = "airflow-sa"
      display_name = "Airflow Orchestrator"
      description  = "Service account for Apache Airflow DAGs (Bronze to Gold pipeline)"
      roles = [
        "roles/bigquery.dataEditor",
        "roles/bigquery.jobUser",
        "roles/storage.objectViewer",
        "roles/cloudfunctions.invoker",
      ]
    }

    grafana = {
      account_id   = "grafana-sa"
      display_name = "Grafana Monitoring"
      description  = "Service account for Grafana dashboards (read-only BigQuery access)"
      roles = [
        "roles/bigquery.dataViewer",
        "roles/bigquery.jobUser",
      ]
    }

    github_ci = {
      account_id   = "github-ci-sa"
      display_name = "GitHub Actions CI/CD"
      description  = "Service account for GitHub Actions deployments via Workload Identity Federation"
      roles = [
        "roles/cloudfunctions.developer",
        "roles/storage.objectAdmin",
        "roles/iam.serviceAccountUser",
        "roles/run.admin",
      ]
    }

    terraform = {
      account_id   = "terraform-sa"
      display_name = "Terraform Infrastructure"
      description  = "Service account for Terraform/Terragrunt infrastructure management"
      roles = [
        "roles/editor",
        "roles/iam.securityAdmin",
        "roles/resourcemanager.projectIamAdmin",
      ]
    }
  }

  # ---------------------------------------------------------------------------
  # Workload Identity Federation (GitHub Actions)
  # ---------------------------------------------------------------------------
  wif_config = {
    pool_id               = "github-actions-pool"
    pool_display_name     = "GitHub Actions"
    pool_description      = "WIF pool for GitHub Actions CI/CD pipelines"
    provider_id           = "github-actions-provider"
    provider_display_name = "GitHub Actions OIDC"
    github_repo           = "arthurmgraf/mrhealth-data-platform"
    service_account_key   = "github_ci"
  }
}
