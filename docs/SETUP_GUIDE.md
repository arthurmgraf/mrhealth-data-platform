# MR. HEALTH Data Platform - Setup Guide

> Complete step-by-step replication guide for deploying the enterprise-grade data warehouse on GCP Free Tier with K3s orchestration.

---

## Prerequisites

### Required Software

- **GCP Account**: Free tier with billing enabled (no charges expected)
- **Python 3.11+**: `python --version` should show 3.11 or higher
- **gcloud CLI**: Install from [cloud.google.com/sdk/docs/install](https://cloud.google.com/sdk/docs/install)
- **K3s Cluster**: Single-node or multi-node cluster (installation: [k3s.io](https://k3s.io))
- **kubectl**: Kubernetes CLI (`curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"`)
- **Git**: For cloning the repository

### Required Knowledge

- Basic Linux command line
- Python virtual environments
- Kubernetes basics (pods, services, namespaces)
- SQL fundamentals
- GCP console navigation

---

## 1. GCP Setup

### 1.1 Create GCP Project

```bash
# Login to GCP
gcloud auth login

# Create new project (or use existing)
export GCP_PROJECT_ID="mrhealth-platform-$(date +%s)"
gcloud projects create $GCP_PROJECT_ID --name="MR. HEALTH Data Platform"

# Set as default project
gcloud config set project $GCP_PROJECT_ID

# Link billing account (REQUIRED even for free tier)
# List billing accounts
gcloud billing accounts list

# Link billing (replace BILLING_ACCOUNT_ID)
gcloud billing projects link $GCP_PROJECT_ID --billing-account=BILLING_ACCOUNT_ID
```

### 1.2 Enable Required APIs

```bash
# Enable all required GCP APIs
gcloud services enable \
  bigquery.googleapis.com \
  cloudfunctions.googleapis.com \
  cloudbuild.googleapis.com \
  storage.googleapis.com \
  eventarc.googleapis.com \
  run.googleapis.com \
  pubsub.googleapis.com \
  cloudscheduler.googleapis.com \
  logging.googleapis.com \
  monitoring.googleapis.com

# Verify APIs are enabled
gcloud services list --enabled
```

### 1.3 Authenticate for Application Default Credentials

```bash
# Create ADC credentials (used by scripts)
gcloud auth application-default login

# Create service account for K3s deployments (optional but recommended)
gcloud iam service-accounts create mrhealth-k3s \
  --display-name="MR. HEALTH K3s Service Account"

# Grant necessary permissions
gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
  --member="serviceAccount:mrhealth-k3s@${GCP_PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataEditor"

gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
  --member="serviceAccount:mrhealth-k3s@${GCP_PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/bigquery.jobUser"

gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
  --member="serviceAccount:mrhealth-k3s@${GCP_PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/storage.objectViewer"

# Download service account key
gcloud iam service-accounts keys create keys/gcp.json \
  --iam-account=mrhealth-k3s@${GCP_PROJECT_ID}.iam.gserviceaccount.com
```

---

## 2. Environment Configuration

### 2.1 Clone Repository

```bash
# Clone the repository
git clone <repository-url> mrhealth-platform
cd mrhealth-platform

# Create keys directory
mkdir -p keys
chmod 700 keys
```

### 2.2 Python Virtual Environment

```bash
# Create virtual environment
python3.11 -m venv venv

# Activate virtual environment
source venv/bin/activate  # Linux/Mac
# OR
venv\Scripts\activate     # Windows

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
```

### 2.3 Environment Variables

```bash
# Create .env file (DO NOT commit this file)
cat > .env << EOF
GCP_PROJECT_ID=$GCP_PROJECT_ID
GCS_BUCKET_NAME=mrhealth-datalake-${GCP_PROJECT_ID}
GCP_REGION=us-central1
PG_HOST=<your-k3s-node-ip>
PG_SSH_USER=<your-ssh-user>
GOOGLE_APPLICATION_CREDENTIALS=$(pwd)/keys/gcp.json
EOF

# Load environment variables
source .env  # Linux/Mac
# OR manually set on Windows
```

### 2.4 Update Configuration File

```bash
# Update config/project_config.yaml with your values
# Replace ${GCP_PROJECT_ID} with actual project ID
# Replace ${GCS_BUCKET_NAME} with actual bucket name

# Use Python script to replace placeholders
python3 << 'PYTHON_SCRIPT'
import os
import yaml

config_path = 'config/project_config.yaml'
with open(config_path, 'r') as f:
    content = f.read()

# Replace placeholders
content = content.replace('${GCP_PROJECT_ID}', os.environ['GCP_PROJECT_ID'])
content = content.replace('${GCS_BUCKET_NAME}', os.environ['GCS_BUCKET_NAME'])
content = content.replace('${GCP_REGION}', os.environ.get('GCP_REGION', 'us-central1'))

with open(config_path, 'w') as f:
    f.write(content)

print("✓ Configuration file updated")
PYTHON_SCRIPT
```

### 2.5 Create GCS Bucket

```bash
# Create data lake bucket
gsutil mb -p $GCP_PROJECT_ID -c STANDARD -l $GCP_REGION gs://$GCS_BUCKET_NAME

# Create folder structure
gsutil -m mkdir -p \
  gs://$GCS_BUCKET_NAME/raw/sales/ \
  gs://$GCS_BUCKET_NAME/raw/reference_data/ \
  gs://$GCS_BUCKET_NAME/processed/

# Verify bucket creation
gsutil ls -p $GCP_PROJECT_ID
```

---

## 3. BigQuery Infrastructure

### 3.1 Deploy Datasets and Tables

```bash
# Deploy Bronze, Silver, Gold, and Monitoring datasets + tables
python scripts/deploy_phase1_infrastructure.py

# Expected output:
# ✓ Dataset mrhealth_bronze created
# ✓ Dataset mrhealth_silver created
# ✓ Dataset mrhealth_gold created
# ✓ Dataset mrhealth_monitoring created
# ✓ Bronze tables created (6 tables)
# ✓ Silver tables created (3 tables)
# ✓ Gold tables created (13 tables)
# ✓ Monitoring tables created (2 tables)
# Total: 24 tables across 4 datasets
```

### 3.2 Verify BigQuery Setup

```bash
# List all datasets
bq ls --project_id=$GCP_PROJECT_ID

# Check tables in bronze dataset
bq ls --project_id=$GCP_PROJECT_ID mrhealth_bronze

# Expected tables: sales, product, unit, state, country, order_items
```

---

## 4. Data Generation and Ingestion

### 4.1 Generate Fake Sales Data

```bash
# Generate 30 days of synthetic sales data (50 units, ~100 CSVs/day)
python scripts/generate_fake_sales.py

# Expected output:
# Generated 3000 sales CSV files in data/fake/sales/
# Date range: 2026-01-20 to 2026-02-18
# ~100 files per day across 50 units
```

### 4.2 Upload Data to GCS

```bash
# Upload generated CSVs to GCS
python scripts/upload_fake_data_to_gcs.py

# Expected output:
# Uploaded 3000 files to gs://<bucket>/raw/sales/
# Trigger: Eventarc will invoke csv-processor automatically
```

---

## 5. Cloud Functions Deployment

### 5.1 Deploy CSV Processor (Event-Driven Ingestion)

```bash
cd cloud_functions/csv_processor

# Deploy with Eventarc trigger for GCS object finalization
gcloud functions deploy csv-processor \
  --gen2 \
  --runtime=python311 \
  --region=$GCP_REGION \
  --source=. \
  --entry-point=process_csv \
  --trigger-event-filters="type=google.cloud.storage.object.v1.finalized" \
  --trigger-event-filters="bucket=$GCS_BUCKET_NAME" \
  --trigger-event-filters-path-pattern="raw/sales/**" \
  --memory=512MB \
  --timeout=540s \
  --set-env-vars=GCP_PROJECT_ID=$GCP_PROJECT_ID

cd ../..

# Verify deployment
gcloud functions describe csv-processor --gen2 --region=$GCP_REGION
```

### 5.2 Deploy Data Generator (HTTP Trigger)

```bash
cd cloud_functions/data_generator

# Deploy HTTP-triggered function for scheduled data generation
gcloud functions deploy data-generator \
  --gen2 \
  --runtime=python311 \
  --region=$GCP_REGION \
  --source=. \
  --entry-point=generate_data \
  --trigger-http \
  --allow-unauthenticated \
  --memory=256MB \
  --timeout=300s \
  --set-env-vars=GCP_PROJECT_ID=$GCP_PROJECT_ID,GCS_BUCKET_NAME=$GCS_BUCKET_NAME

cd ../..

# Get function URL
gcloud functions describe data-generator --gen2 --region=$GCP_REGION --format="value(serviceConfig.uri)"
```

### 5.3 Deploy PostgreSQL Reference Extractor

```bash
cd cloud_functions/pg_reference_extractor

# Deploy HTTP-triggered function for reference data extraction
gcloud functions deploy pg-reference-extractor \
  --gen2 \
  --runtime=python311 \
  --region=$GCP_REGION \
  --source=. \
  --entry-point=extract_reference_data \
  --trigger-http \
  --allow-unauthenticated \
  --memory=512MB \
  --timeout=540s \
  --set-env-vars=GCP_PROJECT_ID=$GCP_PROJECT_ID,GCS_BUCKET_NAME=$GCS_BUCKET_NAME,PG_HOST=$PG_HOST

cd ../..

# Note: This function requires SSH access to K3s PostgreSQL
# Configure SSH keys and network access before triggering
```

---

## 6. Transformation Layers

### 6.1 Build Silver Layer

```bash
# Execute Silver transformations (Bronze → Silver)
python scripts/build_silver_layer.py

# Expected output:
# ✓ Executed: sql/silver/01_create_silver_sales.sql
# ✓ Executed: sql/silver/02_create_silver_order_items.sql
# ✓ Executed: sql/silver/03_create_silver_reference_data.sql
# Silver layer built successfully
```

### 6.2 Build Gold Layer (Star Schema)

```bash
# Execute Gold dimensional model (Silver → Gold)
python scripts/build_gold_layer.py

# Expected output:
# ✓ Created: dim_date, dim_product, dim_unit, dim_geography
# ✓ Created: fact_sales, fact_order_items
# ✓ Created: bridge tables (product_geography, unit_time)
# Gold layer built successfully (Kimball Star Schema)
```

### 6.3 Build Aggregation Tables

```bash
# Execute KPI aggregations
python scripts/build_aggregations.py

# Expected output:
# ✓ Created: agg_daily_sales, agg_product_performance, agg_unit_performance
# Aggregation tables built successfully
```

---

## 7. K3s Services Deployment

### 7.1 Update Secrets

```bash
# Edit k8s/secrets.yaml and replace placeholder passwords
# DO NOT commit real passwords to git

# Generate random passwords
POSTGRES_PASSWORD=$(openssl rand -base64 16)
AIRFLOW_POSTGRES_PASSWORD=$(openssl rand -base64 16)
SUPERSET_POSTGRES_PASSWORD=$(openssl rand -base64 16)
GRAFANA_ADMIN_PASSWORD=$(openssl rand -base64 16)

# Update secrets.yaml with real values (manual edit or script)
# Example: sed replacement (Linux/Mac)
sed -i "s/your-postgres-password-here/$POSTGRES_PASSWORD/g" k8s/secrets.yaml
sed -i "s/your-airflow-postgres-password-here/$AIRFLOW_POSTGRES_PASSWORD/g" k8s/secrets.yaml
sed -i "s/your-superset-postgres-password-here/$SUPERSET_POSTGRES_PASSWORD/g" k8s/secrets.yaml
sed -i "s/your-grafana-admin-password-here/$GRAFANA_ADMIN_PASSWORD/g" k8s/secrets.yaml

# Also update GCP service account JSON (base64 encoded)
base64 -w 0 keys/gcp.json > /tmp/gcp_json_base64.txt
# Replace gcp-service-account-json value in secrets.yaml with this content
```

### 7.2 Create Namespace

```bash
# Create dedicated namespace
kubectl create namespace mrhealth-db

# Set as default namespace (optional)
kubectl config set-context --current --namespace=mrhealth-db
```

### 7.3 Deploy PostgreSQL

```bash
# Apply secrets first
kubectl apply -f k8s/secrets.yaml -n mrhealth-db

# Deploy PostgreSQL (PVC + Deployment + Service)
kubectl apply -f k8s/postgresql/ -n mrhealth-db

# Wait for pod to be ready
kubectl wait --for=condition=ready pod -l app=postgresql -n mrhealth-db --timeout=300s

# Verify
kubectl get pods -n mrhealth-db
kubectl get svc -n mrhealth-db

# Expected: postgresql-0 pod running, NodePort service on port 30432
```

### 7.4 Seed PostgreSQL with Reference Data

```bash
# Seed reference tables: produto, unidade, estado, pais
python scripts/seed_postgresql.py

# Expected output:
# ✓ Created tables: produto, unidade, estado, pais
# ✓ Inserted 50 units, 30 products, 27 states, 1 country
# PostgreSQL seeded successfully
```

### 7.5 Deploy Airflow

```bash
# Deploy Airflow (PVC + ConfigMap + Deployment + Service for webserver and scheduler)
kubectl apply -f k8s/airflow/ -n mrhealth-db

# Wait for pods to be ready
kubectl wait --for=condition=ready pod -l app=airflow-webserver -n mrhealth-db --timeout=600s
kubectl wait --for=condition=ready pod -l app=airflow-scheduler -n mrhealth-db --timeout=600s

# Verify
kubectl get pods -n mrhealth-db | grep airflow

# Expected: airflow-webserver and airflow-scheduler pods running
# Access: http://<k3s-node-ip>:30180 (admin/admin)
```

### 7.6 Deploy Superset

```bash
# Deploy Superset (PVC + Init Job + Deployment + Service)
kubectl apply -f k8s/superset/ -n mrhealth-db

# Wait for init job to complete
kubectl wait --for=condition=complete job/superset-init-db -n mrhealth-db --timeout=600s

# Wait for pod to be ready
kubectl wait --for=condition=ready pod -l app=superset -n mrhealth-db --timeout=300s

# Verify
kubectl get pods -n mrhealth-db | grep superset

# Expected: superset pod running
# Access: http://<k3s-node-ip>:30188 (admin/admin)
```

### 7.7 Deploy Grafana and Prometheus

```bash
# Deploy Prometheus stack
kubectl apply -f k8s/prometheus/ -n mrhealth-db

# Deploy Grafana
kubectl apply -f k8s/grafana/ -n mrhealth-db

# Wait for pods to be ready
kubectl wait --for=condition=ready pod -l app=prometheus -n mrhealth-db --timeout=300s
kubectl wait --for=condition=ready pod -l app=grafana -n mrhealth-db --timeout=300s

# Verify
kubectl get pods -n mrhealth-db | grep -E 'prometheus|grafana'

# Expected: prometheus, node-exporter, statsd-exporter, grafana pods running
# Grafana Access: http://<k3s-node-ip>:30300 (admin/<password-from-secrets>)
```

### 7.8 Apply Network Policies

```bash
# Apply default deny + explicit allow rules
kubectl apply -f k8s/network-policy.yaml -n mrhealth-db

# Verify
kubectl get networkpolicies -n mrhealth-db
```

---

## 8. Airflow Configuration

### 8.1 Access Airflow Web UI

```bash
# Get K3s node IP
kubectl get nodes -o wide

# Access Airflow: http://<node-ip>:30180
# Default credentials: admin / admin
```

### 8.2 Verify DAGs

```bash
# List DAGs via kubectl exec
kubectl exec -it deployment/airflow-scheduler -n mrhealth-db -- airflow dags list

# Expected 5 DAGs:
# - mrhealth_daily_pipeline
# - mrhealth_data_quality
# - mrhealth_data_retention
# - mrhealth_backfill_monitor
# - mrhealth_reference_refresh
```

### 8.3 Trigger First Pipeline Run

```bash
# Trigger daily pipeline manually
kubectl exec -it deployment/airflow-scheduler -n mrhealth-db -- \
  airflow dags trigger mrhealth_daily_pipeline

# Monitor execution in Web UI or via CLI
kubectl exec -it deployment/airflow-scheduler -n mrhealth-db -- \
  airflow dags list-runs -d mrhealth_daily_pipeline
```

### 8.4 Enable All DAGs

```bash
# Unpause all DAGs
kubectl exec -it deployment/airflow-scheduler -n mrhealth-db -- \
  airflow dags unpause mrhealth_daily_pipeline

kubectl exec -it deployment/airflow-scheduler -n mrhealth-db -- \
  airflow dags unpause mrhealth_data_quality

kubectl exec -it deployment/airflow-scheduler -n mrhealth-db -- \
  airflow dags unpause mrhealth_data_retention

kubectl exec -it deployment/airflow-scheduler -n mrhealth-db -- \
  airflow dags unpause mrhealth_backfill_monitor

kubectl exec -it deployment/airflow-scheduler -n mrhealth-db -- \
  airflow dags unpause mrhealth_reference_refresh
```

---

## 9. Superset Setup

### 9.1 Access Superset Web UI

```bash
# Access Superset: http://<node-ip>:30188
# Default credentials: admin / admin
```

### 9.2 Configure BigQuery Connection

```bash
# Superset init job already creates the connection
# Verify in UI: Settings → Database Connections → BigQuery

# Connection URI format:
# bigquery://mrhealth-platform-XXXXX/mrhealth_gold
```

### 9.3 Create Dashboards Automatically

```bash
# Run setup script to create 4 dashboards, 25 datasets, 25 charts, 9 native filters
python scripts/setup_superset_dashboards_v2.py

# Expected output:
# ✓ Created dataset: agg_daily_sales
# ✓ Created dataset: dim_product
# ✓ Created chart: exec_line_daily_revenue
# ✓ Created dashboard: Executive Overview
# ... (25 datasets, 25 charts, 4 dashboards)
# Superset setup complete
```

### 9.4 Verify Dashboards

```bash
# Access dashboards in UI:
# http://<node-ip>:30188/superset/dashboard/executive-overview/
# http://<node-ip>:30188/superset/dashboard/unit-performance/
# http://<node-ip>:30188/superset/dashboard/product-analytics/
# http://<node-ip>:30188/superset/dashboard/order-detail/
```

---

## 10. Verification

### 10.1 Infrastructure Verification Script

```bash
# Run comprehensive verification
python scripts/verify_infrastructure.py

# Expected output:
# ✓ GCS bucket accessible
# ✓ BigQuery datasets created (4/4)
# ✓ BigQuery tables created (24/24)
# ✓ Cloud Functions deployed (3/3)
# ✓ K3s pods running (9/9)
# ✓ Airflow DAGs loaded (5/5)
# ✓ Superset dashboards created (4/4)
# All checks passed
```

### 10.2 Superset Upgrade Verification

```bash
# Verify Superset 4.0.2 setup
python scripts/verify_superset_upgrade.py

# Expected output:
# ✓ Superset health check passed
# ✓ BigQuery database connection active
# ✓ 25 datasets found
# ✓ 25 charts found
# ✓ 4 dashboards found
# ✓ Native filters configured (9 filters)
# ✓ CSS theme applied
# All checks passed (9/9)
```

### 10.3 Run Test Suite

```bash
# Run all tests (unit + integration)
pytest tests/ -v

# Expected: 14 test files, 80+ tests passing
# Coverage target: >85%

# Run only unit tests
pytest tests/unit/ -v

# Run only integration tests (requires GCP credentials)
pytest tests/integration/ -v -m integration
```

### 10.4 Check Service Endpoints

```bash
# Get K3s node IP
K3S_NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[0].address}')

# Verify all services accessible
echo "Airflow: http://$K3S_NODE_IP:30180"
echo "Superset: http://$K3S_NODE_IP:30188"
echo "Grafana: http://$K3S_NODE_IP:30300"
echo "Prometheus: http://$K3S_NODE_IP:30090"
echo "PostgreSQL: $K3S_NODE_IP:30432"

# Test HTTP endpoints
curl -s http://$K3S_NODE_IP:30180/health | jq .
curl -s http://$K3S_NODE_IP:30188/health | jq .
curl -s http://$K3S_NODE_IP:30300/api/health | jq .
curl -s http://$K3S_NODE_IP:30090/-/healthy
```

---

## 11. Troubleshooting

### 11.1 GCP Authentication Issues

**Problem:** `gcloud auth application-default login` fails or scripts can't access BigQuery

**Solution:**
```bash
# Re-authenticate
gcloud auth application-default revoke
gcloud auth application-default login

# Verify credentials
gcloud auth application-default print-access-token

# Check project is set
gcloud config get-value project
```

### 11.2 K3s Pod Crashes (OOMKilled)

**Problem:** Airflow scheduler or Superset pods crash with OOMKilled status

**Solution:**
```bash
# Check pod status
kubectl describe pod <pod-name> -n mrhealth-db

# Increase memory limits in deployment YAML
# For Airflow scheduler: change resources.limits.memory from 1Gi to 2Gi
# Apply updated deployment
kubectl apply -f k8s/airflow/deployment-scheduler.yaml -n mrhealth-db
```

### 11.3 BigQuery Permission Denied

**Problem:** Scripts fail with "Permission denied" errors when accessing BigQuery

**Solution:**
```bash
# Grant necessary roles to your user account
gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
  --member="user:$(gcloud config get-value account)" \
  --role="roles/bigquery.admin"

gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
  --member="user:$(gcloud config get-value account)" \
  --role="roles/storage.admin"

# Wait 60 seconds for IAM propagation
sleep 60
```

### 11.4 Cloud Function Not Triggering

**Problem:** csv-processor doesn't trigger when uploading files to GCS

**Solution:**
```bash
# Check Eventarc trigger
gcloud eventarc triggers list --location=$GCP_REGION

# Check Cloud Function logs
gcloud functions logs read csv-processor --gen2 --region=$GCP_REGION --limit=50

# Verify bucket path pattern
# Files must be uploaded to gs://<bucket>/raw/sales/ to trigger
gsutil ls gs://$GCS_BUCKET_NAME/raw/sales/ | head -5
```

### 11.5 Airflow DAGs Not Appearing

**Problem:** DAGs don't show up in Airflow Web UI

**Solution:**
```bash
# Check DAGs folder is mounted
kubectl exec -it deployment/airflow-scheduler -n mrhealth-db -- ls -la /opt/airflow/dags/

# Reserialize DAGs
kubectl exec -it deployment/airflow-scheduler -n mrhealth-db -- \
  airflow dags reserialize

# Check scheduler logs
kubectl logs deployment/airflow-scheduler -n mrhealth-db --tail=100

# Clear __pycache__ if code was updated
kubectl exec -it deployment/airflow-scheduler -n mrhealth-db -- \
  find /opt/airflow/dags -type d -name __pycache__ -exec rm -rf {} +
```

### 11.6 Superset Error 1035 (Async Queries)

**Problem:** Superset dashboards fail to load with Error 1035

**Solution:**
```bash
# Disable async queries in Superset config
# Edit k8s/superset/config.py and add:
# GLOBAL_ASYNC_QUERIES = False

# Restart Superset pod
kubectl rollout restart deployment/superset -n mrhealth-db
kubectl wait --for=condition=ready pod -l app=superset -n mrhealth-db --timeout=300s
```

### 11.7 PostgreSQL Connection Refused

**Problem:** Can't connect to PostgreSQL on port 30432

**Solution:**
```bash
# Check PostgreSQL pod is running
kubectl get pods -n mrhealth-db -l app=postgresql

# Check service
kubectl get svc postgresql -n mrhealth-db

# Test connection from within cluster
kubectl run -it --rm --restart=Never postgres-test --image=postgres:16-alpine -n mrhealth-db -- \
  psql -h postgresql -U postgres -d postgres -c "SELECT version();"

# Test from outside cluster
psql -h <k3s-node-ip> -p 30432 -U postgres -d postgres -c "SELECT version();"
```

### 11.8 Grafana Datasource Not Working

**Problem:** Grafana can't connect to Prometheus datasource

**Solution:**
```bash
# Check Prometheus is running
kubectl get pods -n mrhealth-db -l app=prometheus

# Test Prometheus endpoint from Grafana pod
kubectl exec -it deployment/grafana -n mrhealth-db -- \
  curl -s http://prometheus:9090/-/healthy

# Re-apply datasource provisioning
kubectl delete configmap grafana-datasources -n mrhealth-db
kubectl apply -f k8s/grafana/datasources.yaml -n mrhealth-db
kubectl rollout restart deployment/grafana -n mrhealth-db
```

---

## 12. Next Steps

After successful setup, explore these advanced topics:

### 12.1 Enable Cloud Scheduler for Data Generator

```bash
# Create Cloud Scheduler job to trigger data-generator daily
gcloud scheduler jobs create http daily-data-generation \
  --location=$GCP_REGION \
  --schedule="0 1 * * *" \
  --uri="https://$GCP_REGION-$GCP_PROJECT_ID.cloudfunctions.net/data-generator" \
  --http-method=POST \
  --time-zone="America/Sao_Paulo"
```

### 12.2 Configure Monitoring Alerts

```bash
# Set up BigQuery monitoring alerts in GCP Console
# Alerts → Create Policy → BigQuery metrics (slots, bytes processed)
```

### 12.3 Explore Terraform Infrastructure as Code

```bash
# Review Terraform modules in infra/
cd infra/terraform/modules/

# Plan and apply (after configuring backend)
terraform init
terraform plan
terraform apply
```

### 12.4 Integrate CI/CD Pipeline

```bash
# GitHub Actions workflows are in .github/workflows/
# - ci.yml: Lint, security scan, test on every PR
# - Configure GitHub Secrets: GCP_PROJECT_ID, GCP_SERVICE_ACCOUNT_KEY
```

### 12.5 Review Architecture Decision Records

```bash
# Read ADRs to understand design decisions
cat docs/adr/001-medallion-architecture.md
cat docs/adr/007-k8s-secret-management.md
```

---

## 13. Maintenance

### 13.1 Regular Tasks

- **Weekly:** Review Airflow DAG runs for failures
- **Monthly:** Check GCP Free Tier usage (should remain $0)
- **Quarterly:** Update Python dependencies (`pip install --upgrade -r requirements.txt`)

### 13.2 Backup Strategy

```bash
# Backup PostgreSQL data
kubectl exec -it postgresql-0 -n mrhealth-db -- \
  pg_dump -U postgres postgres > backup_$(date +%Y%m%d).sql

# Export BigQuery tables (automated via data_retention DAG)
```

### 13.3 Monitoring Dashboards

- **Grafana - K3s Infrastructure:** http://<node-ip>:30300/d/k3s-infra
- **Grafana - Airflow Metrics:** http://<node-ip>:30300/d/airflow-metrics
- **Prometheus Targets:** http://<node-ip>:30090/targets

---

## 14. Cost Monitoring

### 14.1 Verify Free Tier Compliance

```bash
# Check BigQuery usage
bq ls --max_results=100 --project_id=$GCP_PROJECT_ID

# Check Cloud Functions invocations
gcloud logging read "resource.type=cloud_function" \
  --limit=10 \
  --format=json \
  --project=$GCP_PROJECT_ID

# Monitor in GCP Console → Billing → Reports
```

### 14.2 Expected Free Tier Usage

- **BigQuery:** <1 TB queries/month, <10 GB storage (well within 10 GB free)
- **Cloud Functions:** <2M invocations/month (well within 2M free)
- **Cloud Storage:** <5 GB storage (well within 5 GB free)

---

## Success Criteria

After completing this setup, you should have:

- ✅ 4 BigQuery datasets with 24 tables (Bronze, Silver, Gold, Monitoring)
- ✅ 3 Cloud Functions deployed and tested
- ✅ Event-driven CSV ingestion (GCS → BigQuery in <3 min)
- ✅ 5 Airflow DAGs orchestrating daily transformations
- ✅ 4 Superset dashboards with 25 charts and 9 native filters
- ✅ K3s cluster with 9 pods (PostgreSQL, Airflow, Superset, Grafana, Prometheus)
- ✅ End-to-end data latency <3 minutes
- ✅ Test coverage >85%
- ✅ Monthly infrastructure cost: $0.00

---

## Support and Resources

- **Documentation:** See `docs/` folder for Data Catalog, ADRs
- **Tests:** See `tests/` folder for examples
- **Skills:** See `.claude/skills/` for best practices
- **Knowledge Base:** See `.claude/kb/` for GCP, Pydantic, etc.
- **Archived Features:** See `.claude/sdd/archive/` for shipped features

---

**Version:** 1.0.0
**Last Updated:** 2026-02-19
**Maintained By:** MR. HEALTH Data Engineering Team
