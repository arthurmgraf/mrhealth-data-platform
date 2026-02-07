# ADR-007: Kubernetes Secret Management Strategy

## Status
Accepted

## Date
2026-02-07

## Context
Multiple K8s services (PostgreSQL, Airflow, Grafana, Superset) require credentials. Initially, some passwords were hardcoded in deployment manifests (e.g., Grafana admin password, Superset secret key).

**Options considered:**
1. **Kubernetes Secrets (stringData)** -- Native K8s, placeholder values in git, real values on server
2. **External Secrets Operator** -- Syncs from GCP Secret Manager, but adds complexity
3. **Sealed Secrets** -- Encrypted in git, requires controller installation

## Decision
We chose **Kubernetes Secrets with placeholder values** because:

1. **Simplicity**: No additional controllers or operators needed
2. **Single-node K3s**: External secrets operator is overkill for one server
3. **Portfolio scope**: Demonstrates awareness of secret management best practices
4. **GCP Free Tier**: Secret Manager costs $0.06/10K operations, but adds complexity

## Implementation
- `k8s/secrets.yaml`: Centralized secret with placeholder values (committed to git)
- All deployments reference secrets via `secretKeyRef` (never hardcoded in env)
- `k8s/network-policy.yaml`: NetworkPolicy restricts inter-pod communication
- `.gitignore`: Excludes `.env`, `keys/`, and credential files

## Security Measures Applied
1. No plaintext passwords in deployment manifests
2. NetworkPolicy: default deny ingress + explicit allow rules
3. Pod security context: non-root users (Grafana uid 472)
4. ReadOnly volume mounts for GCP credentials
5. Placeholder pattern: `REPLACE_WITH_SECURE_PASSWORD` in committed files

## Consequences
- Operators must replace placeholder values on the server before applying
- No automatic secret rotation (acceptable for portfolio/single-node scope)
- NetworkPolicy enforcement depends on K3s CNI (Flannel supports it with kube-router)
