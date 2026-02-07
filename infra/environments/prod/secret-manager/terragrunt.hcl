###############################################################################
# MR. HEALTH Data Platform - Secret Manager (Prod)
# 6 Secrets for PostgreSQL connectivity via SSH tunnel
###############################################################################

include "root" {
  path = find_in_parent_folders("terragrunt.hcl")
}

include "env" {
  path   = "${get_parent_terragrunt_dir()}/prod/terragrunt.hcl"
  expose = true
}

terraform {
  source = "../../../modules/secret-manager"
}

dependency "iam" {
  config_path = "../iam"

  mock_outputs = {
    service_account_emails = {
      pg_extractor = "pg-extractor-sa@${include.env.locals.project_id}.iam.gserviceaccount.com"
      airflow      = "airflow-sa@${include.env.locals.project_id}.iam.gserviceaccount.com"
    }
  }
}

inputs = {
  project_id = include.env.locals.project_id

  common_labels = include.env.locals.common_labels

  # ---------------------------------------------------------------------------
  # Secrets (values are NOT managed by Terraform)
  # Set values via: gcloud secrets versions add SECRET_ID --data-file=secret.txt
  # ---------------------------------------------------------------------------
  secrets = {
    pg_host = {
      id      = "mrhealth-pg-host"
      purpose = "postgresql"
      accessor_members = [
        "serviceAccount:${dependency.iam.outputs.service_account_emails["pg_extractor"]}",
      ]
    }

    pg_user = {
      id      = "mrhealth-pg-user"
      purpose = "postgresql"
      accessor_members = [
        "serviceAccount:${dependency.iam.outputs.service_account_emails["pg_extractor"]}",
      ]
    }

    pg_password = {
      id      = "mrhealth-pg-password"
      purpose = "postgresql"
      accessor_members = [
        "serviceAccount:${dependency.iam.outputs.service_account_emails["pg_extractor"]}",
      ]
    }

    pg_ssh_key = {
      id      = "mrhealth-pg-ssh-key"
      purpose = "ssh-tunnel"
      accessor_members = [
        "serviceAccount:${dependency.iam.outputs.service_account_emails["pg_extractor"]}",
      ]
    }

    pg_ssh_user = {
      id      = "mrhealth-pg-ssh-user"
      purpose = "ssh-tunnel"
      accessor_members = [
        "serviceAccount:${dependency.iam.outputs.service_account_emails["pg_extractor"]}",
      ]
    }

    pg_database = {
      id      = "mrhealth-pg-database"
      purpose = "postgresql"
      accessor_members = [
        "serviceAccount:${dependency.iam.outputs.service_account_emails["pg_extractor"]}",
      ]
    }
  }
}
