# PostgreSQL Integration - Guia Operacional

## Visao Geral

A integracao PostgreSQL conecta o banco de dados da matriz (hospedado em K3s) ao pipeline de dados na nuvem GCP. Uma Cloud Function extrai diariamente as 4 tabelas de referencia via SSH tunnel e deposita como CSVs no GCS.

```
PostgreSQL (K3s) --SSH--> Cloud Function --CSV--> GCS --> BigQuery (Medallion)
```

---

## Componentes

| Componente | Localizacao | Funcao |
|------------|-------------|--------|
| PostgreSQL 16 | K3s (pod) | Armazena dados de referencia |
| pg-reference-extractor | Cloud Function (GCP) | Extrai dados via SSH tunnel |
| Secret Manager | GCP | Armazena credenciais |
| Cloud Scheduler | GCP | Dispara extracao diaria (01:00) |

---

## Setup Inicial

### 1. PostgreSQL no K3s

```bash
# Conectar ao servidor
<YOUR-SSH-USER>@<K3s-IP>

# Aplicar manifests (em ordem)
kubectl apply -f k8s/postgresql/namespace.yaml
kubectl apply -f k8s/postgresql/secret.yaml
kubectl apply -f k8s/postgresql/pvc.yaml
kubectl apply -f k8s/postgresql/configmap.yaml
kubectl apply -f k8s/postgresql/deployment.yaml
kubectl apply -f k8s/postgresql/service.yaml

# Aguardar pod ficar ready
kubectl -n mrhealth-db wait --for=condition=ready pod -l app=postgresql --timeout=120s

# Verificar
kubectl -n mrhealth-db get pods
```

### 2. Popular Dados

```bash
# Port-forward para acesso local
kubectl -n mrhealth-db port-forward svc/postgresql 5432:5432 &

# Seed
python scripts/seed_postgresql.py --host 127.0.0.1 --password <admin-password>

# Verificar
kubectl -n mrhealth-db exec -it deploy/postgresql -- \
  psql -U mrh_extractor -d mrhealth -c "SELECT count(*) FROM produto;"
```

### 3. Infraestrutura GCP

```bash
# Secrets
python scripts/setup_pg_secrets.py --project sixth-foundry-485810-e5

# IAM
bash scripts/setup_mrh_extractor_iam.sh

# Deploy Cloud Function
cd cloud_functions/pg_reference_extractor
gcloud functions deploy pg-reference-extractor \
  --gen2 --runtime=python311 --region=us-central1 \
  --source=. --entry-point=extract_reference_data \
  --trigger-http --memory=256MB --timeout=300s \
  --service-account=pg-extractor-sa@sixth-foundry-485810-e5.iam.gserviceaccount.com \
  --set-env-vars="PROJECT_ID=sixth-foundry-485810-e5,BUCKET_NAME=mrhealth-datalake-485810"

# Scheduler
bash scripts/setup_pg_scheduler.sh
```

---

## Operacao Diaria

### Fluxo Automatico

1. **01:00 (America/Sao_Paulo)** - Cloud Scheduler dispara Cloud Function
2. Cloud Function busca credenciais no Secret Manager
3. Estabelece SSH tunnel para K3s
4. Extrai 4 tabelas via SELECT
5. Gera CSVs e deposita no GCS `raw/reference_data/`
6. Pipeline existente processa (Bronze -> Silver -> Gold)

### Monitoramento

```bash
# Logs da Cloud Function
gcloud functions logs read pg-reference-extractor --gen2 --region=us-central1 --limit=20

# Verificar CSVs no GCS
gsutil ls -l gs://mrhealth-datalake-485810/raw/reference_data/

# Verificar dados no BigQuery
bq query "SELECT count(*) FROM case_ficticio_bronze.products"
```

### Execucao Manual

```bash
# Disparar manualmente
gcloud functions call pg-reference-extractor --gen2 --region=us-central1

# Ou via scheduler
gcloud scheduler jobs run pg-reference-extraction \
  --project=sixth-foundry-485810-e5 --location=us-central1
```

---

## Troubleshooting

| Problema | Causa | Solucao |
|----------|-------|---------|
| SSH timeout | K3s server indisponivel | Verificar se o servidor esta online; checar porta 22 |
| PostgreSQL connection refused | Pod nao esta running | `kubectl -n mrhealth-db get pods` e reiniciar se necessario |
| Permission denied (PG) | User mrh_extractor sem GRANT | Re-executar `sql/postgresql/create_readonly_user.sql` |
| Empty CSV | Tabela sem dados | Re-executar `scripts/seed_postgresql.py` |
| Secret not found | Secret Manager nao configurado | Re-executar `scripts/setup_pg_secrets.py` |
| Scheduler nao dispara | Job nao criado ou SA sem permissao | `gcloud scheduler jobs list` e verificar IAM |

### Verificar Pod PostgreSQL

```bash
# Status
kubectl -n mrhealth-db get pods

# Logs
kubectl -n mrhealth-db logs deploy/postgresql

# Conectar ao psql
kubectl -n mrhealth-db exec -it deploy/postgresql -- psql -U mrhealth_admin -d mrhealth
```

### Rotacao de Credenciais

```bash
# Atualizar secret no Secret Manager
python scripts/setup_pg_secrets.py --project sixth-foundry-485810-e5

# A Cloud Function usa sempre a versao "latest" automaticamente
```

---

## Arquivos

| Arquivo | Descricao |
|---------|-----------|
| `k8s/postgresql/*.yaml` | Kubernetes manifests (6 arquivos) |
| `sql/postgresql/create_tables.sql` | DDL das tabelas |
| `sql/postgresql/create_readonly_user.sql` | User read-only |
| `scripts/seed_postgresql.py` | Popular dados de referencia |
| `scripts/setup_pg_secrets.py` | Configurar Secret Manager |
| `scripts/setup_mrh_extractor_iam.sh` | Configurar IAM |
| `scripts/setup_pg_scheduler.sh` | Configurar Cloud Scheduler |
| `cloud_functions/pg_reference_extractor/` | Cloud Function source |
| `tests/unit/test_mrh_extractor.py` | Testes unitarios |
| `tests/integration/test_pg_connectivity.py` | Testes de integracao |
