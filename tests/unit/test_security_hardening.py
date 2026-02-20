"""
Security hardening verification tests.

Validates that security controls from ADR-009 are properly implemented
across configuration files, K8s manifests, and application code.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).parent.parent.parent


class TestSuperset:
    """Verify Superset security configuration."""

    def test_secret_key_from_env(self, project_root: Path):
        """SECRET_KEY must come from env var, not hardcoded."""
        config = (project_root / "superset" / "superset_config.py").read_text()
        assert 'os.environ["SUPERSET_SECRET_KEY"]' in config
        assert "change_me" not in config.lower()
        assert "default_secret" not in config.lower()

    def test_csrf_enabled(self, project_root: Path):
        """CSRF protection must be enabled."""
        config = (project_root / "superset" / "superset_config.py").read_text()
        assert "WTF_CSRF_ENABLED = True" in config

    def test_template_processing_disabled(self, project_root: Path):
        """Jinja template processing must be disabled (SSTI prevention)."""
        config = (project_root / "superset" / "superset_config.py").read_text()
        assert '"ENABLE_TEMPLATE_PROCESSING": False' in config


class TestAirflowK8s:
    """Verify Airflow K8s security configuration."""

    def test_expose_config_disabled(self, project_root: Path):
        """Airflow config should not be exposed in the web UI."""
        configmap = (project_root / "k8s" / "airflow" / "configmap.yaml").read_text()
        data = yaml.safe_load(configmap)
        assert data["data"]["AIRFLOW__WEBSERVER__EXPOSE_CONFIG"] == "false"

    def test_no_secrets_in_configmap(self, project_root: Path):
        """ConfigMap must not contain SECRET_KEY or DB connection strings."""
        configmap = (project_root / "k8s" / "airflow" / "configmap.yaml").read_text()
        data = yaml.safe_load(configmap)
        assert "AIRFLOW__WEBSERVER__SECRET_KEY" not in data["data"]
        assert "AIRFLOW__DATABASE__SQL_ALCHEMY_CONN" not in data["data"]

    def test_postgres_password_from_secret(self, project_root: Path):
        """Airflow PostgreSQL password must use secretKeyRef."""
        manifest = (project_root / "k8s" / "airflow" / "postgres.yaml").read_text()
        docs = list(yaml.safe_load_all(manifest))
        deployment = next(d for d in docs if d.get("kind") == "Deployment")
        container = deployment["spec"]["template"]["spec"]["containers"][0]
        pg_pass_env = next(e for e in container["env"] if e["name"] == "POSTGRES_PASSWORD")
        assert "valueFrom" in pg_pass_env
        assert pg_pass_env["valueFrom"]["secretKeyRef"]["name"] == "mrhealth-secrets"

    def test_webserver_has_secret_key_from_secret(self, project_root: Path):
        """Webserver deployment must get SECRET_KEY from K8s Secret."""
        manifest = (project_root / "k8s" / "airflow" / "webserver.yaml").read_text()
        docs = list(yaml.safe_load_all(manifest))
        deployment = next(d for d in docs if d.get("kind") == "Deployment")
        webserver = next(
            c
            for c in deployment["spec"]["template"]["spec"]["containers"]
            if c["name"] == "webserver"
        )
        secret_env = next(
            e for e in webserver["env"] if e["name"] == "AIRFLOW__WEBSERVER__SECRET_KEY"
        )
        assert secret_env["valueFrom"]["secretKeyRef"]["key"] == "airflow-secret-key"

    def test_scheduler_has_db_conn_from_secret(self, project_root: Path):
        """Scheduler deployment must get DB conn from K8s Secret."""
        manifest = (project_root / "k8s" / "airflow" / "scheduler.yaml").read_text()
        docs = list(yaml.safe_load_all(manifest))
        deployment = next(d for d in docs if d.get("kind") == "Deployment")
        scheduler = next(
            c
            for c in deployment["spec"]["template"]["spec"]["containers"]
            if c["name"] == "scheduler"
        )
        db_env = next(
            e for e in scheduler["env"] if e["name"] == "AIRFLOW__DATABASE__SQL_ALCHEMY_CONN"
        )
        assert db_env["valueFrom"]["secretKeyRef"]["key"] == "airflow-db-conn"


class TestPrometheus:
    """Verify Prometheus security configuration."""

    def test_admin_api_disabled(self, project_root: Path):
        """Prometheus admin API must not be enabled."""
        manifest = (project_root / "k8s" / "prometheus" / "deployment.yaml").read_text()
        assert "--web.enable-admin-api" not in manifest

    def test_lifecycle_api_enabled(self, project_root: Path):
        """Prometheus lifecycle API should remain for graceful reloads."""
        manifest = (project_root / "k8s" / "prometheus" / "deployment.yaml").read_text()
        assert "--web.enable-lifecycle" in manifest


class TestNodeExporter:
    """Verify node-exporter security configuration."""

    def test_no_host_ipc(self, project_root: Path):
        """Node exporter must not use hostIPC."""
        manifest = (project_root / "k8s" / "prometheus" / "node-exporter.yaml").read_text()
        docs = list(yaml.safe_load_all(manifest))
        daemonset = next(d for d in docs if d.get("kind") == "DaemonSet")
        spec = daemonset["spec"]["template"]["spec"]
        assert spec.get("hostIPC") is not True


class TestPostgreSQL:
    """Verify PostgreSQL service security."""

    def test_clusterip_not_nodeport(self, project_root: Path):
        """Reference PostgreSQL must use ClusterIP, not NodePort."""
        manifest = (project_root / "k8s" / "postgresql" / "service.yaml").read_text()
        svc = yaml.safe_load(manifest)
        assert svc["spec"]["type"] == "ClusterIP"


class TestCIPipeline:
    """Verify CI pipeline security enforcement."""

    def test_bandit_not_suppressed(self, project_root: Path):
        """Bandit scan must not be silenced with || true."""
        ci = (project_root / ".github" / "workflows" / "ci.yml").read_text()
        # Find the bandit step and check it doesn't end with || true
        assert "bandit" in ci.lower()
        # The Bandit run command should not have || true
        lines = ci.split("\n")
        in_bandit = False
        for line in lines:
            if "Bandit security scan" in line:
                in_bandit = True
            if in_bandit and "|| true" in line:
                pytest.fail("Bandit step uses '|| true' which suppresses security failures")
            if in_bandit and line.strip().startswith("- name:") and "Bandit" not in line:
                break

    def test_gitleaks_not_continue_on_error(self, project_root: Path):
        """Gitleaks must block the pipeline on failure."""
        ci = (project_root / ".github" / "workflows" / "ci.yml").read_text()
        # Find gitleaks section and check no continue-on-error
        lines = ci.split("\n")
        in_gitleaks = False
        for line in lines:
            if "Gitleaks" in line:
                in_gitleaks = True
            if in_gitleaks and "continue-on-error: true" in line:
                pytest.fail("Gitleaks step uses continue-on-error which suppresses failures")
            if in_gitleaks and line.strip().startswith("- name:") and "Gitleaks" not in line:
                break


class TestGCSTerraform:
    """Verify GCS Terraform security."""

    def test_public_access_prevention(self, project_root: Path):
        """GCS bucket must enforce public access prevention."""
        tf = (project_root / "infra" / "modules" / "gcs" / "main.tf").read_text()
        assert "public_access_prevention" in tf
        assert '"enforced"' in tf


class TestSecretsYaml:
    """Verify centralized secrets configuration."""

    def test_all_required_keys_present(self, project_root: Path):
        """secrets.yaml must have all required credential keys."""
        manifest = (project_root / "k8s" / "secrets.yaml").read_text()
        secrets = yaml.safe_load(manifest)
        required_keys = [
            "postgres-password",
            "airflow-admin-password",
            "airflow-secret-key",
            "airflow-db-conn",
            "airflow-postgres-password",
            "grafana-admin-password",
            "superset-admin-password",
            "superset-secret-key",
        ]
        for key in required_keys:
            assert key in secrets["stringData"], f"Missing secret key: {key}"

    def test_no_real_passwords_committed(self, project_root: Path):
        """secrets.yaml must contain only placeholder values."""
        manifest = (project_root / "k8s" / "secrets.yaml").read_text()
        secrets = yaml.safe_load(manifest)
        for key, value in secrets["stringData"].items():
            assert "REPLACE_WITH" in value or "REPLACE" in value, (
                f"Secret '{key}' may contain a real password (expected placeholder)"
            )


class TestDependencyPinning:
    """Verify dependency versions are pinned."""

    def test_requirements_pinned(self, project_root: Path):
        """All dependencies in requirements.txt must use exact pins (==)."""
        requirements = (project_root / "requirements.txt").read_text()
        for line in requirements.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            assert "==" in line, f"Dependency not pinned: {line}"
            assert ">=" not in line, f"Dependency uses >= instead of ==: {line}"
