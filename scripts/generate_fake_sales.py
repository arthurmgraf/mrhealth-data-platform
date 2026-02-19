#!/usr/bin/env python3
"""
Case Fictício - Teste -- Fake Sales Data Generator
========================================

Generates realistic fake data for the Case Fictício - Teste data platform MVP.
Produces CSV files matching the schema defined in case_CaseFicticio.md:
  - pedido.csv (ORDER.CSV): Sales orders per unit per day
  - item_pedido.csv (ORDER_ITEM.CSV): Order line items
  - produto.csv: Product catalog (reference)
  - unidade.csv: Unit/restaurant list (reference)
  - estado.csv: States (reference)
  - pais.csv: Countries (reference)

Usage:
    python generate_fake_sales.py
    python generate_fake_sales.py --units 5 --days 7 --min-orders 5 --max-orders 10
    python generate_fake_sales.py --start-date 2026-01-01 --end-date 2026-01-31
    python generate_fake_sales.py --output-dir ./test_data --seed 42

Author: Arthur Graf -- Case Fictício - Teste Project
Date: January 2026
"""

import argparse
import os
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from faker import Faker

# ============================================================================
# CONSTANTS -- Product Catalog (Health/Slow-Food themed)
# ============================================================================

PRODUCT_CATALOG = [
    {"id": 1, "name": "Bowl de Acai Premium", "price": 28.90},
    {"id": 2, "name": "Salada Caesar Grelhada", "price": 32.50},
    {"id": 3, "name": "Wrap Integral de Frango", "price": 26.90},
    {"id": 4, "name": "Suco Verde Detox", "price": 14.90},
    {"id": 5, "name": "Smoothie de Frutas Vermelhas", "price": 18.50},
    {"id": 6, "name": "Poke Bowl Salmao", "price": 42.90},
    {"id": 7, "name": "Sanduiche Natural Integral", "price": 22.90},
    {"id": 8, "name": "Tapioca Fit Recheada", "price": 19.90},
    {"id": 9, "name": "Sopa de Legumes Organica", "price": 24.50},
    {"id": 10, "name": "Omelete de Claras", "price": 21.90},
    {"id": 11, "name": "Granola Bowl com Iogurte", "price": 23.50},
    {"id": 12, "name": "Hamburguer de Grao de Bico", "price": 34.90},
    {"id": 13, "name": "Crepioca Proteica", "price": 20.90},
    {"id": 14, "name": "Agua de Coco Natural", "price": 8.90},
    {"id": 15, "name": "Cha Gelado Funcional", "price": 12.50},
    {"id": 16, "name": "Panqueca de Banana Fit", "price": 19.90},
    {"id": 17, "name": "Cuscuz Nordestino Light", "price": 18.50},
    {"id": 18, "name": "Pasta de Amendoim Artesanal", "price": 15.90},
    {"id": 19, "name": "Mix de Castanhas Premium", "price": 22.90},
    {"id": 20, "name": "Biscoito de Arroz Integral", "price": 9.90},
    {"id": 21, "name": "Iogurte Grego Natural", "price": 13.50},
    {"id": 22, "name": "Barra de Proteina Caseira", "price": 11.90},
    {"id": 23, "name": "Risoto de Quinoa", "price": 36.90},
    {"id": 24, "name": "Frango Grelhado com Legumes", "price": 38.50},
    {"id": 25, "name": "Salmao ao Molho de Maracuja", "price": 52.90},
    {"id": 26, "name": "Espaguete de Abobrinha", "price": 29.90},
    {"id": 27, "name": "Torta Salgada Integral", "price": 16.90},
    {"id": 28, "name": "Vitamina de Abacate Proteica", "price": 17.50},
    {"id": 29, "name": "Brigadeiro Fit de Cacau", "price": 7.90},
    {"id": 30, "name": "Pudim de Chia com Manga", "price": 14.90},
]

# Southern Brazil states (where Case Fictício - Teste operates)
STATES = [
    {"id": 1, "name": "Rio Grande do Sul", "country_id": 1},
    {"id": 2, "name": "Santa Catarina", "country_id": 1},
    {"id": 3, "name": "Parana", "country_id": 1},
]

COUNTRIES = [
    {"id": 1, "name": "Brasil"},
]

