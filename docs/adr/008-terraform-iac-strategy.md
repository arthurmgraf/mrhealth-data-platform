# ADR-008: Terraform IaC Strategy

## Status
Accepted

## Date
2026-02-18

## Context
The project has a complete Terraform/Terragrunt codebase (`infra/`) with 6 modules (BigQuery, GCS, Cloud Functions, IAM, Secret Manager, Cloud Scheduler). However, all GCP infrastructure was initially deployed imperatively using Python SDK scripts (`scripts/deploy_phase1_infrastructure.py`) and `gcloud` CLI commands.

**Options considered:**
1. **Terraform import** -- Import existing resources into Terraform state, validate with `terraform plan`
2. **Keep Terraform as reference architecture** -- Document that it's IaC-ready but not the active deployment method
3. **Remove Terraform** -- Delete `infra/` to avoid confusion

## Decision
We chose **Option 2: Keep Terraform as reference architecture** because:

1. **Demonstrates IaC proficiency**: The Terraform modules show proper patterns (modular structure, variable-driven, least-privilege IAM, Terragrunt for DRY config)
2. **Ready for production adoption**: A team could `terraform import` existing resources and switch to IaC management
3. **Single-environment reality**: Only `prod` exists (no dev/staging), matching the project's single-server K3s deployment
4. **Workload Identity Federation ready**: IAM module includes WIF pool/provider configuration for GitHub Actions CI/CD

## Implementation Details

### What Terraform covers (IaC-ready)
- BigQuery datasets + tables with partitioning and schema JSON files
- GCS bucket with lifecycle policies
- Cloud Functions deployment configuration
- IAM service accounts + role bindings + WIF
- Cloud Scheduler jobs

### Active deployment method (current)
- `python scripts/deploy_phase1_infrastructure.py` -- BigQuery datasets + tables
- `gcloud functions deploy` -- Cloud Functions (via CI/CD workflow or manual)
- `kubectl apply -f k8s/` -- K3s services (Airflow, Superset, Grafana, Prometheus)

### Migration path to full IaC
```bash
# 1. Initialize Terraform
cd infra/environments/prod && terragrunt run-all init

# 2. Import existing resources
terraform import google_bigquery_dataset.bronze mrhealth_bronze
terraform import google_bigquery_dataset.silver mrhealth_silver
terraform import google_bigquery_dataset.gold mrhealth_gold

# 3. Validate (should show no changes)
terragrunt run-all plan
```

## Consequences
- `infra/` directory is reference code, not actively managing infrastructure
- CI/CD workflow (`deploy-infra.yml`) requires WIF setup before first use
- No risk of Terraform drift since state is not tracked
- Clear documentation prevents confusion about deployment method
