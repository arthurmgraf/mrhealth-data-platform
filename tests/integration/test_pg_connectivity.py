"""
Integration tests for PostgreSQL connectivity.

Estes testes requerem acesso real ao servidor K3s e PostgreSQL.
Só são executados quando as variáveis de ambiente estão configuradas.

Uso:
    PG_SSH_HOST=<ip> PG_SSH_USER=<user> PG_SSH_KEY_FILE=<path> \
    PG_DB_NAME=mrhealth PG_DB_USER=mrh_extractor PG_DB_PASSWORD=<pass> \
    pytest tests/integration/ -m integration -v
"""

import io
import os

import pytest


def _skip_if_no_config():
    if not os.environ.get("PG_SSH_HOST"):
        pytest.skip("PG_SSH_HOST not set - skipping integration test")


@pytest.fixture
def ssh_config():
    _skip_if_no_config()
    key_file = os.environ.get("PG_SSH_KEY_FILE", "")
    key_content = ""
    if key_file and os.path.exists(key_file):
        with open(key_file, "r") as f:
            key_content = f.read()
    return {
        "host": os.environ.get("PG_SSH_HOST"),
        "user": os.environ.get("PG_SSH_USER"),
        "key": key_content or os.environ.get("PG_SSH_KEY", ""),
    }


@pytest.fixture
def pg_config():
    _skip_if_no_config()
    return {
        "database": os.environ.get("PG_DB_NAME", "mrhealth"),
        "user": os.environ.get("PG_DB_USER", "mrh_extractor"),
        "password": os.environ.get("PG_DB_PASSWORD", ""),
    }


class TestSSHConnectivity:

    @pytest.mark.integration
    def test_ssh_connection(self, ssh_config):
        import paramiko

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        if ssh_config["key"]:
            pkey = paramiko.RSAKey.from_private_key(io.StringIO(ssh_config["key"]))
            client.connect(
                hostname=ssh_config["host"],
                username=ssh_config["user"],
                pkey=pkey,
                timeout=30,
            )
        else:
            pytest.skip("No SSH key provided")

        stdin, stdout, stderr = client.exec_command("echo ok")
        assert stdout.read().decode().strip() == "ok"
        client.close()

    @pytest.mark.integration
    def test_ssh_pg_port_reachable(self, ssh_config):
        import paramiko

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        pkey = paramiko.RSAKey.from_private_key(io.StringIO(ssh_config["key"]))
        client.connect(
            hostname=ssh_config["host"],
            username=ssh_config["user"],
            pkey=pkey,
            timeout=30,
        )

        stdin, stdout, stderr = client.exec_command(
            "kubectl -n mrhealth-db get pod -l app=postgresql -o jsonpath='{.items[0].status.phase}'"
        )
        phase = stdout.read().decode().strip()
        assert phase == "Running", f"PostgreSQL pod is not running: {phase}"
        client.close()


class TestPostgreSQLData:

    @pytest.mark.integration
    def test_table_row_counts(self, pg_config):
        import psycopg2

        if not pg_config["password"]:
            pytest.skip("PG_DB_PASSWORD not set")

        conn = psycopg2.connect(
            host=os.environ.get("PG_SSH_HOST"),
            port=5432,
            **pg_config,
        )
        cursor = conn.cursor()

        expected = {"produto": 30, "unidade": 3, "estado": 3, "pais": 1}
        for table, expected_count in expected.items():
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            actual = cursor.fetchone()[0]
            assert actual == expected_count, f"{table}: expected {expected_count}, got {actual}"

        cursor.close()
        conn.close()

    @pytest.mark.integration
    def test_readonly_user_cannot_write(self, pg_config):
        import psycopg2

        if not pg_config["password"]:
            pytest.skip("PG_DB_PASSWORD not set")

        conn = psycopg2.connect(
            host=os.environ.get("PG_SSH_HOST"),
            port=5432,
            **pg_config,
        )
        cursor = conn.cursor()

        with pytest.raises(psycopg2.errors.InsufficientPrivilege):
            cursor.execute("INSERT INTO produto (id_produto, nome_produto) VALUES (999, 'Test')")

        conn.rollback()
        cursor.close()
        conn.close()

    @pytest.mark.integration
    def test_referential_integrity(self, pg_config):
        import psycopg2

        if not pg_config["password"]:
            pytest.skip("PG_DB_PASSWORD not set")

        conn = psycopg2.connect(
            host=os.environ.get("PG_SSH_HOST"),
            port=5432,
            **pg_config,
        )
        cursor = conn.cursor()

        cursor.execute("""
            SELECT u.id_unidade, u.nome_unidade
            FROM unidade u
            LEFT JOIN estado e ON u.id_estado = e.id_estado
            WHERE e.id_estado IS NULL
        """)
        orphans = cursor.fetchall()
        assert len(orphans) == 0, f"Orphaned units found: {orphans}"

        cursor.execute("""
            SELECT e.id_estado, e.nome_estado
            FROM estado e
            LEFT JOIN pais p ON e.id_pais = p.id_pais
            WHERE p.id_pais IS NULL
        """)
        orphans = cursor.fetchall()
        assert len(orphans) == 0, f"Orphaned states found: {orphans}"

        cursor.close()
        conn.close()