# City pools per state for realistic unit names
CITIES_BY_STATE = {
    1: [  # RS
        "Porto Alegre",
        "Caxias do Sul",
        "Pelotas",
        "Canoas",
        "Santa Maria",
        "Gravatai",
        "Viamao",
        "Novo Hamburgo",
        "Sao Leopoldo",
        "Rio Grande",
        "Alvorada",
        "Passo Fundo",
        "Sapucaia do Sul",
        "Uruguaiana",
        "Santa Cruz do Sul",
        "Cachoeirinha",
        "Bage",
        "Bento Goncalves",
        "Erechim",
        "Guaiba",
    ],
    2: [  # SC
        "Florianopolis",
        "Joinville",
        "Blumenau",
        "Sao Jose",
        "Chapeco",
        "Criciuma",
        "Itajai",
        "Jaragua do Sul",
        "Lages",
        "Palhoca",
        "Balneario Camboriu",
        "Brusque",
        "Tubarao",
        "Sao Bento do Sul",
        "Cacador",
    ],
    3: [  # PR
        "Curitiba",
        "Londrina",
        "Maringa",
        "Ponta Grossa",
        "Cascavel",
        "Sao Jose dos Pinhais",
        "Foz do Iguacu",
        "Colombo",
        "Guarapuava",
        "Paranagua",
        "Araucaria",
        "Toledo",
        "Apucarana",
        "Pinhais",
        "Campo Largo",
    ],
}

# Observation templates for order items
OBSERVATIONS = [
    "Sem gluten",
    "Extra proteina",
    "Sem lactose",
    "Sem acucar",
    "Ponto especial",
    "Dobro de molho",
    "Sem cebola",
    "Bem passado",
    "Ao ponto",
    "Sem sal",
    "Porção extra",
    "Sem pimenta",
    "Com molho a parte",
    "Vegano",
    "Sem conservantes",
]

# Status distribution weights
STATUS_CHOICES = ["Finalizado", "Pendente", "Cancelado"]
STATUS_WEIGHTS = [0.85, 0.10, 0.05]

# Order type distribution weights
ORDER_TYPE_CHOICES = ["Loja Online", "Loja Fisica"]
ORDER_TYPE_WEIGHTS = [0.60, 0.40]


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def generate_unit_list(num_units: int) -> list[dict]:
    """Generate a list of restaurant units distributed across southern Brazil states."""
    units = []
    # Distribute units across states: 40% RS, 35% SC, 25% PR
    state_distribution = {1: 0.40, 2: 0.35, 3: 0.25}

    unit_id = 1
    for state_id, ratio in state_distribution.items():
        count = max(1, round(num_units * ratio))
        cities = CITIES_BY_STATE[state_id]
        for i in range(count):
            if unit_id > num_units:
                break
            city = cities[i % len(cities)]
            units.append(
                {
                    "id": unit_id,
                    "name": f"Mr. Health - {city}",
                    "state_id": state_id,
                }
            )
            unit_id += 1

    # Ensure we have exactly num_units
    while len(units) < num_units:
        state_id = random.choice([1, 2, 3])
        city = random.choice(CITIES_BY_STATE[state_id])
        units.append(
            {
                "id": len(units) + 1,
                "name": f"Mr. Health - {city} II",
                "state_id": state_id,
            }
        )

    return units[:num_units]


