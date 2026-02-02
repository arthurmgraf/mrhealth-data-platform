# Deploy: pg-reference-extractor

## Pre-requisitos

1. Secret Manager configurado: `python scripts/setup_pg_secrets.py --project <PROJECT_ID>`
2. Service Account criada: `bash scripts/setup_pg_extractor_iam.sh`
3. PostgreSQL rodando no K3s com dados populados

## Deploy

```bash
cd cloud_functions/pg_reference_extractor

gcloud functions deploy pg-reference-extractor \
  --gen2 \
  --runtime=python311 \
  --region=us-central1 \
  --source=. \
  --entry-point=extract_reference_data \
  --trigger-http \
  --memory=256MB \
  --timeout=300s \
  --service-account=pg-extractor-sa@sixth-foundry-485810-e5.iam.gserviceaccount.com \
  --set-env-vars="PROJECT_ID=sixth-foundry-485810-e5,BUCKET_NAME=mrhealth-datalake-485810"
```

## Teste Manual

```bash
gcloud functions call pg-reference-extractor \
  --gen2 \
  --region=us-central1
```

## Configurar Cloud Scheduler

```bash
bash scripts/setup_pg_scheduler.sh
```

## Verificar

```bash
# Logs
gcloud functions logs read pg-reference-extractor --gen2 --region=us-central1 --limit=10

# CSVs gerados
gsutil ls gs://mrhealth-datalake-485810/raw/reference_data/

# Conteudo
gsutil cat gs://mrhealth-datalake-485810/raw/reference_data/produto.csv | head -5
```
