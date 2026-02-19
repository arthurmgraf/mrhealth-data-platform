"""
MR. HEALTH Data Platform -- Data Generator Cloud Function
=========================================================

HTTP Cloud Function triggered by Cloud Scheduler.
Generates incremental sales data for a 2-hour business window
and uploads CSVs to GCS, triggering the csv-processor pipeline.

Flow:
    Cloud Scheduler (7x/day) -> HTTP POST -> this function
      -> Detect current BRT window
      -> Generate orders for all 50 units
      -> Upload CSVs to GCS raw/csv_sales/
      -> csv-processor triggers automatically (Eventarc)

Author: Arthur Graf
Date: February 2026
"""

import os
import random
import uuid
from datetime import datetime, timedelta, timezone

import functions_framework
import pandas as pd
from faker import Faker
from google.cloud import storage

# ============================================================================
# CONFIGURATION
# ============================================================================

PROJECT = os.environ["PROJECT_ID"]
BUCKET = os.environ["BUCKET_NAME"]
NUM_UNITS = int(os.environ.get("NUM_UNITS", "50"))

BRT = timezone(timedelta(hours=-3))

# Business window -> (min_orders, max_orders) per unit
# Key = hour when Cloud Scheduler fires; window covers [hour, hour+2)
WINDOW_VOLUMES = {
    10: (1, 2),  # 10-12: Morning ramp-up (brunch)
    12: (3, 5),  # 12-14: Lunch peak
    14: (1, 2),  # 14-16: Afternoon lull
    16: (2, 3),  # 16-18: Late afternoon
    18: (4, 6),  # 18-20: Dinner peak
    20: (2, 3),  # 20-22: Evening wind-down
    22: (2, 3),  # 22-00: Late evening
}


# ============================================================================
# PRODUCT CATALOG (mirrors generate_fake_sales.py -- see ADR-1)
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

STATUS_CHOICES = ["Finalizado", "Pendente", "Cancelado"]
STATUS_WEIGHTS = [0.85, 0.10, 0.05]

ORDER_TYPE_CHOICES = ["Loja Online", "Loja Fisica"]
ORDER_TYPE_WEIGHTS = [0.60, 0.40]

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
    "Porcao extra",
    "Sem pimenta",
    "Com molho a parte",
    "Vegano",
    "Sem conservantes",
]

# Southern Brazil state -> city mapping
CITIES_BY_STATE = {
    1: [
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
    2: [
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
    3: [
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


# ============================================================================
# GENERATION LOGIC (mirrors generate_fake_sales.py -- see ADR-1)
# ============================================================================


def generate_unit_list(num_units: int) -> list[dict]:
    """Generate restaurant units distributed across southern Brazil."""
    units = []
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


def generate_orders_for_unit(
    fake: Faker,
    unit_id: int,
    date: datetime,
    min_orders: int,
    max_orders: int,
) -> tuple[list[dict], list[dict]]:
    """Generate orders and order items for one unit in one window."""
    num_orders = random.randint(min_orders, max_orders)
    orders = []
    items = []
    for _ in range(num_orders):
        order_id = str(uuid.uuid4())
        order_type = random.choices(ORDER_TYPE_CHOICES, weights=ORDER_TYPE_WEIGHTS, k=1)[0]
        status = random.choices(STATUS_CHOICES, weights=STATUS_WEIGHTS, k=1)[0]
        num_items = random.randint(1, 5)
        total_items_value = 0.0
        for _ in range(num_items):
            product = random.choice(PRODUCT_CATALOG)
            qty = random.randint(1, 3)
            item_value = product["price"]
            total_item = round(qty * item_value, 2)
            total_items_value += total_item
            items.append(
                {
                    "Id_Pedido": order_id,
                    "Id_Item_Pedido": str(uuid.uuid4()),
                    "Id_Produto": product["id"],
                    "Qtd": qty,
                    "Vlr_Item": f"{item_value:.2f}",
                    "Observacao": random.choice(OBSERVATIONS) if random.random() < 0.30 else "",
                }
            )
        if order_type == "Loja Online":
            delivery_fee = round(random.uniform(5.00, 25.00), 2)
            delivery_address = fake.address().replace("\n", ", ")
        else:
            delivery_fee = 0.00
            delivery_address = ""
        orders.append(
            {
                "Id_Unidade": unit_id,
                "Id_Pedido": order_id,
                "Tipo_Pedido": order_type,
                "Data_Pedido": date.strftime("%Y-%m-%d"),
                "Vlr_Pedido": f"{round(total_items_value + delivery_fee, 2):.2f}",
                "Endereco_Entrega": delivery_address,
                "Taxa_Entrega": f"{delivery_fee:.2f}",
                "Status": status,
            }
        )
    return orders, items


# ============================================================================
# GCS UPLOAD
# ============================================================================


def upload_csv_to_gcs(bucket, blob_name: str, df: pd.DataFrame) -> None:
    """Upload a DataFrame as CSV directly to GCS (no local file)."""
    csv_content = df.to_csv(index=False, sep=";", encoding="utf-8")
    blob = bucket.blob(blob_name)
    blob.upload_from_string(csv_content, content_type="text/csv")


# ============================================================================
# CLOUD FUNCTION ENTRY POINT
# ============================================================================


@functions_framework.http
def generate_data(request):
    """HTTP Cloud Function entry point. Triggered by Cloud Scheduler."""
    now = datetime.now(BRT)
    window_hour = now.hour

    # Validate: only generate during business windows
    if window_hour not in WINDOW_VOLUMES:
        msg = f"Hour {window_hour} is outside business windows (10-22 even hours)"
        print(f"[SKIP] {msg}")
        return {"status": "skipped", "reason": msg}, 200

    min_orders, max_orders = WINDOW_VOLUMES[window_hour]
    window_end = window_hour + 2
    window_tag = f"window_{window_hour:02d}{window_end:02d}"

    date_str = now.strftime("%Y-%m-%d")
    year = now.strftime("%Y")
    month = now.strftime("%m")
    day = now.strftime("%d")

    print(f"[START] Window: {window_hour}:00-{window_end}:00 | Date: {date_str}")
    print(f"[CONFIG] Units: {NUM_UNITS} | Volume: {min_orders}-{max_orders} orders/unit")

    fake = Faker("pt_BR")
    units = generate_unit_list(NUM_UNITS)

    storage_client = storage.Client(project=PROJECT)
    bucket = storage_client.bucket(BUCKET)

    total_orders = 0
    total_items = 0
    files_uploaded = 0

    for unit in units:
        orders, items = generate_orders_for_unit(
            fake=fake,
            unit_id=unit["id"],
            date=now,
            min_orders=min_orders,
            max_orders=max_orders,
        )

        prefix = f"raw/csv_sales/{year}/{month}/{day}/unit_{unit['id']:03d}/{window_tag}"
        upload_csv_to_gcs(bucket, f"{prefix}/pedido.csv", pd.DataFrame(orders))
        upload_csv_to_gcs(bucket, f"{prefix}/item_pedido.csv", pd.DataFrame(items))

        total_orders += len(orders)
        total_items += len(items)
        files_uploaded += 2

    summary = {
        "status": "success",
        "window": f"{window_hour:02d}:00-{window_end:02d}:00",
        "date": date_str,
        "units": NUM_UNITS,
        "total_orders": total_orders,
        "total_items": total_items,
        "files_uploaded": files_uploaded,
    }

    print(f"[COMPLETE] {total_orders} orders, {total_items} items, {files_uploaded} files")
    return summary, 200
