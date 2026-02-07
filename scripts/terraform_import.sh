#!/bin/bash
###############################################################################
# MR. HEALTH Data Platform - Terraform Import Script
# Import existing GCP resources into Terraform state
#
# USAGE:
#   1. cd infra/environments/prod/<module>
#   2. terragrunt init
#   3. bash ../../../../scripts/terraform_import.sh <module>
#
# Run ONCE per module after initial terragrunt init.
# After import, run: terragrunt plan  (should show no changes)
###############################################################################

set -euo pipefail

PROJECT_ID="${PROJECT_ID}"
REGION="us-central1"

usage() {
  echo "Usage: $0 <module>"
  echo ""
  echo "Available modules:"
  echo "  bigquery          Import BigQuery datasets and tables"
  echo "  gcs               Import GCS data lake bucket"
  echo "  cloud-functions   Import Cloud Functions (2nd Gen)"
  echo "  cloud-scheduler   Import Cloud Scheduler jobs"
  echo "  secret-manager    Import Secret Manager secrets"
  echo "  iam               Import service accounts"
  echo "  all               Import all modules (run from each module dir)"
  echo ""
  echo "Example:"
  echo "  cd infra/environments/prod/bigquery"
  echo "  bash ../../../../scripts/terraform_import.sh bigquery"
  exit 1
}

import_bigquery() {
  echo "=== Importing BigQuery Datasets ==="

  terragrunt import \
    'module.bigquery.google_bigquery_dataset.datasets["bronze"]' \
    "projects/${PROJECT_ID}/datasets/mrhealth_bronze" || true

  terragrunt import \
    'module.bigquery.google_bigquery_dataset.datasets["silver"]' \
    "projects/${PROJECT_ID}/datasets/mrhealth_silver" || true

  terragrunt import \
    'module.bigquery.google_bigquery_dataset.datasets["gold"]' \
    "projects/${PROJECT_ID}/datasets/mrhealth_gold" || true

  terragrunt import \
    'module.bigquery.google_bigquery_dataset.datasets["monitoring"]' \
    "projects/${PROJECT_ID}/datasets/mrhealth_monitoring" || true

  echo ""
  echo "=== Importing BigQuery Bronze Tables ==="

  for table in orders order_items products units states countries; do
    terragrunt import \
      "module.bigquery.google_bigquery_table.bronze_tables[\"${table}\"]" \
      "projects/${PROJECT_ID}/datasets/mrhealth_bronze/tables/${table}" || true
  done

  echo ""
  echo "=== Importing BigQuery Monitoring Tables ==="

  for table in data_quality_log pipeline_metrics free_tier_usage; do
    terragrunt import \
      "module.bigquery.google_bigquery_table.monitoring_tables[\"${table}\"]" \
      "projects/${PROJECT_ID}/datasets/mrhealth_monitoring/tables/${table}" || true
  done

  echo "BigQuery import complete."
}

import_gcs() {
  echo "=== Importing GCS Bucket ==="

  terragrunt import \
    'module.gcs.google_storage_bucket.datalake' \
    "mrhealth-datalake-485810" || true

  echo "GCS import complete."
}

import_cloud_functions() {
  echo "=== Importing Cloud Functions (2nd Gen) ==="

  terragrunt import \
    'module.cloud-functions.google_cloudfunctions2_function.functions["csv-processor"]' \
    "projects/${PROJECT_ID}/locations/${REGION}/functions/csv-processor" || true

  terragrunt import \
    'module.cloud-functions.google_cloudfunctions2_function.functions["data-generator"]' \
    "projects/${PROJECT_ID}/locations/${REGION}/functions/data-generator" || true

  terragrunt import \
    'module.cloud-functions.google_cloudfunctions2_function.functions["pg-reference-extractor"]' \
    "projects/${PROJECT_ID}/locations/${REGION}/functions/pg-reference-extractor" || true

  echo "Cloud Functions import complete."
}

import_cloud_scheduler() {
  echo "=== Importing Cloud Scheduler Jobs ==="

  terragrunt import \
    'module.cloud-scheduler.google_cloud_scheduler_job.jobs["pg-extraction"]' \
    "projects/${PROJECT_ID}/locations/${REGION}/jobs/pg-reference-extraction" || true

  terragrunt import \
    'module.cloud-scheduler.google_cloud_scheduler_job.jobs["data-generator"]' \
    "projects/${PROJECT_ID}/locations/${REGION}/jobs/continuous-data-generator" || true

  terragrunt import \
    'module.cloud-scheduler.google_cloud_scheduler_job.jobs["daily-transform"]' \
    "projects/${PROJECT_ID}/locations/${REGION}/jobs/daily-transform-trigger" || true

  echo "Cloud Scheduler import complete."
}

