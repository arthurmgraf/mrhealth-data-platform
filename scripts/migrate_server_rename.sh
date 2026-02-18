#!/bin/bash
# =============================================================================
# MR. HEALTH Data Platform -- Server Migration Script
# =============================================================================
#
# Renames the project folder on the production server and restarts all K8s
# pods that use hostPath volumes pointing to the old path.
#
# WHAT THIS DOES:
#   1. Renames /home/arthur/case_mrHealth -> /home/arthur/mrhealth-data-platform
#   2. Updates git remote URL to match the renamed GitHub repo
#   3. Restarts K8s deployments that use hostPath volumes (Grafana, Superset)
#   4. Verifies all pods are running
#
# USAGE (run on production server 15.235.61.251):
#   ssh arthur@15.235.61.251
#   bash /home/arthur/case_mrHealth/scripts/migrate_server_rename.sh
#
# ROLLBACK:
#   mv /home/arthur/mrhealth-data-platform /home/arthur/case_mrHealth
#   cd /home/arthur/case_mrHealth && git remote set-url origin https://github.com/arthurmgraf/mrhealth-data-platform.git
#   kubectl -n mrhealth-db rollout restart deployment grafana superset
#
# Author: Arthur Graf
# Date: February 2026
# =============================================================================

set -euo pipefail

OLD_DIR="/home/arthur/case_mrHealth"
NEW_DIR="/home/arthur/mrhealth-data-platform"
NAMESPACE="mrhealth-db"
NEW_REPO_URL="https://github.com/arthurmgraf/mrhealth-data-platform.git"

echo "============================================================"
echo "MR. HEALTH -- Server Migration: Folder Rename"
echo "============================================================"
echo ""
echo "  Old path: $OLD_DIR"
echo "  New path: $NEW_DIR"
echo "  Repo URL: $NEW_REPO_URL"
echo ""

# --- Pre-flight checks ---

if [ ! -d "$OLD_DIR" ]; then
    if [ -d "$NEW_DIR" ]; then
        echo "[OK] Folder already renamed to $NEW_DIR. Skipping rename."
    else
        echo "[ERROR] Neither $OLD_DIR nor $NEW_DIR exists!"
        exit 1
    fi
else
    if [ -d "$NEW_DIR" ]; then
        echo "[ERROR] Both $OLD_DIR and $NEW_DIR exist! Resolve manually."
        exit 1
    fi

    # --- Step 1: Rename the folder ---
    echo "[STEP 1] Renaming project folder..."
    mv "$OLD_DIR" "$NEW_DIR"
    echo "  [OK] $OLD_DIR -> $NEW_DIR"
fi

# --- Step 2: Update git remote URL ---
echo ""
echo "[STEP 2] Updating git remote URL..."
cd "$NEW_DIR"
git remote set-url origin "$NEW_REPO_URL"
echo "  [OK] Remote updated to $NEW_REPO_URL"

# --- Step 3: Pull latest code (has the renamed references) ---
echo ""
echo "[STEP 3] Pulling latest code..."
git pull origin main
echo "  [OK] Latest code pulled"

# --- Step 4: Restart K8s deployments with hostPath volumes ---
echo ""
echo "[STEP 4] Restarting K8s deployments that use hostPath volumes..."

# Grafana uses hostPath for dashboards and keys
echo "  Restarting grafana..."
kubectl -n "$NAMESPACE" rollout restart deployment grafana 2>/dev/null || echo "  [WARN] grafana deployment not found"

# Superset uses hostPath for keys
echo "  Restarting superset..."
kubectl -n "$NAMESPACE" rollout restart deployment superset 2>/dev/null || echo "  [WARN] superset deployment not found"

# Airflow uses PVC (not hostPath) for DAGs, but restart to pick up new git remote
echo "  Restarting airflow-scheduler..."
kubectl -n "$NAMESPACE" rollout restart deployment airflow-scheduler 2>/dev/null || echo "  [WARN] airflow-scheduler deployment not found"

echo "  Restarting airflow-webserver..."
kubectl -n "$NAMESPACE" rollout restart deployment airflow-webserver 2>/dev/null || echo "  [WARN] airflow-webserver deployment not found"

# --- Step 5: Wait for rollouts ---
echo ""
echo "[STEP 5] Waiting for rollouts to complete..."
kubectl -n "$NAMESPACE" rollout status deployment grafana --timeout=120s 2>/dev/null || true
kubectl -n "$NAMESPACE" rollout status deployment superset --timeout=120s 2>/dev/null || true
kubectl -n "$NAMESPACE" rollout status deployment airflow-scheduler --timeout=120s 2>/dev/null || true
kubectl -n "$NAMESPACE" rollout status deployment airflow-webserver --timeout=120s 2>/dev/null || true

# --- Step 6: Verify ---
echo ""
echo "[STEP 6] Verifying pod status..."
kubectl -n "$NAMESPACE" get pods -o wide
echo ""

# Check for CrashLoopBackOff or Error
UNHEALTHY=$(kubectl -n "$NAMESPACE" get pods --no-headers 2>/dev/null | grep -E "CrashLoopBackOff|Error|ImagePullBackOff" | wc -l)
if [ "$UNHEALTHY" -gt 0 ]; then
    echo "[WARN] $UNHEALTHY pod(s) in unhealthy state. Check logs:"
    kubectl -n "$NAMESPACE" get pods --no-headers | grep -E "CrashLoopBackOff|Error|ImagePullBackOff"
    echo ""
    echo "  Debug: kubectl -n $NAMESPACE logs <pod-name>"
else
    echo "[OK] All pods healthy!"
fi

# --- Step 7: Verify hostPath mounts ---
echo ""
echo "[STEP 7] Verifying hostPath directories exist..."
for dir in "$NEW_DIR/keys" "$NEW_DIR/k8s/grafana/dashboards"; do
    if [ -d "$dir" ]; then
        echo "  [OK] $dir exists"
    else
        echo "  [WARN] $dir NOT found!"
    fi
done

echo ""
echo "============================================================"
echo "Migration complete!"
echo "============================================================"
echo ""
echo "Verify services:"
echo "  Airflow:  http://15.235.61.251:30180"
echo "  Grafana:  http://15.235.61.251:30300"
echo "  Superset: http://15.235.61.251:30188"
echo ""
