# ADR-001: GCP Free Tier as Sole Infrastructure Provider

## Status
Accepted

## Date
2025-01-10

## Context
MR. HEALTH is a data platform for a 50-unit restaurant chain processing ~100 CSVs/day. Infrastructure cost is a primary constraint.

**Options considered:**
1. **GCP Free Tier** — BigQuery (1TB query/month, 10GB storage), Cloud Functions (2M invocations), GCS (5GB)
2. **AWS Free Tier** — Similar limits but less generous for analytics
3. **On-premises** — Full control, but maintenance overhead and hardware cost
4. **Databricks Community** — Free Spark, but limited to notebooks

## Decision
We chose **GCP Free Tier** because:

1. **BigQuery free tier**: 1TB query/month + 10GB storage covers the workload
2. **Cloud Functions 2nd Gen**: Event-driven ingestion at zero cost for our volume
3. **Eventarc**: Native GCS-to-CloudFunction triggering
4. **Workload Identity Federation**: Zero service account key management
5. **Portfolio value**: Demonstrates enterprise architecture within cost constraints

## Consequences
- All compute via Cloud Functions (serverless, event-driven)
- All storage via BigQuery (Bronze/Silver/Gold) + GCS (raw landing zone)
- Orchestration via Airflow on K3s (self-hosted, zero cloud cost)
- Monitoring via Grafana + Prometheus on K3s