import_secret_manager() {
  echo "=== Importing Secret Manager Secrets ==="

  terragrunt import \
    'module.secret-manager.google_secret_manager_secret.secrets["pg_host"]' \
    "projects/${PROJECT_ID}/secrets/mrhealth-pg-host" || true

  terragrunt import \
    'module.secret-manager.google_secret_manager_secret.secrets["pg_user"]' \
    "projects/${PROJECT_ID}/secrets/mrhealth-pg-user" || true

  terragrunt import \
    'module.secret-manager.google_secret_manager_secret.secrets["pg_password"]' \
    "projects/${PROJECT_ID}/secrets/mrhealth-pg-password" || true

  terragrunt import \
    'module.secret-manager.google_secret_manager_secret.secrets["pg_ssh_key"]' \
    "projects/${PROJECT_ID}/secrets/mrhealth-pg-ssh-key" || true

  terragrunt import \
    'module.secret-manager.google_secret_manager_secret.secrets["pg_ssh_user"]' \
    "projects/${PROJECT_ID}/secrets/mrhealth-pg-ssh-user" || true

  terragrunt import \
    'module.secret-manager.google_secret_manager_secret.secrets["pg_database"]' \
    "projects/${PROJECT_ID}/secrets/mrhealth-pg-database" || true

  echo "Secret Manager import complete."
}

import_iam() {
  echo "=== Importing Service Accounts ==="

  local sa_map=(
    "csv_processor:csv-processor-sa"
    "data_generator:data-generator-sa"
    "pg_extractor:pg-extractor-sa"
    "airflow:airflow-sa"
    "grafana:grafana-sa"
    "github_ci:github-ci-sa"
    "terraform:terraform-sa"
  )

  for entry in "${sa_map[@]}"; do
    local key="${entry%%:*}"
    local account_id="${entry##*:}"
    terragrunt import \
      "module.iam.google_service_account.accounts[\"${key}\"]" \
      "projects/${PROJECT_ID}/serviceAccounts/${account_id}@${PROJECT_ID}.iam.gserviceaccount.com" || true
  done

  echo ""
  echo "=== Importing Workload Identity Pool ==="

  terragrunt import \
    'module.iam.google_iam_workload_identity_pool.github[0]' \
    "projects/${PROJECT_ID}/locations/global/workloadIdentityPools/github-actions-pool" || true

  terragrunt import \
    'module.iam.google_iam_workload_identity_pool_provider.github[0]' \
    "projects/${PROJECT_ID}/locations/global/workloadIdentityPools/github-actions-pool/providers/github-actions-provider" || true

  echo "IAM import complete."
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if [ $# -lt 1 ]; then
  usage
fi

MODULE="$1"

case "${MODULE}" in
  bigquery)         import_bigquery ;;
  gcs)              import_gcs ;;
  cloud-functions)  import_cloud_functions ;;
  cloud-scheduler)  import_cloud_scheduler ;;
  secret-manager)   import_secret_manager ;;
  iam)              import_iam ;;
  all)
    echo "============================================="
    echo "  Importing ALL modules"
    echo "============================================="
    echo ""
    echo "NOTE: You must run this from each module directory separately."
    echo "The 'all' option is for documentation purposes."
    echo ""
    echo "Run in this order:"
    echo "  1. cd infra/environments/prod/iam && terragrunt init && bash ../../../../scripts/terraform_import.sh iam"
    echo "  2. cd ../gcs && terragrunt init && bash ../../../../scripts/terraform_import.sh gcs"
    echo "  3. cd ../bigquery && terragrunt init && bash ../../../../scripts/terraform_import.sh bigquery"
    echo "  4. cd ../secret-manager && terragrunt init && bash ../../../../scripts/terraform_import.sh secret-manager"
    echo "  5. cd ../cloud-functions && terragrunt init && bash ../../../../scripts/terraform_import.sh cloud-functions"
    echo "  6. cd ../cloud-scheduler && terragrunt init && bash ../../../../scripts/terraform_import.sh cloud-scheduler"
    ;;
  *)
    echo "ERROR: Unknown module '${MODULE}'"
    usage
    ;;
esac

echo ""
echo "Done. Run 'terragrunt plan' to verify no drift."