def generate_orders_for_unit_day(
    fake: Faker,
    unit_id: int,
    date: datetime,
    min_orders: int,
    max_orders: int,
) -> tuple[list[dict], list[dict]]:
    """Generate orders and order items for one unit on one day."""
    num_orders = random.randint(min_orders, max_orders)
    orders = []
    items = []

    for _ in range(num_orders):
        order_id = str(uuid.uuid4())
        order_type = random.choices(ORDER_TYPE_CHOICES, weights=ORDER_TYPE_WEIGHTS, k=1)[0]
        status = random.choices(STATUS_CHOICES, weights=STATUS_WEIGHTS, k=1)[0]

        # Generate 1-5 items for this order
        num_items = random.randint(1, 5)
        order_items = []
        total_items_value = 0.0

        for _ in range(num_items):
            product = random.choice(PRODUCT_CATALOG)
            qty = random.randint(1, 3)
            item_value = product["price"]
            total_item = round(qty * item_value, 2)
            total_items_value += total_item

            has_observation = random.random() < 0.30
            observation = random.choice(OBSERVATIONS) if has_observation else ""

            order_items.append(
                {
                    "Id_Pedido": order_id,
                    "Id_Item_Pedido": str(uuid.uuid4()),
                    "Id_Produto": product["id"],
                    "Qtd": qty,
                    "Vlr_Item": f"{item_value:.2f}",
                    "Observacao": observation,
                }
            )

        # Delivery fee: 0.00 for physical, 5.00-25.00 for online
        if order_type == "Loja Online":
            delivery_fee = round(random.uniform(5.00, 25.00), 2)
            delivery_address = fake.address().replace("\n", ", ")
        else:
            delivery_fee = 0.00
            delivery_address = ""

        order_value = round(total_items_value + delivery_fee, 2)

        orders.append(
            {
                "Id_Unidade": unit_id,
                "Id_Pedido": order_id,
                "Tipo_Pedido": order_type,
                "Data_Pedido": date.strftime("%Y-%m-%d"),
                "Vlr_Pedido": f"{order_value:.2f}",
                "Endereco_Entrega": delivery_address,
                "Taxa_Entrega": f"{delivery_fee:.2f}",
                "Status": status,
            }
        )

        items.extend(order_items)

    return orders, items


# ============================================================================
# REFERENCE DATA GENERATORS
# ============================================================================


def generate_reference_data(units: list[dict], output_dir: Path) -> None:
    """Generate all static reference data CSVs."""
    ref_dir = output_dir / "reference_data"
    ref_dir.mkdir(parents=True, exist_ok=True)

    # produto.csv
    df_products = pd.DataFrame(
        [{"Id_Produto": p["id"], "Nome_Produto": p["name"]} for p in PRODUCT_CATALOG]
    )
    df_products.to_csv(ref_dir / "produto.csv", index=False, sep=";", encoding="utf-8")
    print(f"  [OK] produto.csv: {len(df_products)} products")

    # unidade.csv
    df_units = pd.DataFrame(
        [
            {"Id_Unidade": u["id"], "Nome_Unidade": u["name"], "Id_Estado": u["state_id"]}
            for u in units
        ]
    )
    df_units.to_csv(ref_dir / "unidade.csv", index=False, sep=";", encoding="utf-8")
    print(f"  [OK] unidade.csv: {len(df_units)} units")

    # estado.csv
    df_states = pd.DataFrame(
        [
            {"Id_Estado": s["id"], "Id_Pais": s["country_id"], "Nome_Estado": s["name"]}
            for s in STATES
        ]
    )
    df_states.to_csv(ref_dir / "estado.csv", index=False, sep=";", encoding="utf-8")
    print(f"  [OK] estado.csv: {len(df_states)} states")

    # pais.csv
    df_countries = pd.DataFrame([{"Id_Pais": c["id"], "Nome_Pais": c["name"]} for c in COUNTRIES])
    df_countries.to_csv(ref_dir / "pais.csv", index=False, sep=";", encoding="utf-8")
    print(f"  [OK] pais.csv: {len(df_countries)} countries")


# ============================================================================
# MAIN GENERATION LOGIC
# ============================================================================


