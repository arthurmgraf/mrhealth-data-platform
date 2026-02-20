# MR. HEALTH Data Platform - Production IAM Configuration
# ========================================================
# Granular IAM roles following least-privilege principle (ADR-009).
# Each Cloud Function gets only the permissions it needs.

service_accounts = {
  csv_processor = {
    display_name = "CSV Processor Cloud Function"
    roles = [
      "roles/bigquery.dataEditor",       # Write to Bronze tables
      "roles/bigquery.jobUser",           # Run BigQuery jobs
      "roles/storage.objectViewer",       # Read CSV files from GCS
      "roles/storage.objectCreator",      # Write quarantine files
    ]
  }

  data_generator = {
    display_name = "Data Generator Cloud Function"
    roles = [
      "roles/storage.objectCreator",      # Write generated CSVs to GCS
    ]
  }

  pg_reference_extractor = {
    display_name = "PG Reference Extractor Cloud Function"
    roles = [
      "roles/storage.objectCreator",      # Write reference CSVs to GCS
      "roles/secretmanager.secretAccessor", # Access SSH/PG credentials
    ]
  }
}
