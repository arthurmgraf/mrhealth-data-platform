# ADR-004: Event-Driven Ingestion over Batch Processing

## Status
Accepted

## Date
2025-01-18

## Context
The 50 restaurant units upload CSV files (pedido.csv, item_pedido.csv) to GCS throughout the day. We needed to decide how to process these files into BigQuery Bronze layer.

Options considered:
1. **Batch processing** (Cloud Scheduler + Cloud Function) -- Poll GCS at intervals
2. **Event-driven** (Eventarc + Cloud Function) -- React to GCS upload events
3. **Streaming** (Pub/Sub + Dataflow) -- Real-time stream processing

## Decision
We chose **event-driven ingestion** using Eventarc triggers on GCS `object.finalized` events.

Reasons:
1. **Zero polling cost**: No scheduled invocations, only triggered on actual uploads
2. **Near real-time**: Files processed within seconds of upload (~2-3 min end-to-end)
3. **Free Tier fit**: Cloud Functions 2nd Gen with 2M free invocations/month
4. **Simplicity**: Single function handles validation, dedup, and BigQuery load
5. **Quarantine pattern**: Invalid files moved to quarantine prefix with error reports

## Consequences
- CSV files must follow naming convention (pedido.csv, item_pedido.csv)
- Cloud Function must be idempotent (duplicate events are possible)
- Batch transforms (Silver/Gold) still run via Airflow on schedule
- No ordering guarantee between pedido.csv and item_pedido.csv uploads
