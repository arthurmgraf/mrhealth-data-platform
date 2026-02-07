"""End-to-end pipeline validation tests.

Tests the logical flow from CSV generation through validation to loading.
Uses real data generation but mocks all GCP services (BigQuery, GCS).
This validates the contracts between pipeline stages.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from scripts.constants import PRODUCT_CATALOG, STATUS_CHOICES, ORDER_TYPE_CHOICES


class TestCSVToValidation:
    """Tests that generated CSV data passes Cloud Function validation."""

    def test_generated_pedido_passes_validation(self):
        from scripts.generate_fake_sales import generate_orders_for_unit_day
        from cloud_functions.csv_processor.main import validate_pedido, PEDIDO_COLUMNS
        from faker import Faker

        fake = Faker("pt_BR")
        fake.seed_instance(42)

        orders, items = generate_orders_for_unit_day(
            fake, unit_id=1, date=datetime(2026, 1, 15),
            min_orders=20, max_orders=20,
        )

        df = pd.DataFrame(orders)
        assert set(PEDIDO_COLUMNS).issubset(set(df.columns))

        df_valid, errors = validate_pedido(df)

        assert len(df_valid) == 20
        assert len(errors) == 0

    def test_generated_item_pedido_passes_validation(self):
        from scripts.generate_fake_sales import generate_orders_for_unit_day
        from cloud_functions.csv_processor.main import validate_item_pedido, ITEM_PEDIDO_COLUMNS
        from faker import Faker

        fake = Faker("pt_BR")
        fake.seed_instance(42)

        orders, items = generate_orders_for_unit_day(
            fake, unit_id=1, date=datetime(2026, 1, 15),
            min_orders=10, max_orders=10,
        )

        df = pd.DataFrame(items)
        assert set(ITEM_PEDIDO_COLUMNS).issubset(set(df.columns))

        df_valid, errors = validate_item_pedido(df)

        assert len(df_valid) > 0
        assert len(errors) == 0


class TestDataConsistency:
    """Tests cross-table referential integrity of generated data."""

    def test_all_items_reference_valid_orders(self):
        from scripts.generate_fake_sales import generate_orders_for_unit_day
        from faker import Faker

        fake = Faker("pt_BR")
        fake.seed_instance(123)

        orders, items = generate_orders_for_unit_day(
            fake, unit_id=1, date=datetime(2026, 1, 15),
            min_orders=50, max_orders=50,
        )

        order_ids = {o["Id_Pedido"] for o in orders}
        for item in items:
            assert item["Id_Pedido"] in order_ids

    def test_all_products_reference_valid_catalog(self):
        from scripts.generate_fake_sales import generate_orders_for_unit_day
        from faker import Faker

        fake = Faker("pt_BR")
        fake.seed_instance(456)

        _, items = generate_orders_for_unit_day(
            fake, unit_id=1, date=datetime(2026, 1, 15),
            min_orders=50, max_orders=50,
        )

        valid_product_ids = {p["id"] for p in PRODUCT_CATALOG}
        for item in items:
            assert item["Id_Produto"] in valid_product_ids

    def test_order_value_positive(self):
        from scripts.generate_fake_sales import generate_orders_for_unit_day
        from faker import Faker

        fake = Faker("pt_BR")
        fake.seed_instance(789)

        orders, _ = generate_orders_for_unit_day(
            fake, unit_id=1, date=datetime(2026, 1, 15),
            min_orders=100, max_orders=100,
        )

        for order in orders:
            assert float(order["Vlr_Pedido"]) > 0


class TestSQLFileIntegrity:
    """Tests that all SQL files referenced by the pipeline exist and are valid."""

    @pytest.fixture
    def project_root(self):
        return Path(__file__).parent.parent.parent

    def test_all_silver_sql_files_exist(self, project_root):
        sql_dir = project_root / "sql" / "silver"
        expected = [
            "01_reference_tables.sql",
            "02_orders.sql",
            "03_order_items.sql",
        ]
        for f in expected:
            assert (sql_dir / f).exists(), f"Missing Silver SQL: {f}"

    def test_all_gold_sql_files_exist(self, project_root):
        sql_dir = project_root / "sql" / "gold"
        expected = [
            "01_dim_date.sql",
            "02_dim_product.sql",
            "03_dim_unit.sql",
            "04_dim_geography.sql",
            "05_fact_sales.sql",
            "06_fact_order_items.sql",
        ]
        for f in expected:
            assert (sql_dir / f).exists(), f"Missing Gold SQL: {f}"

    def test_all_aggregation_sql_files_exist(self, project_root):
        sql_dir = project_root / "sql" / "gold"
        expected = [
            "07_agg_daily_sales.sql",
            "08_agg_unit_performance.sql",
            "09_agg_product_performance.sql",
        ]
        for f in expected:
            assert (sql_dir / f).exists(), f"Missing Aggregation SQL: {f}"

    def test_all_monitoring_sql_files_exist(self, project_root):
        sql_dir = project_root / "sql" / "monitoring"
        expected = [
            "01_create_data_quality_log.sql",
            "02_create_pipeline_metrics.sql",
            "03_create_free_tier_usage.sql",
        ]
        for f in expected:
            assert (sql_dir / f).exists(), f"Missing Monitoring SQL: {f}"

    def test_sql_files_contain_project_id_placeholder(self, project_root):
        """Gold/Silver SQL files should use {PROJECT_ID} for portability."""
        sql_dirs = [
            project_root / "sql" / "silver",
            project_root / "sql" / "gold",
        ]
        for sql_dir in sql_dirs:
            for sql_file in sql_dir.glob("*.sql"):
                content = sql_file.read_text(encoding="utf-8")
                assert "{PROJECT_ID}" in content, (
                    f"{sql_file.name} missing {{PROJECT_ID}} placeholder"
                )

    def test_no_hardcoded_project_ids_in_sql(self, project_root):
        """SQL files should not contain hardcoded project IDs."""
        import re
        pattern = re.compile(r"sixth-foundry-\d+-\w+|case.ficticio", re.IGNORECASE)

        for sql_dir in ["bronze", "silver", "gold", "monitoring"]:
            path = project_root / "sql" / sql_dir
            if path.exists():
                for sql_file in path.glob("*.sql"):
                    content = sql_file.read_text(encoding="utf-8")
                    match = pattern.search(content)
                    assert match is None, (
                        f"{sql_file.name} contains hardcoded ID: {match.group()}"
                    )


class TestConfigIntegrity:
    """Tests that the project configuration is valid."""

    @pytest.fixture
    def project_root(self):
        return Path(__file__).parent.parent.parent

    def test_config_yaml_exists(self, project_root):
        assert (project_root / "config" / "project_config.yaml").exists()

    def test_config_has_required_sections(self, project_root):
        import yaml

        config_path = project_root / "config" / "project_config.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)

        assert "project" in config
        assert "bigquery" in config
        assert "storage" in config

    def test_config_dataset_names_use_mrhealth(self, project_root):
        import yaml

        config_path = project_root / "config" / "project_config.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)

        datasets = config["bigquery"]["datasets"]
        for layer, name in datasets.items():
            assert name.startswith("mrhealth_"), (
                f"Dataset {layer} = '{name}' should start with 'mrhealth_'"
            )
