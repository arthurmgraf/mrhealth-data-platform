# ADR-005: Airflow on K3s over Cloud Composer

## Status
Accepted

## Date
2025-01-20

## Context
We needed orchestration for the daily Bronze->Silver->Gold pipeline and supporting DAGs (quality, retention, reference refresh, backfill monitoring). Options:
1. **Cloud Composer** (managed Airflow on GCP) -- $300+/month minimum
2. **Airflow on K3s** (self-hosted) -- $0 on existing server
3. **Cloud Scheduler + Cloud Functions** -- No DAG dependencies, limited monitoring

## Decision
We chose **Apache Airflow 2.8 self-hosted on K3s** with LocalExecutor.

Reasons:
1. **$0 cost**: K3s runs on existing server (single-node cluster)
2. **Full control**: Custom operators, sensors, callbacks, plugins
3. **5 DAGs**: daily_pipeline, data_quality, data_retention, reference_refresh, backfill_monitor
4. **hostPath volumes**: Git repo mounted directly into pods for instant code updates
5. **LocalExecutor**: Sufficient for 5 DAGs with 2Gi scheduler memory

## Consequences
- Scheduler needs 2Gi memory (1Gi causes OOM with parallel tasks)
- No auto-scaling (acceptable for current workload)
- Manual pod management (mitigated by K3s self-healing)
- Must clear __pycache__ after code changes via hostPath
- authorized_user GCP credentials cannot trigger Cloud Functions via IAM auth
