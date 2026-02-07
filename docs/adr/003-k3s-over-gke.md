# ADR-003: K3s Self-Hosted over GKE for Orchestration

## Status
Accepted

## Date
2025-01-15

## Context
Airflow, PostgreSQL, Grafana, Prometheus, and Superset need container orchestration. GKE costs $72+/month minimum.

**Options considered:**
1. **K3s (self-hosted)** — Lightweight Kubernetes on a single VM, zero cost
2. **GKE Autopilot** — Fully managed, but $72/month minimum
3. **Docker Compose** — Simplest, but no auto-restart or scaling
4. **Cloud Run** — Serverless, but Airflow needs persistent state

## Decision
We chose **K3s** because:

1. **Zero cost**: Runs on any Linux machine
2. **Real Kubernetes**: Full K8s API, production-realistic experience
3. **Lightweight**: Single binary, <512MB RAM for control plane
4. **Portfolio value**: Demonstrates Kubernetes skills without cloud billing
5. **Full stack**: Supports Helm, PVCs, Secrets, ConfigMaps, Services, Ingress

## Consequences
- K8s manifests in k8s/ directory
- Helm values for Airflow in k8s/airflow/
- Monitoring stack with Prometheus scraping
- Git-sync for DAG deployment
- Manual upgrades (no managed auto-patching)
