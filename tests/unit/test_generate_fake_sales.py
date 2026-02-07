"""Unit tests for the fake data generator (scripts/generate_fake_sales.py).

Tests run locally without GCP dependencies.
"""

import pytest
import pandas as pd
from pathlib import Path
from datetime import datetime
import sys
import os

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'scripts'))

from generate_fake_sales import (
    generate_unit_list,
    generate_orders_for_unit_day,
    generate_reference_data,
    PRODUCT_CATALOG,
    STATUS_CHOICES,
    ORDER_TYPE_CHOICES,
    STATES,
    COUNTRIES,
)
from faker import Faker


class TestUnitList:
    """Tests for unit list generation."""

    def test_default_50_units(self):
        """Test generating default 50 units."""
        units = generate_unit_list(50)
        assert len(units) == 50

    def test_custom_unit_count(self):
        """Test generating custom unit counts."""
        for count in [1, 5, 10, 100]:
            units = generate_unit_list(count)
            assert len(units) == count

    def test_unique_ids(self):
        """Test that all unit IDs are unique."""
        units = generate_unit_list(50)
        ids = [u["id"] for u in units]
        assert len(set(ids)) == 50

    def test_all_units_have_state(self):
        """Test that all units have a valid state ID."""
        units = generate_unit_list(50)
        for unit in units:
            assert unit["state_id"] in [1, 2, 3]

    def test_unit_name_format(self):
        """Test that unit names have correct format."""
        units = generate_unit_list(5)
        for unit in units:
            assert unit["name"].startswith("Mr. Health")


