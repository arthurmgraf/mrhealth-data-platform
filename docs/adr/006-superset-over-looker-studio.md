# ADR-006: Apache Superset over Looker Studio

## Status
Accepted (supersedes initial Looker Studio choice)

## Date
2026-02-07

## Context
Initially the project used Looker Studio for dashboards. We switched to Apache Superset for several reasons.

Options:
1. **Looker Studio** (Google) -- Free, cloud-hosted, limited customization
2. **Apache Superset** (open-source) -- Self-hosted, full control, native BigQuery
3. **Metabase** -- Open-source, simpler but less features
4. **Grafana** -- Excellent for metrics, limited for BI analytics

## Decision
We chose **Apache Superset 4.0.2** self-hosted on K3s with BigQuery as the data source.

Reasons:
1. **Self-hosted**: Full control, no Google account dependency for viewers
2. **Native BigQuery**: sqlalchemy-bigquery driver, ADC credentials
3. **Native filters**: filter_select, filter_time (replaced deprecated Filter Box)
4. **CSS theming**: Custom mrhealth-green theme (#28a745)
5. **4 dashboards**: Executive Overview, Unit Performance, Product Analytics, Order Detail
6. **25 charts, 9 filters**: Comprehensive analytics coverage

## Consequences
- Requires K3s deployment and maintenance
- PostgreSQL metadata database (shared with Airflow)
- Session-based authentication (JWT broken in Superset 4.x)
- packaging<24 must be installed before other deps (version conflict)
- initContainer clears stale .local packages on startup
