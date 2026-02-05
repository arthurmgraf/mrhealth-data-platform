#!/bin/bash
# Deploy Airflow, Superset, and Grafana to K3s
# Run this script from the server via SSH

set -e

echo "=== Deploying Airflow ==="

# Apply Airflow manifests
kubectl apply -f /tmp/k8s/airflow/configmap.yaml
kubectl apply -f /tmp/k8s/airflow/pvc-dags.yaml
kubectl apply -f /tmp/k8s/airflow/pvc-logs.yaml
kubectl apply -f /tmp/k8s/airflow/secret-gcp.yaml
kubectl apply -f /tmp/k8s/airflow/postgres.yaml
kubectl apply -f /tmp/k8s/airflow/webserver.yaml
kubectl apply -f /tmp/k8s/airflow/scheduler.yaml

echo "Waiting for Airflow Postgres to be ready..."
kubectl wait --for=condition=ready pod -l app=airflow-postgres -n mrhealth-db --timeout=120s

echo "=== Deploying Superset ==="

# Apply Superset manifests
kubectl apply -f /tmp/k8s/superset/configmap.yaml
kubectl apply -f /tmp/k8s/superset/deployment.yaml

echo "=== Deploying Grafana ==="

# Grafana runs in mrhealth-db namespace (shared with Airflow, PG, Superset)
# No separate namespace needed

# Apply Grafana manifests
kubectl apply -f /tmp/k8s/grafana/pvc.yaml
kubectl apply -f /tmp/k8s/grafana/configmap.yaml
kubectl apply -f /tmp/k8s/grafana/deployment.yaml
kubectl apply -f /tmp/k8s/grafana/service.yaml

echo "Waiting for Grafana to be ready..."
kubectl wait --for=condition=ready pod -l app=grafana -n mrhealth-db --timeout=180s

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "Access URLs:"
echo "  Airflow:  http://15.235.61.251:30180"
echo "  Superset: http://15.235.61.251:30188"
echo "  Grafana:  http://15.235.61.251:30300  (admin / GrafanaMrH3alth2026)"
echo ""
echo "Check pod status with:"
echo "  kubectl get pods -n mrhealth-db"
echo ""
echo "NOTE: Grafana will download the BigQuery plugin on first start."
echo "  This may take 1-2 minutes. Check logs with:"
echo "  kubectl logs -l app=grafana -n mrhealth-db -f"
