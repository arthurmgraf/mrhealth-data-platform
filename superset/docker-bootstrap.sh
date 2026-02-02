#!/bin/bash
set -e

echo "=== MR. Health Superset Bootstrap ==="

echo "[1/3] Upgrading database..."
superset db upgrade

echo "[2/3] Creating admin user..."
superset fab create-admin \
  --username admin \
  --firstname Admin \
  --lastname User \
  --email admin@mrhealth.local \
  --password admin || true

echo "[3/3] Initializing roles..."
superset init

echo "=== Bootstrap complete ==="
