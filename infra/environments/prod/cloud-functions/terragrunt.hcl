###############################################################################
# MR. HEALTH Data Platform - Cloud Functions (Prod)
# 3 Functions: csv-processor, data-generator, pg-reference-extractor
###############################################################################

include "root" {
  path = find_in_parent_folders("terragrunt.hcl")
}

include "env" {
  path   = "${get_parent_terragrunt_dir()}/prod/terragrunt.hcl"
  expose = true
}

terraform {
  source = "../../../modules/cloud-functions"
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

dependency "gcs" {
  config_path = "../gcs"

  mock_outputs = {
    bucket_name = "mrhealth-datalake-${include.env.locals.project_id}"
  }
}

inputs = {
  project_id = include.env.locals.project_id
  region     = include.env.locals.region

  common_labels = include.env.locals.common_labels

  # ---------------------------------------------------------------------------
  # Cloud Functions (2nd Gen)
  # ---------------------------------------------------------------------------
  functions = {
    csv-processor = {
      name                  = "csv-processor"
      runtime               = "python311"
      entry_point           = "process_csv"
      memory                = "256Mi"
      timeout_seconds       = 300
      max_instances         = 10
      min_instances         = 0
      source_bucket         = dependency.gcs.outputs.bucket_name
      source_object         = "cloud-functions/csv-processor.zip"
      service_account_email = dependency.iam.outputs.service_account_emails["csv_processor"]

      environment_variables = {
        GCP_PROJECT_ID  = include.env.locals.project_id
        GCS_BUCKET_NAME = dependency.gcs.outputs.bucket_name
        BQ_DATASET      = "mrhealth_bronze"
        ENVIRONMENT     = include.env.locals.environment
      }

      secret_env_vars = []

      event_trigger = {
        event_type   = "google.cloud.storage.object.v1.finalized"
        retry_policy = "RETRY_POLICY_RETRY"
        event_filters = [
          {
            attribute = "bucket"
            value     = dependency.gcs.outputs.bucket_name
          }
        ]
      }
    }

    data-generator = {
      name                  = "data-generator"
      runtime               = "python311"
      entry_point           = "generate_data"
      memory                = "256Mi"
      timeout_seconds       = 300
      max_instances         = 1
      min_instances         = 0
      source_bucket         = dependency.gcs.outputs.bucket_name
      source_object         = "cloud-functions/data-generator.zip"
      service_account_email = dependency.iam.outputs.service_account_emails["data_generator"]

      environment_variables = {
        GCP_PROJECT_ID  = include.env.locals.project_id
        GCS_BUCKET_NAME = dependency.gcs.outputs.bucket_name
        ENVIRONMENT     = include.env.locals.environment
      }

      secret_env_vars = []
      event_trigger   = null
    }

    pg-reference-extractor = {
      name                  = "pg-reference-extractor"
      runtime               = "python311"
      entry_point           = "extract_references"
      memory                = "256Mi"
      timeout_seconds       = 300
      max_instances         = 1
      min_instances         = 0
      source_bucket         = dependency.gcs.outputs.bucket_name
      source_object         = "cloud-functions/pg-reference-extractor.zip"
      service_account_email = dependency.iam.outputs.service_account_emails["pg_extractor"]

      environment_variables = {
        GCP_PROJECT_ID  = include.env.locals.project_id
        GCS_BUCKET_NAME = dependency.gcs.outputs.bucket_name
        PG_DATABASE     = "mrhealth"
        ENVIRONMENT     = include.env.locals.environment
      }

      secret_env_vars = [
        {
          env_var     = "PG_HOST"
          secret_name = "mrhealth-pg-host"
          version     = "latest"
        },
        {
          env_var     = "PG_USER"
          secret_name = "mrhealth-pg-user"
          version     = "latest"
        },
        {
          env_var     = "PG_PASSWORD"
          secret_name = "mrhealth-pg-password"
          version     = "latest"
        },
        {
          env_var     = "PG_SSH_KEY"
          secret_name = "mrhealth-pg-ssh-key"
          version     = "latest"
        },
        {
          env_var     = "PG_SSH_USER"
          secret_name = "mrhealth-pg-ssh-user"
          version     = "latest"
        }
      ]

      event_trigger = null
    }
  }
}
