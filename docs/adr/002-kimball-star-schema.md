# ADR-002: Kimball Star Schema over Data Vault

## Status
Accepted

## Date
2025-01-12

## Context
The Gold layer needs a dimensional model for analytics.

**Options considered:**
1. **Kimball Star Schema** — Dimensions + facts, query-optimized, industry standard for BI
2. **Data Vault 2.0** — Hub/Link/Satellite, audit-friendly, better for rapidly changing sources
3. **One Big Table (OBT)** — Denormalized, simplest queries, but poor maintainability

## Decision
We chose **Kimball Star Schema** because:

1. **Query performance**: BigQuery excels with denormalized star schemas
2. **BI tool compatibility**: Superset and Looker Studio work best with star schemas
3. **Team familiarity**: Industry standard for data engineering
4. **Complexity match**: 4 dimensions + 2 facts + 3 aggregations is manageable
5. **SCD readiness**: Type 2 scaffolding on dim_product for future support

## Consequences
- Gold SQL scripts follow UPSERT pattern (MERGE statements)
- Surrogate keys generated via hash functions
- Pre-computed aggregations reduce query cost
- Date dimension populated via generate_date_array()
