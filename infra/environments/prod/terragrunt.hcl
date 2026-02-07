###############################################################################
# MR. HEALTH Data Platform - Prod Environment Configuration
# Project ID is read from the GCP_PROJECT_ID environment variable
###############################################################################

locals {
  environment = "prod"
  project_id  = get_env("GCP_PROJECT_ID")
  region      = "us-central1"

  common_labels = {
    project     = "mrhealth"
    environment = local.environment
    managed_by  = "terraform"
    team        = "data-lakers"
  }
}
