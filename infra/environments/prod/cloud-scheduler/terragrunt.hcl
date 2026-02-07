###############################################################################
# MR. HEALTH Data Platform - Cloud Scheduler (Prod)
# 3 Jobs: pg-extraction, data-generator, daily-transform
###############################################################################

include "root" {
  path = find_in_parent_folders("terragrunt.hcl")
}

include "env" {
  path   = "${get_parent_terragrunt_dir()}/prod/terragrunt.hcl"
  expose = true
}

terraform {
  source = "../../../modules/cloud-scheduler"
}

dependency "cloud_functions" {
  config_path = "../cloud-functions"

  mock_outputs = {
    function_uris = {
      "data-generator"         = "https://data-generator-xxx.a.run.app"
      "pg-reference-extractor" = "https://pg-reference-extractor-xxx.a.run.app"
    }
  }
}

dependency "iam" {
  config_path = "../iam"

  mock_outputs = {
    service_account_emails = {
      csv_processor  = "csv-processor-sa@${include.env.locals.project_id}.iam.gserviceaccount.com"
      data_generator = "data-generator-sa@${include.env.locals.project_id}.iam.gserviceaccount.com"
      pg_extractor   = "pg-extractor-sa@${include.env.locals.project_id}.iam.gserviceaccount.com"
    }
  }
}

inputs = {
  project_id = include.env.locals.project_id
  region     = include.env.locals.region

  # ---------------------------------------------------------------------------
  # Scheduler Jobs
  # ---------------------------------------------------------------------------
  scheduler_jobs = {
    pg-extraction = {
      name             = "pg-reference-extraction"
      schedule         = "0 1 * * *"
      timezone         = "America/Sao_Paulo"
      description      = "Extract reference data from PostgreSQL to GCS daily at 1 AM BRT"
      attempt_deadline = "320s"
      http_method      = "POST"
      target_uri       = dependency.cloud_functions.outputs.function_uris["pg-reference-extractor"]
      oidc_service_account = dependency.iam.outputs.service_account_emails["pg_extractor"]
    }

    data-generator = {
      name             = "continuous-data-generator"
      schedule         = "0 10,12,14,16,18,20,22 * * *"
      timezone         = "America/Sao_Paulo"
      description      = "Generate synthetic sales data throughout business hours"
      attempt_deadline = "320s"
      http_method      = "POST"
      target_uri       = dependency.cloud_functions.outputs.function_uris["data-generator"]
      oidc_service_account = dependency.iam.outputs.service_account_emails["data_generator"]
    }

    daily-transform = {
      name             = "daily-transform-trigger"
      schedule         = "0 2 * * *"
      timezone         = "America/Sao_Paulo"
      description      = "Trigger daily Bronze to Silver to Gold transform pipeline at 2 AM BRT"
      attempt_deadline = "600s"
      http_method      = "POST"
      target_uri       = "https://airflow.mrhealth.internal/api/v1/dags/mrhealth_daily_pipeline/dagRuns"
      oidc_service_account = null
      headers = {
        "Content-Type" = "application/json"
      }
      body = "{\"conf\": {\"triggered_by\": \"cloud-scheduler\"}}"
    }
  }
}
