#!/bin/bash
# MR. HEALTH - IAM Setup for pg-reference-extractor
#
# Cria Service Account dedicada e atribui roles mínimas
# para a Cloud Function pg-reference-extractor.
#
# Uso: bash scripts/setup_pg_extractor_iam.sh

set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:?ERROR: GCP_PROJECT_ID environment variable is required}"
SA_NAME="pg-extractor-sa"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "============================================================"
echo "MR. HEALTH - IAM Setup for pg-reference-extractor"
echo "============================================================"
echo "  Project: ${PROJECT_ID}"
echo "  SA:      ${SA_EMAIL}"
echo ""

# 1. Criar Service Account
echo "[STEP 1] Creating Service Account..."
gcloud iam service-accounts create "${SA_NAME}" \
  --project="${PROJECT_ID}" \
  --display-name="PG Reference Extractor" \
  --description="Service Account for pg-reference-extractor Cloud Function" \
  2>/dev/null || echo "  [EXISTS] ${SA_NAME}"

echo "  [OK] Service Account ready"

# 2. Atribuir roles (menor privilégio)
echo ""
echo "[STEP 2] Assigning IAM roles..."

ROLES=(
  "roles/secretmanager.secretAccessor"
  "roles/storage.objectCreator"
)

for ROLE in "${ROLES[@]}"; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="${ROLE}" \
    --condition=None \
    --quiet
  echo "  [OK] ${ROLE}"
done

# 3. Permitir Cloud Scheduler invocar a Cloud Function
echo ""
echo "[STEP 3] Granting Cloud Functions invoker role..."
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/cloudfunctions.invoker" \
  --condition=None \
  --quiet
echo "  [OK] roles/cloudfunctions.invoker"

echo ""
echo "============================================================"
echo "[DONE] IAM configurado com sucesso"
echo "  SA: ${SA_EMAIL}"
echo "  Roles: secretmanager.secretAccessor, storage.objectCreator, cloudfunctions.invoker"
echo "============================================================"
