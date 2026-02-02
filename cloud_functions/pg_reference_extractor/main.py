"""
Cloud Function: pg-reference-extractor

Extrai tabelas de referência do PostgreSQL da matriz (hospedado em K3s)
via SSH tunnel e deposita como CSVs no GCS para o pipeline Medallion processar.

Trigger: HTTP (invocado pelo Cloud Scheduler diariamente às 01:00)
Runtime: Python 3.11, 256MB, timeout 300s
"""

import io
import json
import os
import time
import uuid
from datetime import datetime, timezone

import functions_framework
import paramiko
import psycopg2
from google.cloud import secretmanager, storage
from sshtunnel import SSHTunnelForwarder


# --- Configuração ---
PROJECT_ID = os.environ.get("PROJECT_ID", "sixth-foundry-485810-e5")
BUCKET_NAME = os.environ.get("BUCKET_NAME", "mrhealth-datalake-485810")
GCS_PREFIX = os.environ.get("GCS_PREFIX", "raw/reference_data")

TABLES = {
    "produto": {
        "query": "SELECT id_produto, nome_produto FROM produto ORDER BY id_produto",
        "csv_name": "produto.csv",
        "header": "Id_Produto;Nome_Produto",
    },
    "unidade": {
        "query": "SELECT id_unidade, nome_unidade, id_estado FROM unidade ORDER BY id_unidade",
        "csv_name": "unidade.csv",
        "header": "Id_Unidade;Nome_Unidade;Id_Estado",
    },
    "estado": {
        "query": "SELECT id_estado, id_pais, nome_estado FROM estado ORDER BY id_estado",
        "csv_name": "estado.csv",
        "header": "Id_Estado;Id_Pais;Nome_Estado",
    },
    "pais": {
        "query": "SELECT id_pais, nome_pais FROM pais ORDER BY id_pais",
        "csv_name": "pais.csv",
        "header": "Id_Pais;Nome_Pais",
    },
}

MAX_RETRIES = 3
RETRY_DELAYS = [30, 60, 120]
SSH_TIMEOUT = 30
PG_CONNECT_TIMEOUT = 15
PG_NODE_PORT = 30432


def get_secret(client: secretmanager.SecretManagerServiceClient, secret_id: str) -> str:
    name = f"projects/{PROJECT_ID}/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")


def get_all_secrets(client: secretmanager.SecretManagerServiceClient) -> dict:
    return {
        "ssh_host": get_secret(client, "pg-host"),
        "ssh_user": get_secret(client, "pg-ssh-user"),
        "ssh_key": get_secret(client, "pg-ssh-private-key"),
        "pg_db": get_secret(client, "pg-db-name"),
        "pg_user": get_secret(client, "pg-db-user"),
        "pg_pass": get_secret(client, "pg-db-password"),
    }


def load_ssh_key(key_pem: str) -> paramiko.PKey:
    key_file = io.StringIO(key_pem)
    for key_class in (paramiko.Ed25519Key, paramiko.RSAKey, paramiko.ECDSAKey):
        try:
            key_file.seek(0)
            return key_class.from_private_key(key_file)
        except (paramiko.SSHException, ValueError):
            continue
    raise ValueError("Unsupported SSH key type. Supported: Ed25519, RSA, ECDSA")


def extract_table(cursor, table_config: dict) -> tuple[str, int]:
    cursor.execute(table_config["query"])
    rows = cursor.fetchall()

    if not rows:
        return "", 0

    csv_lines = [table_config["header"]]
    for row in rows:
        csv_lines.append(";".join(str(val) for val in row))

    csv_content = "\n".join(csv_lines) + "\n"
    return csv_content, len(rows)


def upload_to_gcs(bucket, csv_content: str, csv_name: str) -> None:
    blob_name = f"{GCS_PREFIX}/{csv_name}"
    blob = bucket.blob(blob_name)
    blob.upload_from_string(csv_content, content_type="text/csv; charset=utf-8")


def check_existing_file(bucket, csv_name: str) -> bool:
    blob_name = f"{GCS_PREFIX}/{csv_name}"
    blob = bucket.blob(blob_name)
    return blob.exists()


def extract_with_retry(secrets: dict) -> dict:
    results = {}
    pkey = load_ssh_key(secrets["ssh_key"])

    for attempt in range(MAX_RETRIES):
        try:
            with SSHTunnelForwarder(
                (secrets["ssh_host"], 22),
                ssh_username=secrets["ssh_user"],
                ssh_pkey=pkey,
                remote_bind_address=("127.0.0.1", PG_NODE_PORT),
                local_bind_address=("127.0.0.1",),
            ) as tunnel:
                print(f"  [OK] SSH tunnel: {secrets['ssh_host']}:{PG_NODE_PORT} -> localhost:{tunnel.local_bind_port}")

                conn = psycopg2.connect(
                    host="127.0.0.1",
                    port=tunnel.local_bind_port,
                    database=secrets["pg_db"],
                    user=secrets["pg_user"],
                    password=secrets["pg_pass"],
                    connect_timeout=PG_CONNECT_TIMEOUT,
                )
                cursor = conn.cursor()
                print(f"  [OK] Connected to PostgreSQL ({secrets['pg_db']})")

                storage_client = storage.Client(project=PROJECT_ID)
                bucket = storage_client.bucket(BUCKET_NAME)

                for table_name, config in TABLES.items():
                    csv_content, row_count = extract_table(cursor, config)

                    if row_count == 0:
                        print(f"  [WARN] Empty table detected: {table_name}")
                        if check_existing_file(bucket, config["csv_name"]):
                            print(f"  [SKIP] Preserving existing {config['csv_name']}")
                        results[table_name] = {"status": "skipped", "rows": 0}
                        continue

                    upload_to_gcs(bucket, csv_content, config["csv_name"])
                    print(f"  [OK] {table_name}: {row_count} rows -> {config['csv_name']}")
                    results[table_name] = {"status": "success", "rows": row_count}

                cursor.close()
                conn.close()
                print(f"  [OK] Connections closed")

            return results

        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAYS[attempt]
                print(f"  [RETRY] Attempt {attempt + 1} failed: {e}")
                print(f"  [RETRY] Waiting {delay}s before retry...")
                time.sleep(delay)
            else:
                raise

    return results


@functions_framework.http
def extract_reference_data(request):
    extraction_id = str(uuid.uuid4())[:8]
    start_time = datetime.now(timezone.utc)

    print(f"[START] Extraction {extraction_id} at {start_time.isoformat()}")

    try:
        sm_client = secretmanager.SecretManagerServiceClient()
        secrets = get_all_secrets(sm_client)
        print(f"  [OK] Credentials loaded from Secret Manager")

        results = extract_with_retry(secrets)

    except Exception as e:
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        error_log = {
            "extraction_id": extraction_id,
            "status": "error",
            "error": str(e),
            "duration_seconds": round(duration, 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        print(f"[ERROR] {json.dumps(error_log)}")
        return json.dumps(error_log), 500

    duration = (datetime.now(timezone.utc) - start_time).total_seconds()
    total_rows = sum(r["rows"] for r in results.values())

    success_log = {
        "extraction_id": extraction_id,
        "status": "success",
        "tables_extracted": [t for t, r in results.items() if r["status"] == "success"],
        "tables_skipped": [t for t, r in results.items() if r["status"] == "skipped"],
        "total_rows": total_rows,
        "duration_seconds": round(duration, 2),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    print(f"[DONE] {json.dumps(success_log)}")

    return json.dumps(success_log), 200
