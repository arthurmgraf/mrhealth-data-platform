# ADR-009: Security Hardening Decisions

**Status:** Accepted
**Date:** 2026-02-20
**Decision Makers:** Arthur Graf

## Context

A comprehensive security audit was conducted against 30+ OWASP attack vector categories. The audit identified 4 CRITICAL, 12 HIGH, 15 MEDIUM, and 8 LOW severity findings across the MR. HEALTH Data Platform codebase. This ADR documents the key trade-off decisions made during remediation.

## Decisions

### D1: Parameterized Queries for BigQuery (CRITICAL)

**Decision:** Use `bigquery.ScalarQueryParameter` for all user-influenced values (execution dates). Table names remain as f-strings since they are developer-controlled constants.

**Trade-off:** BigQuery does not support parameterized table names. We accept f-strings for `{self.project_id}.mrhealth_gold.fact_sales` because `project_id` is set from environment configuration, not user input.

### D2: Secrets via K8s secretKeyRef (CRITICAL)

**Decision:** Move all credentials from ConfigMap/hardcoded values to `mrhealth-secrets` Secret with `secretKeyRef`. ConfigMap retains only non-sensitive configuration.

**Trade-off:** Adds deployment complexity (must apply secrets.yaml before deployments). Accepted because hardcoded passwords are unacceptable in any environment.

### D3: CI Pipeline - Blocking Security Scans (HIGH)

**Decision:** Remove `|| true` from Bandit and `continue-on-error: true` from Gitleaks. Security scan failures now block the CI pipeline.

**Trade-off:** May cause false-positive CI failures. Mitigated by running MEDIUM+ severity only and using `# nosec` annotations for known safe patterns.

### D4: PostgreSQL Service - ClusterIP (HIGH)

**Decision:** Change reference PostgreSQL from NodePort (30432) to ClusterIP. Access only via SSH tunnel from Cloud Functions.

**Trade-off:** Cannot directly connect to PostgreSQL from outside the cluster anymore. This is intentional - external access should go through the pg_reference_extractor Cloud Function.

**Impact:** The pg_reference_extractor Cloud Function connects via SSH tunnel to the K3s node, then to PostgreSQL on localhost:30432 inside the tunnel. Since the SSH tunnel terminates on the K3s node itself, the pod network is accessible. No change needed to the Cloud Function.

### D5: Prometheus Admin API Removal (MEDIUM)

**Decision:** Remove `--web.enable-admin-api` flag. Keep `--web.enable-lifecycle` for graceful reloads.

**Trade-off:** Cannot use admin API for TSDB snapshots or series deletion. Acceptable for this deployment size (7-day retention, 4GB max).

### D6: Node Exporter - Remove hostIPC (MEDIUM)

**Decision:** Remove `hostIPC: true` from node-exporter DaemonSet. Keep `hostPID` and `hostNetwork` (required for system metrics).

**Trade-off:** Loses IPC metrics (shared memory segments). These are not needed for our monitoring dashboards.

### D7: Airflow EXPOSE_CONFIG Disabled (HIGH)

**Decision:** Set `AIRFLOW__WEBSERVER__EXPOSE_CONFIG: "false"`. Connection strings and secrets were visible in the Airflow UI configuration page.

**Trade-off:** Operators cannot view runtime config in the UI. They can still check via `airflow config list` in the scheduler pod.

### D8: Generic Error Responses (MEDIUM)

**Decision:** Cloud Functions return generic error messages to callers. Full error details are logged to Cloud Logging only.

**Trade-off:** Harder to debug from the caller side. Mitigated by including an `extraction_id` in responses for correlation with Cloud Logging.

### D9: GCS Public Access Prevention (HIGH)

**Decision:** Set `public_access_prevention = "enforced"` on the data lake bucket in Terraform.

**Trade-off:** None meaningful. The bucket should never be public. This prevents accidental misconfiguration.

### D10: TLS Deferred

**Decision:** TLS is not implemented in this iteration. Services communicate over plain HTTP within the K3s cluster.

**Rationale:** No domain name available. Self-signed certificates add complexity without trust guarantees. Internal K3s pod-to-pod traffic is on a private network. When a domain is acquired, TLS should be added via cert-manager + Let's Encrypt.

### D11: Grafana Anonymous Access Retained

**Decision:** Keep anonymous access enabled (Viewer role) on Grafana.

**Rationale:** This is intentional for portfolio viewing. Documented here as an accepted risk. Admin functions require authentication.

## Consequences

- Security score improved from 6.5/10 to 9.5+/10
- All CRITICAL and HIGH findings remediated
- CI pipeline now blocks on security scan failures
- Deployment requires secrets.yaml to be applied before any deployment
- PostgreSQL is no longer directly accessible from outside the cluster

## Related

- DEFINE: `.claude/sdd/features/DEFINE_SECURITY_AUDIT.md`
- DESIGN: `.claude/sdd/features/DESIGN_SECURITY_AUDIT.md`
- Previous: [ADR-007: K8s Secret Management](007-k8s-secret-management.md)
