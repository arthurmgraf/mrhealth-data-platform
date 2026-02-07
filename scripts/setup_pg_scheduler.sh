#!/bin/bash
# MR. HEALTH - Cloud Scheduler Setup for pg-reference-extractor
#
# Configura o Cloud Scheduler para disparar a extração diária
# de dados de referência do PostgreSQL.
#
# Uso: bash scripts/setup_pg_scheduler.sh
#
# Pré-requisito: Cloud Function pg-reference-extractor já deployada

set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:?ERROR: GCP_PROJECT_ID environment variable is required}"
REGION="${GCP_REGION:-us-central1}"
SA_EMAIL="pg-extractor-sa@${PROJECT_ID}.iam.gserviceaccount.com"
JOB_NAME="pg-reference-extraction"
FUNCTION_URL="https://${REGION}-${PROJECT_ID}.cloudfunctions.net/pg-reference-extractor"

echo "============================================================"
echo "MR. HEALTH - Cloud Scheduler Setup"
echo "============================================================"
echo "  Project:  ${PROJECT_ID}"
echo "  Region:   ${REGION}"
echo "  Job:      ${JOB_NAME}"
echo "  Schedule: 0 1 * * * (01:00 America/Sao_Paulo)"
echo "  Target:   ${FUNCTION_URL}"
echo ""

# Deletar job existente se houver
echo "[STEP 1] Removing existing job (if any)..."
gcloud scheduler jobs delete "${JOB_NAME}" \
  --project="${PROJECT_ID}" \
  --location="${REGION}" \
  --quiet 2>/dev/null || echo "  [INFO] No existing job to delete"

# Criar novo job
echo ""
echo "[STEP 2] Creating Cloud Scheduler job..."
gcloud scheduler jobs create http "${JOB_NAME}" \
  --project="${PROJECT_ID}" \
  --location="${REGION}" \
  --schedule="0 1 * * *" \
  --time-zone="America/Sao_Paulo" \
  --uri="${FUNCTION_URL}" \
  --http-method=POST \
  --oidc-service-account-email="${SA_EMAIL}" \
  --oidc-token-audience="${FUNCTION_URL}" \
  --attempt-deadline="300s" \
  --max-retry-attempts=3 \
  --min-backoff-duration="30s" \
  --max-backoff-duration="120s" \
  --description="Extração diária de dados de referência do PostgreSQL (K3s) para GCS"

echo "  [OK] Job created"

echo ""
echo "============================================================"
echo "[DONE] Cloud Scheduler configurado"
echo ""
echo "  Teste manual:"
echo "    gcloud scheduler jobs run ${JOB_NAME} --project=${PROJECT_ID} --location=${REGION}"
echo ""
echo "  Verificar logs:"
echo "    gcloud functions logs read pg-reference-extractor --gen2 --region=${REGION} --limit=10"
echo "============================================================"
