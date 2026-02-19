"""Shared constants for MR. HEALTH data generation.

Consolidates the product catalog, status/order-type choices, observations,
geographic data, and reference tables that were duplicated between:
  - scripts/generate_fake_sales.py
  - cloud_functions/data_generator/main.py

Both files had identical copies of PRODUCT_CATALOG, STATUS_CHOICES,
ORDER_TYPE_CHOICES, OBSERVATIONS, and CITIES_BY_STATE. This module
provides the single source of truth.

Note: cloud_functions/data_generator/main.py runs on GCP Cloud Functions
and may not be able to import from scripts/ directly. In that case, keep
a copy there but reference this file as the canonical source for updates.
"""

from __future__ import annotations

# ============================================================================
# Product Catalog (Health/Slow-Food themed -- MR. HEALTH brand)
# ============================================================================

PRODUCT_CATALOG: list[dict[str, str | int | float]] = [
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

# ============================================================================
# Reference Data (Southern Brazil -- where MR. HEALTH operates)
# ============================================================================

STATES: list[dict[str, str | int]] = [
    {"id": 1, "name": "Rio Grande do Sul", "country_id": 1},
    {"id": 2, "name": "Santa Catarina", "country_id": 1},
    {"id": 3, "name": "Parana", "country_id": 1},
]

COUNTRIES: list[dict[str, str | int]] = [
    {"id": 1, "name": "Brasil"},
]

# ============================================================================
# Geographic Distribution (cities per state by integer state ID)
# ============================================================================

CITIES_BY_STATE: dict[int, list[str]] = {
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

# ============================================================================
# Order Status Choices (weighted distribution)
# ============================================================================

STATUS_CHOICES: list[str] = ["Finalizado", "Pendente", "Cancelado"]
STATUS_WEIGHTS: list[float] = [0.85, 0.10, 0.05]

# ============================================================================
# Order Type Choices (weighted distribution)
# ============================================================================

ORDER_TYPE_CHOICES: list[str] = ["Loja Online", "Loja Fisica"]
ORDER_TYPE_WEIGHTS: list[float] = [0.60, 0.40]

# ============================================================================
# Item Observations (used with ~30% probability per order item)
# ============================================================================

OBSERVATIONS: list[str] = [
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
