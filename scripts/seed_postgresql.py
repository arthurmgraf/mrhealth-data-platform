"""
MR. HEALTH - PostgreSQL Reference Data Seeder

Popula o PostgreSQL no K3s com dados de referência a partir dos CSVs
existentes em output/reference_data/.

Uso:
    python scripts/seed_postgresql.py --host <k3s-ip> --password <admin-password>
    python scripts/seed_postgresql.py --host 127.0.0.1 --port 5432 --password mypass

Pré-requisitos:
    - PostgreSQL rodando no K3s com tabelas criadas (via configmap init)
    - CSVs de referência em output/reference_data/
    - pip install psycopg2-binary
"""

import argparse
import csv
import sys
from pathlib import Path

import psycopg2

REFERENCE_DIR = Path(__file__).parent.parent / "output" / "reference_data"

# Ordem respeita foreign keys: pais → estado → unidade → produto
TABLE_CONFIG = [
    {
        "csv": "pais.csv",
        "table": "pais",
        "insert": "INSERT INTO pais (id_pais, nome_pais) VALUES (%s, %s) ON CONFLICT (id_pais) DO NOTHING",
        "fields": ["Id_Pais", "Nome_Pais"],
    },
    {
        "csv": "estado.csv",
        "table": "estado",
        "insert": "INSERT INTO estado (id_estado, id_pais, nome_estado) VALUES (%s, %s, %s) ON CONFLICT (id_estado) DO NOTHING",
        "fields": ["Id_Estado", "Id_Pais", "Nome_Estado"],
    },
    {
        "csv": "unidade.csv",
        "table": "unidade",
        "insert": "INSERT INTO unidade (id_unidade, nome_unidade, id_estado) VALUES (%s, %s, %s) ON CONFLICT (id_unidade) DO NOTHING",
        "fields": ["Id_Unidade", "Nome_Unidade", "Id_Estado"],
    },
    {
        "csv": "produto.csv",
        "table": "produto",
        "insert": "INSERT INTO produto (id_produto, nome_produto) VALUES (%s, %s) ON CONFLICT (id_produto) DO NOTHING",
        "fields": ["Id_Produto", "Nome_Produto"],
    },
]


def load_csv(filepath: Path, delimiter: str = ";") -> list[dict]:
    with open(filepath, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        return list(reader)


def seed_table(cursor, config: dict, rows: list[dict]) -> int:
    count = 0
    for row in rows:
        values = [row[field] for field in config["fields"]]
        cursor.execute(config["insert"], values)
        count += 1
    return count


def verify_counts(cursor) -> dict:
    tables = ["pais", "estado", "unidade", "produto"]
    counts = {}
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        counts[table] = cursor.fetchone()[0]
    return counts


def main():
    parser = argparse.ArgumentParser(
        description="MR. HEALTH - Seed PostgreSQL with reference data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Via port-forward do K3s
  python scripts/seed_postgresql.py --host 127.0.0.1 --password mypass

  # Direto no servidor K3s
  python scripts/seed_postgresql.py --host <YOUR-K3S-IP> --password <YOUR-PASSWORD>
        """,
    )
    parser.add_argument("--host", required=True, help="PostgreSQL host")
    parser.add_argument("--port", type=int, default=5432, help="PostgreSQL port (default: 5432)")
    parser.add_argument("--database", default="mrhealth", help="Database name (default: mrhealth)")
    parser.add_argument(
        "--user", default="mrhealth_admin", help="PostgreSQL user (default: mrhealth_admin)"
    )
    parser.add_argument("--password", required=True, help="PostgreSQL password")
    args = parser.parse_args()

    print("=" * 60)
    print("MR. HEALTH - PostgreSQL Reference Data Seeder")
    print("=" * 60)
    print(f"  Host:     {args.host}:{args.port}")
    print(f"  Database: {args.database}")
    print(f"  User:     {args.user}")
    print(f"  Source:   {REFERENCE_DIR}")
    print()

    if not REFERENCE_DIR.exists():
        print(f"[ERROR] Reference data directory not found: {REFERENCE_DIR}")
        print("[HINT]  Run: python scripts/generate_fake_sales.py first")
        return 1

    try:
        conn = psycopg2.connect(
            host=args.host,
            port=args.port,
            database=args.database,
            user=args.user,
            password=args.password,
            connect_timeout=15,
        )
    except psycopg2.OperationalError as e:
        print(f"[ERROR] Failed to connect to PostgreSQL: {e}")
        return 1

    cursor = conn.cursor()

    print("[STEP 1] Seeding reference tables...")
    total_rows = 0
    for config in TABLE_CONFIG:
        filepath = REFERENCE_DIR / config["csv"]
        if not filepath.exists():
            print(f"  [ERROR] File not found: {filepath}")
            continue

        rows = load_csv(filepath)
        count = seed_table(cursor, config, rows)
        total_rows += count
        print(f"  [OK] {config['table']:12} {count:>4} rows inserted")

    conn.commit()

    print()
    print("[STEP 2] Verifying row counts...")
    counts = verify_counts(cursor)
    for table, count in counts.items():
        print(f"  {table:12} {count:>4} rows")

    cursor.close()
    conn.close()

    print()
    print("=" * 60)
    print(f"[DONE] {total_rows} total rows seeded successfully")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