def generate_sales_data(
    units: list[dict],
    start_date: datetime,
    end_date: datetime,
    min_orders: int,
    max_orders: int,
    output_dir: Path,
    seed: int | None = None,
) -> dict:
    """Generate all sales data (orders + items) for all units across date range."""

    if seed is not None:
        random.seed(seed)
        Faker.seed(seed)

    fake = Faker("pt_BR")
    if seed is not None:
        fake.seed_instance(seed)

    stats = {
        "total_orders": 0,
        "total_items": 0,
        "total_files": 0,
        "units_processed": 0,
        "days_processed": 0,
    }

    current_date = start_date
    dates = []
    while current_date <= end_date:
        dates.append(current_date)
        current_date += timedelta(days=1)

    stats["days_processed"] = len(dates)
    stats["units_processed"] = len(units)

    print("\nGenerating sales data:")
    print(f"  Units: {len(units)}")
    print(f"  Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    print(f"  Days: {len(dates)}")
    print(f"  Orders per unit per day: {min_orders}-{max_orders}")
    print()

    for date in dates:
        year = date.strftime("%Y")
        month = date.strftime("%m")
        day = date.strftime("%d")

        for unit in units:
            unit_id = unit["id"]
            unit_dir = output_dir / "csv_sales" / year / month / day / f"unit_{unit_id:03d}"
            unit_dir.mkdir(parents=True, exist_ok=True)

            orders, items = generate_orders_for_unit_day(
                fake=fake,
                unit_id=unit_id,
                date=date,
                min_orders=min_orders,
                max_orders=max_orders,
            )

            # Write pedido.csv
            df_orders = pd.DataFrame(orders)
            df_orders.to_csv(
                unit_dir / "pedido.csv",
                index=False,
                sep=";",
                encoding="utf-8",
            )

            # Write item_pedido.csv
            df_items = pd.DataFrame(items)
            df_items.to_csv(
                unit_dir / "item_pedido.csv",
                index=False,
                sep=";",
                encoding="utf-8",
            )

            stats["total_orders"] += len(orders)
            stats["total_items"] += len(items)
            stats["total_files"] += 2

        print(f"  [OK] {date.strftime('%Y-%m-%d')}: {len(units)} units processed")

    return stats


def print_summary(stats: dict, output_dir: Path) -> None:
    """Print generation summary."""
    print("\n" + "=" * 60)
    print("GENERATION COMPLETE -- SUMMARY")
    print("=" * 60)
    print(f"  Output directory:  {output_dir.resolve()}")
    print(f"  Units processed:   {stats['units_processed']}")
    print(f"  Days processed:    {stats['days_processed']}")
    print(f"  Total orders:      {stats['total_orders']:,}")
    print(f"  Total items:       {stats['total_items']:,}")
    print(f"  Total CSV files:   {stats['total_files']:,}")
    print()

    # Estimate total size
    total_size = 0
    for root, _dirs, files in os.walk(output_dir):
        for f in files:
            total_size += os.path.getsize(os.path.join(root, f))

    size_mb = total_size / (1024 * 1024)
    print(f"  Total size:        {size_mb:.2f} MB")
    print("  GCS Free Tier:     5,120 MB (5 GB)")
    print(f"  Usage:             {(size_mb / 5120) * 100:.2f}%")
    print("=" * 60)


# ============================================================================
# CLI ENTRY POINT
# ============================================================================


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Case Fictício - Teste Fake Sales Data Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Default: 50 units, 30 days, 10-50 orders/unit/day
  python generate_fake_sales.py

  # Quick test: 5 units, 3 days
  python generate_fake_sales.py --units 5 --days 3 --min-orders 5 --max-orders 10

  # Specific date range
  python generate_fake_sales.py --start-date 2026-01-01 --end-date 2026-01-31

  # Reproducible output
  python generate_fake_sales.py --seed 42
        """,
    )

    parser.add_argument(
        "--units",
        type=int,
        default=50,
        help="Number of restaurant units (default: 50)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days to generate (default: 30, ignored if --start-date/--end-date set)",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="Start date in YYYY-MM-DD format (default: 30 days ago)",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        help="End date in YYYY-MM-DD format (default: yesterday)",
    )
    parser.add_argument(
        "--min-orders",
        type=int,
        default=10,
        help="Minimum orders per unit per day (default: 10)",
    )
    parser.add_argument(
        "--max-orders",
        type=int,
        default=50,
        help="Maximum orders per unit per day (default: 50)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="output",
        help="Output directory (default: ./output)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducible output (default: None)",
    )

    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    args = parse_args()

    print("=" * 60)
    print("Case Fictício - Teste -- Fake Sales Data Generator")
    print("=" * 60)

    # Resolve dates
    if args.start_date and args.end_date:
        start_date = datetime.strptime(args.start_date, "%Y-%m-%d")
        end_date = datetime.strptime(args.end_date, "%Y-%m-%d")
    else:
        end_date = datetime.now() - timedelta(days=1)
        start_date = end_date - timedelta(days=args.days - 1)

    output_dir = Path(args.output_dir)

    # Generate unit list
    units = generate_unit_list(args.units)

    # Generate reference data
    print("\nGenerating reference data:")
    generate_reference_data(units, output_dir)

    # Generate sales data
    stats = generate_sales_data(
        units=units,
        start_date=start_date,
        end_date=end_date,
        min_orders=args.min_orders,
        max_orders=args.max_orders,
        output_dir=output_dir,
        seed=args.seed,
    )

    # Print summary
    print_summary(stats, output_dir)


if __name__ == "__main__":
    main()
