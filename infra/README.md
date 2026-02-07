# MR. HEALTH Data Platform - Infrastructure as Code

Terraform modules + Terragrunt environment configuration for the MR. HEALTH Data Platform on GCP.

## Architecture

```text
infra/
├── modules/                          # Reusable Terraform modules
│   ├── bigquery/                     # Datasets + tables + JSON schemas
│   │   └── schemas/                  # 9 JSON schema files
│   ├── gcs/                          # Data lake bucket + lifecycle rules
│   ├── cloud-functions/              # 3 Cloud Functions (2nd Gen)
│   ├── cloud-scheduler/              # 3 Scheduler jobs (cron triggers)
│   ├── secret-manager/               # 6 secrets (PostgreSQL connectivity)
│   └── iam/                          # 7 service accounts + WIF
│
├── environments/
│   ├── terragrunt.hcl                # Root config (GCS backend, provider)
│   └── prod/                         # Production environment
│       ├── terragrunt.hcl            # Shared inputs (project, labels)
│       ├── bigquery/terragrunt.hcl   # 4 datasets, 6+3 tables
│       ├── gcs/terragrunt.hcl        # Data lake bucket
│       ├── cloud-functions/          # 3 Cloud Functions
│       ├── cloud-scheduler/          # 3 Scheduler jobs
│       ├── secret-manager/           # 6 secrets
│       └── iam/                      # 7 SAs + WIF
│
└── README.md                         # This file
```

## GCP Project

| Property | Value |
|----------|-------|
| Project ID | `$GCP_PROJECT_ID` (set via environment variable) |
| Region | `us-central1` |
| Environment | `prod` (single environment) |
| Terraform State | `gs://mrhealth-terraform-state` |

## Resources Managed

| Module | Resource Type | Count | Details |
|--------|--------------|-------|---------|
| **bigquery** | Datasets | 4 | bronze, silver, gold, monitoring |
| **bigquery** | Bronze Tables | 6 | orders, order_items, products, units, states, countries |
| **bigquery** | Monitoring Tables | 3 | data_quality_log, pipeline_metrics, free_tier_usage |
| **gcs** | Buckets | 1 | mrhealth-datalake-485810 |
| **cloud-functions** | Functions (2nd Gen) | 3 | csv-processor, data-generator, pg-reference-extractor |
| **cloud-scheduler** | Jobs | 3 | pg-extraction, data-generator, daily-transform |
| **secret-manager** | Secrets | 6 | PostgreSQL host, user, password, SSH key, SSH user, database |
| **iam** | Service Accounts | 7 | csv-processor, data-generator, pg-extractor, airflow, grafana, github-ci, terraform |
| **iam** | WIF Pool | 1 | GitHub Actions OIDC federation |

## Prerequisites

1. **Terraform** >= 1.5
2. **Terragrunt** >= 0.50
3. **gcloud CLI** authenticated with sufficient permissions
4. **GCS state bucket** must exist:
   ```bash
   gsutil mb -p $GCP_PROJECT_ID -l us-central1 gs://mrhealth-terraform-state
   ```

## Initial Setup (Import Existing Resources)

All resources already exist in GCP. We use `terraform import` to bring them under IaC management.

### Step 1: Initialize and Import (one-time)

Run imports in dependency order:

```bash
# 1. IAM (no dependencies)
cd infra/environments/prod/iam
terragrunt init
bash ../../../../scripts/terraform_import.sh iam

# 2. GCS (no dependencies)
cd ../gcs
terragrunt init
bash ../../../../scripts/terraform_import.sh gcs

# 3. BigQuery (no dependencies)
cd ../bigquery
terragrunt init
bash ../../../../scripts/terraform_import.sh bigquery

# 4. Secret Manager (depends on IAM)
cd ../secret-manager
terragrunt init
bash ../../../../scripts/terraform_import.sh secret-manager

# 5. Cloud Functions (depends on IAM + GCS)
cd ../cloud-functions
terragrunt init
bash ../../../../scripts/terraform_import.sh cloud-functions

# 6. Cloud Scheduler (depends on Cloud Functions + IAM)
cd ../cloud-scheduler
terragrunt init
bash ../../../../scripts/terraform_import.sh cloud-scheduler
```

### Step 2: Verify No Drift

After importing, verify Terraform sees no changes:

```bash
cd infra/environments/prod/bigquery
terragrunt plan
# Expected: "No changes. Your infrastructure matches the configuration."
```

Repeat for each module. Minor drift is expected (e.g., labels, descriptions) -- review and apply as needed.

## Day-to-Day Operations

### Plan Changes

```bash
# Plan a specific module
cd infra/environments/prod/bigquery
terragrunt plan

# Plan all modules
cd infra/environments/prod
terragrunt run-all plan
```

### Apply Changes

```bash
# Apply a specific module
cd infra/environments/prod/bigquery
terragrunt apply

# Apply all modules (respects dependency order)
cd infra/environments/prod
terragrunt run-all apply
```

### View State

```bash
cd infra/environments/prod/bigquery
terragrunt state list
terragrunt state show 'google_bigquery_dataset.datasets["bronze"]'
```

## Module Dependency Graph

```text
iam ──────────────────┐
  │                    │
  ├──► secret-manager  │
  │                    │
  ├──► cloud-functions ◄── gcs
  │         │
  └──► cloud-scheduler ◄── cloud-functions

bigquery (independent)
gcs (independent)
```

## Design Decisions

1. **Terragrunt over plain Terraform**: DRY configuration, automatic backend generation, dependency management between modules.

2. **for_each over count**: Named resource instances for stable state addresses (e.g., `datasets["bronze"]` instead of `datasets[0]`).

3. **JSON schemas in files**: Keeps HCL clean, schemas can be validated independently, and changes are easy to diff in code review.

4. **delete_contents_on_destroy = false**: Safety net to prevent accidental data loss on `terraform destroy`.

5. **Secret values not in Terraform**: Only secret definitions (metadata) are managed. Values are set via `gcloud secrets versions add` to avoid storing secrets in state.

6. **Workload Identity Federation**: Keyless authentication for GitHub Actions CI/CD. No service account keys to rotate.

## Security Notes

- Service accounts follow least-privilege principle
- Secret values are NEVER stored in Terraform state or code
- WIF eliminates the need for long-lived service account keys
- Uniform bucket-level access on GCS (no ACLs)
- BigQuery tables have `deletion_protection = false` only for Terraform management; data protection is via `delete_contents_on_destroy = false` on datasets
