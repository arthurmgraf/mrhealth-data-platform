"""
MR. HEALTH - Secret Manager Setup for PostgreSQL Integration

Cria os secrets necessários no GCP Secret Manager para a Cloud Function
pg-reference-extractor acessar o PostgreSQL no K3s via SSH tunnel.

Uso:
    python scripts/setup_pg_secrets.py --project $GCP_PROJECT_ID

Secrets criados:
    - pg-host:            IP do servidor K3s
    - pg-ssh-user:        Usuário SSH
    - pg-ssh-private-key: Chave SSH privada (PEM)
    - pg-db-name:         Nome do banco PostgreSQL
    - pg-db-user:         Usuário PostgreSQL (mrh_extractor)
    - pg-db-password:     Senha do PostgreSQL
"""

import argparse
import sys

from google.cloud import secretmanager


SECRETS = [
    ("pg-host", "IP ou hostname do servidor K3s"),
    ("pg-ssh-user", "Usuário SSH para acesso ao K3s"),
    ("pg-ssh-private-key", "Chave SSH privada (cole o conteúdo PEM completo)"),
    ("pg-db-name", "Nome do banco PostgreSQL (default: mrhealth)"),
    ("pg-db-user", "Usuário PostgreSQL (default: mrh_extractor)"),
    ("pg-db-password", "Senha do usuário PostgreSQL"),
]


def create_or_update_secret(
    client: secretmanager.SecretManagerServiceClient,
    project_id: str,
    secret_id: str,
    secret_value: str,
) -> None:
    parent = f"projects/{project_id}"
    secret_path = f"{parent}/secrets/{secret_id}"

    try:
        client.get_secret(request={"name": secret_path})
        print(f"  [EXISTS] {secret_id}")
    except Exception:
        client.create_secret(
            request={
                "parent": parent,
                "secret_id": secret_id,
                "secret": {"replication": {"automatic": {}}},
            }
        )
        print(f"  [CREATED] {secret_id}")

    client.add_secret_version(
        request={
            "parent": secret_path,
            "payload": {"data": secret_value.encode("UTF-8")},
        }
    )
    print(f"  [OK] {secret_id} → new version added")


def read_multiline_input(prompt: str) -> str:
    print(f"  {prompt}")
    print("  (Cole o conteúdo e pressione Enter duas vezes para finalizar)")
    lines = []
    empty_count = 0
    while True:
        line = input()
        if line == "":
            empty_count += 1
            if empty_count >= 2:
                break
            lines.append(line)
        else:
            empty_count = 0
            lines.append(line)
    return "\n".join(lines).strip()


def main():
    parser = argparse.ArgumentParser(
        description="MR. HEALTH - Setup Secret Manager for PostgreSQL integration"
    )
    parser.add_argument("--project", required=True, help="GCP project ID")
    args = parser.parse_args()

    print("=" * 60)
    print("MR. HEALTH - Secret Manager Setup")
    print("=" * 60)
    print(f"  Project: {args.project}")
    print(f"  Secrets: {len(SECRETS)}")
    print()

    client = secretmanager.SecretManagerServiceClient()

    for secret_id, description in SECRETS:
        print(f"\n--- {secret_id} ---")
        if secret_id == "pg-ssh-private-key":
            value = read_multiline_input(description)
        else:
            value = input(f"  {description}: ").strip()

        if not value:
            print(f"  [SKIP] {secret_id} (vazio)")
            continue

        create_or_update_secret(client, args.project, secret_id, value)

    print()
    print("=" * 60)
    print("[DONE] Secret Manager configurado com sucesso")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