class TestOrderGeneration:
    """Tests for order and item generation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.fake = Faker("pt_BR")
        self.fake.seed_instance(42)
        self.unit_id = 1
        self.date = datetime(2026, 1, 15)

    def test_generates_correct_number_of_orders(self):
        """Test that exact number of orders is generated."""
        orders, items = generate_orders_for_unit_day(
            self.fake, self.unit_id, self.date, min_orders=10, max_orders=10
        )
        assert len(orders) == 10

    def test_order_has_required_fields(self):
        """Test that all orders have required fields."""
        orders, items = generate_orders_for_unit_day(
            self.fake, self.unit_id, self.date, min_orders=1, max_orders=1
        )
        required_fields = [
            "Id_Unidade", "Id_Pedido", "Tipo_Pedido", "Data_Pedido",
            "Vlr_Pedido", "Endereco_Entrega", "Taxa_Entrega", "Status"
        ]
        for field in required_fields:
            assert field in orders[0], f"Missing required field: {field}"

    def test_item_has_required_fields(self):
        """Test that all items have required fields."""
        orders, items = generate_orders_for_unit_day(
            self.fake, self.unit_id, self.date, min_orders=1, max_orders=1
        )
        required_fields = [
            "Id_Pedido", "Id_Item_Pedido", "Id_Produto", "Qtd", "Vlr_Item", "Observacao"
        ]
        assert len(items) > 0, "No items generated"
        for field in required_fields:
            assert field in items[0], f"Missing required field: {field}"

    def test_order_references_correct_unit(self):
        """Test that orders reference the correct unit ID."""
        unit_id = 42
        orders, items = generate_orders_for_unit_day(
            self.fake, unit_id, self.date, min_orders=5, max_orders=5
        )
        for order in orders:
            assert order["Id_Unidade"] == unit_id

    def test_items_reference_valid_orders(self):
        """Test that items reference existing orders."""
        orders, items = generate_orders_for_unit_day(
            self.fake, self.unit_id, self.date, min_orders=5, max_orders=5
        )
        order_ids = {o["Id_Pedido"] for o in orders}
        for item in items:
            assert item["Id_Pedido"] in order_ids

    def test_valid_statuses(self):
        """Test that all orders have valid status values."""
        orders, items = generate_orders_for_unit_day(
            self.fake, self.unit_id, self.date, min_orders=50, max_orders=50
        )
        for order in orders:
            assert order["Status"] in STATUS_CHOICES

    def test_valid_order_types(self):
        """Test that all orders have valid order types."""
        orders, items = generate_orders_for_unit_day(
            self.fake, self.unit_id, self.date, min_orders=50, max_orders=50
        )
        for order in orders:
            assert order["Tipo_Pedido"] in ORDER_TYPE_CHOICES

    def test_physical_orders_no_delivery_fee(self):
        """Test that physical orders have zero delivery fee."""
        orders, items = generate_orders_for_unit_day(
            self.fake, self.unit_id, self.date, min_orders=100, max_orders=100
        )
        physical_orders = [o for o in orders if o["Tipo_Pedido"] == "Loja Fisica"]
        assert len(physical_orders) > 0, "No physical orders generated"
        for order in physical_orders:
            assert float(order["Taxa_Entrega"]) == 0.00

    def test_product_ids_in_catalog(self):
        """Test that all product IDs are from the catalog."""
        orders, items = generate_orders_for_unit_day(
            self.fake, self.unit_id, self.date, min_orders=20, max_orders=20
        )
        valid_ids = {p["id"] for p in PRODUCT_CATALOG}
        for item in items:
            assert item["Id_Produto"] in valid_ids

    def test_positive_quantities(self):
        """Test that all item quantities are positive."""
        orders, items = generate_orders_for_unit_day(
            self.fake, self.unit_id, self.date, min_orders=20, max_orders=20
        )
        for item in items:
            assert item["Qtd"] >= 1

    def test_date_format(self):
        """Test that order dates have correct format."""
        orders, items = generate_orders_for_unit_day(
            self.fake, self.unit_id, self.date, min_orders=1, max_orders=1
        )
        assert orders[0]["Data_Pedido"] == "2026-01-15"


class TestReferenceData:
    """Tests for reference data constants."""

    def test_product_catalog_has_30_items(self):
        """Test that product catalog has exactly 30 products."""
        assert len(PRODUCT_CATALOG) == 30

    def test_states_are_southern_brazil(self):
        """Test that states are from southern Brazil."""
        state_names = {s["name"] for s in STATES}
        assert "Rio Grande do Sul" in state_names
        assert "Santa Catarina" in state_names
        assert "Parana" in state_names

    def test_countries_has_brazil(self):
        """Test that Brasil is the only country."""
        assert len(COUNTRIES) == 1
        assert COUNTRIES[0]["name"] == "Brasil"

    def test_reference_data_generates_csvs(self, tmp_path):
        """Test that reference data CSVs are generated."""
        units = generate_unit_list(5)
        generate_reference_data(units, tmp_path)

        assert (tmp_path / "reference_data" / "produto.csv").exists()
        assert (tmp_path / "reference_data" / "unidade.csv").exists()
        assert (tmp_path / "reference_data" / "estado.csv").exists()
        assert (tmp_path / "reference_data" / "pais.csv").exists()

    def test_produto_csv_has_correct_columns(self, tmp_path):
        """Test that product CSV has correct structure."""
        units = generate_unit_list(5)
        generate_reference_data(units, tmp_path)
        df = pd.read_csv(tmp_path / "reference_data" / "produto.csv", sep=";")
        assert "Id_Produto" in df.columns
        assert "Nome_Produto" in df.columns
        assert len(df) == 30


class TestReproducibility:
    """Tests for data generation reproducibility."""

    def test_seed_produces_same_output(self):
        """Test that same seed produces identical data."""
        fake1 = Faker("pt_BR")
        fake1.seed_instance(42)
        orders1, items1 = generate_orders_for_unit_day(
            fake1, 1, datetime(2026, 1, 1), 10, 10
        )

        fake2 = Faker("pt_BR")
        fake2.seed_instance(42)
        orders2, items2 = generate_orders_for_unit_day(
            fake2, 1, datetime(2026, 1, 1), 10, 10
        )

        assert len(orders1) == len(orders2)
        for o1, o2 in zip(orders1, orders2):
            assert o1["Id_Pedido"] == o2["Id_Pedido"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
