"""Unit tests for the csv_processor Cloud Function.

Tests all validation, loading, and quarantine logic without GCP dependencies.
All GCS/BigQuery calls are mocked.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch, call

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def valid_pedido_df() -> pd.DataFrame:
    """DataFrame mimicking a valid pedido.csv."""
    return pd.DataFrame({
        "Id_Unidade": [1, 2, 3],
        "Id_Pedido": ["ORD001", "ORD002", "ORD003"],
        "Tipo_Pedido": ["Loja Online", "Loja Fisica", "Loja Online"],
        "Data_Pedido": ["2026-01-15", "2026-01-15", "2026-01-16"],
        "Vlr_Pedido": [42.90, 28.50, 100.00],
        "Endereco_Entrega": ["Rua A", "Rua B", "Rua C"],
        "Taxa_Entrega": [5.00, 0.00, 8.50],
        "Status": ["Finalizado", "Pendente", "Cancelado"],
    })


@pytest.fixture
def valid_item_pedido_df() -> pd.DataFrame:
    """DataFrame mimicking a valid item_pedido.csv."""
    return pd.DataFrame({
        "Id_Pedido": ["ORD001", "ORD001", "ORD002"],
        "Id_Item_Pedido": ["ITEM001", "ITEM002", "ITEM003"],
        "Id_Produto": [1, 5, 10],
        "Qtd": [2, 1, 3],
        "Vlr_Item": [28.90, 18.50, 21.90],
        "Observacao": ["Sem gluten", "", "Extra proteina"],
    })


# ---------------------------------------------------------------------------
# validate_pedido
# ---------------------------------------------------------------------------

class TestValidatePedido:
    def test_valid_data_returns_all_rows(self, valid_pedido_df):
        from cloud_functions.csv_processor.main import validate_pedido

        df_valid, errors = validate_pedido(valid_pedido_df.copy())
        assert len(df_valid) == 3
        assert len(errors) == 0

    def test_missing_columns_returns_empty(self):
        from cloud_functions.csv_processor.main import validate_pedido

        df = pd.DataFrame({"Id_Unidade": [1], "Id_Pedido": ["ORD001"]})
        df_valid, errors = validate_pedido(df)
        assert len(df_valid) == 0
        assert any("Missing columns" in e for e in errors)

    def test_null_required_fields_dropped(self, valid_pedido_df):
        from cloud_functions.csv_processor.main import validate_pedido

        df = valid_pedido_df.copy()
        df.loc[0, "Vlr_Pedido"] = None
        df_valid, errors = validate_pedido(df)
        assert len(df_valid) == 2
        assert any("null required fields" in e for e in errors)

    def test_invalid_status_dropped(self, valid_pedido_df):
        from cloud_functions.csv_processor.main import validate_pedido

        df = valid_pedido_df.copy()
        df.loc[0, "Status"] = "InvalidStatus"
        df_valid, errors = validate_pedido(df)
        assert len(df_valid) == 2
        assert any("invalid Status" in e for e in errors)

    def test_duplicate_orders_deduplicated(self, valid_pedido_df):
        from cloud_functions.csv_processor.main import validate_pedido

        df = valid_pedido_df.copy()
        df.loc[2, "Id_Pedido"] = "ORD001"  # duplicate
        df_valid, errors = validate_pedido(df)
        assert len(df_valid) == 2
        assert any("duplicate" in e for e in errors)

    def test_type_coercion_handles_strings(self, valid_pedido_df):
        from cloud_functions.csv_processor.main import validate_pedido

        df = valid_pedido_df.copy()
        df["Vlr_Pedido"] = ["42.90", "28.50", "100.00"]
        df["Id_Unidade"] = ["1", "2", "3"]
        df_valid, errors = validate_pedido(df)
        assert len(df_valid) == 3

    def test_non_numeric_value_becomes_null_and_dropped(self, valid_pedido_df):
        from cloud_functions.csv_processor.main import validate_pedido

        df = valid_pedido_df.copy()
        df.loc[0, "Vlr_Pedido"] = "not_a_number"
        df_valid, errors = validate_pedido(df)
        assert len(df_valid) == 2

    def test_date_coercion(self, valid_pedido_df):
        from cloud_functions.csv_processor.main import validate_pedido

        df = valid_pedido_df.copy()
        df.loc[0, "Data_Pedido"] = "invalid-date"
        df_valid, errors = validate_pedido(df)
        assert len(df_valid) == 2


# ---------------------------------------------------------------------------
# validate_item_pedido
# ---------------------------------------------------------------------------

class TestValidateItemPedido:
    def test_valid_data_returns_all_rows(self, valid_item_pedido_df):
        from cloud_functions.csv_processor.main import validate_item_pedido

        df_valid, errors = validate_item_pedido(valid_item_pedido_df.copy())
        assert len(df_valid) == 3
        assert len(errors) == 0

    def test_missing_columns_returns_empty(self):
        from cloud_functions.csv_processor.main import validate_item_pedido

        df = pd.DataFrame({"Id_Pedido": ["ORD001"]})
        df_valid, errors = validate_item_pedido(df)
        assert len(df_valid) == 0
        assert any("Missing columns" in e for e in errors)

    def test_null_required_fields_dropped(self, valid_item_pedido_df):
        from cloud_functions.csv_processor.main import validate_item_pedido

        df = valid_item_pedido_df.copy()
        df.loc[0, "Qtd"] = None
        df_valid, errors = validate_item_pedido(df)
        assert len(df_valid) == 2

    def test_duplicate_items_deduplicated(self, valid_item_pedido_df):
        from cloud_functions.csv_processor.main import validate_item_pedido

        df = valid_item_pedido_df.copy()
        df.loc[2, "Id_Item_Pedido"] = "ITEM001"  # duplicate
        df_valid, errors = validate_item_pedido(df)
        assert len(df_valid) == 2
        assert any("duplicate" in e for e in errors)

    def test_type_coercion_handles_strings(self, valid_item_pedido_df):
        from cloud_functions.csv_processor.main import validate_item_pedido

        df = valid_item_pedido_df.copy()
        df["Qtd"] = ["2", "1", "3"]
        df_valid, errors = validate_item_pedido(df)
        assert len(df_valid) == 3


# ---------------------------------------------------------------------------
# load_to_bigquery
# ---------------------------------------------------------------------------

class TestLoadToBigquery:
    @patch("cloud_functions.csv_processor.main.bigquery.Client")
    def test_load_adds_metadata_columns(self, mock_bq_cls, valid_pedido_df):
        from cloud_functions.csv_processor.main import load_to_bigquery

        client = MagicMock()
        mock_bq_cls.return_value = client
        job = MagicMock()
        client.load_table_from_dataframe.return_value = job

        rows = load_to_bigquery(valid_pedido_df.copy(), "orders", "raw/csv_sales/pedido.csv")

        assert rows == 3
        call_args = client.load_table_from_dataframe.call_args
        loaded_df = call_args[0][0]
        assert "_source_file" in loaded_df.columns
        assert "_ingest_timestamp" in loaded_df.columns
        assert "_ingest_date" in loaded_df.columns

    @patch("cloud_functions.csv_processor.main.bigquery.Client")
    def test_load_normalizes_column_names(self, mock_bq_cls, valid_pedido_df):
        from cloud_functions.csv_processor.main import load_to_bigquery

        client = MagicMock()
        mock_bq_cls.return_value = client
        job = MagicMock()
        client.load_table_from_dataframe.return_value = job

        load_to_bigquery(valid_pedido_df.copy(), "orders", "test.csv")

        loaded_df = client.load_table_from_dataframe.call_args[0][0]
        assert "id_pedido" in loaded_df.columns
        assert "Id_Pedido" not in loaded_df.columns
        assert "vlr_pedido" in loaded_df.columns

    @patch("cloud_functions.csv_processor.main.bigquery.Client")
    def test_load_converts_numerics_to_decimal(self, mock_bq_cls, valid_pedido_df):
        from cloud_functions.csv_processor.main import load_to_bigquery
        from decimal import Decimal

        client = MagicMock()
        mock_bq_cls.return_value = client
        job = MagicMock()
        client.load_table_from_dataframe.return_value = job

        load_to_bigquery(valid_pedido_df.copy(), "orders", "test.csv")

        loaded_df = client.load_table_from_dataframe.call_args[0][0]
        assert isinstance(loaded_df["vlr_pedido"].iloc[0], Decimal)

    @patch("cloud_functions.csv_processor.main.bigquery.Client")
    def test_load_uses_write_append(self, mock_bq_cls, valid_pedido_df):
        from cloud_functions.csv_processor.main import load_to_bigquery

        client = MagicMock()
        mock_bq_cls.return_value = client
        job = MagicMock()
        client.load_table_from_dataframe.return_value = job

        load_to_bigquery(valid_pedido_df.copy(), "orders", "test.csv")

        job_config = client.load_table_from_dataframe.call_args[1].get(
            "job_config",
            client.load_table_from_dataframe.call_args[0][2] if len(client.load_table_from_dataframe.call_args[0]) > 2 else None,
        )
        assert job_config is not None


# ---------------------------------------------------------------------------
# quarantine_file
# ---------------------------------------------------------------------------

class TestQuarantineFile:
    @patch("cloud_functions.csv_processor.main.storage.Client")
    def test_quarantine_copies_and_writes_error(self, mock_storage_cls):
        from cloud_functions.csv_processor.main import quarantine_file

        client = MagicMock()
        mock_storage_cls.return_value = client
        bucket = MagicMock()
        client.bucket.return_value = bucket
        source_blob = MagicMock()
        bucket.blob.return_value = source_blob

        quarantine_file("test-bucket", "raw/csv_sales/pedido.csv", "Test error")

        bucket.copy_blob.assert_called_once()
        assert bucket.blob.call_count >= 1

    @patch("cloud_functions.csv_processor.main.storage.Client")
    def test_quarantine_path_replaces_prefix(self, mock_storage_cls):
        from cloud_functions.csv_processor.main import quarantine_file

        client = MagicMock()
        mock_storage_cls.return_value = client
        bucket = MagicMock()
        client.bucket.return_value = bucket
        source_blob = MagicMock()
        bucket.blob.return_value = source_blob

        quarantine_file("test-bucket", "raw/csv_sales/pedido.csv", "Error")

        copy_args = bucket.copy_blob.call_args
        dest_path = copy_args[0][2]
        assert dest_path.startswith("quarantine/")
        assert "raw/csv_sales/" not in dest_path


# ---------------------------------------------------------------------------
# process_csv (entry point)
# ---------------------------------------------------------------------------

class TestProcessCsv:
    @patch("cloud_functions.csv_processor.main.load_to_bigquery")
    @patch("cloud_functions.csv_processor.main.read_csv_from_gcs")
    def test_skips_non_csv_files(self, mock_read, mock_load):
        from cloud_functions.csv_processor.main import process_csv

        event = MagicMock()
        event.data = {"bucket": "test-bucket", "name": "raw/csv_sales/readme.txt"}

        process_csv(event)

        mock_read.assert_not_called()
        mock_load.assert_not_called()

    @patch("cloud_functions.csv_processor.main.load_to_bigquery")
    @patch("cloud_functions.csv_processor.main.read_csv_from_gcs")
    def test_skips_non_sales_prefix(self, mock_read, mock_load):
        from cloud_functions.csv_processor.main import process_csv

        event = MagicMock()
        event.data = {"bucket": "test-bucket", "name": "raw/reference_data/produto.csv"}

        process_csv(event)

        mock_read.assert_not_called()

    @patch("cloud_functions.csv_processor.main.load_to_bigquery")
    @patch("cloud_functions.csv_processor.main.validate_pedido")
    @patch("cloud_functions.csv_processor.main.read_csv_from_gcs")
    def test_processes_pedido_csv(self, mock_read, mock_validate, mock_load, valid_pedido_df):
        from cloud_functions.csv_processor.main import process_csv

        mock_read.return_value = valid_pedido_df
        mock_validate.return_value = (valid_pedido_df, [])
        mock_load.return_value = 3

        event = MagicMock()
        event.data = {"bucket": "test-bucket", "name": "raw/csv_sales/pedido.csv"}

        process_csv(event)

        mock_validate.assert_called_once()
        mock_load.assert_called_once_with(valid_pedido_df, "orders", "raw/csv_sales/pedido.csv")

    @patch("cloud_functions.csv_processor.main.load_to_bigquery")
    @patch("cloud_functions.csv_processor.main.validate_item_pedido")
    @patch("cloud_functions.csv_processor.main.read_csv_from_gcs")
    def test_processes_item_pedido_csv(self, mock_read, mock_validate, mock_load, valid_item_pedido_df):
        from cloud_functions.csv_processor.main import process_csv

        mock_read.return_value = valid_item_pedido_df
        mock_validate.return_value = (valid_item_pedido_df, [])
        mock_load.return_value = 3

        event = MagicMock()
        event.data = {"bucket": "test-bucket", "name": "raw/csv_sales/item_pedido.csv"}

        process_csv(event)

        mock_validate.assert_called_once()
        mock_load.assert_called_once_with(valid_item_pedido_df, "order_items", "raw/csv_sales/item_pedido.csv")

    @patch("cloud_functions.csv_processor.main.load_to_bigquery")
    @patch("cloud_functions.csv_processor.main.read_csv_from_gcs")
    def test_skips_unknown_csv_file(self, mock_read, mock_load):
        from cloud_functions.csv_processor.main import process_csv

        mock_read.return_value = pd.DataFrame({"col": [1]})

        event = MagicMock()
        event.data = {"bucket": "test-bucket", "name": "raw/csv_sales/unknown.csv"}

        process_csv(event)

        mock_load.assert_not_called()

    @patch("cloud_functions.csv_processor.main.quarantine_file")
    @patch("cloud_functions.csv_processor.main.validate_pedido")
    @patch("cloud_functions.csv_processor.main.read_csv_from_gcs")
    def test_quarantines_when_no_valid_rows(self, mock_read, mock_validate, mock_quarantine, valid_pedido_df):
        from cloud_functions.csv_processor.main import process_csv

        mock_read.return_value = valid_pedido_df
        mock_validate.return_value = (pd.DataFrame(), ["All rows invalid"])

        event = MagicMock()
        event.data = {"bucket": "test-bucket", "name": "raw/csv_sales/pedido.csv"}

        process_csv(event)

        mock_quarantine.assert_called_once()

    @patch("cloud_functions.csv_processor.main.quarantine_file")
    @patch("cloud_functions.csv_processor.main.read_csv_from_gcs")
    def test_quarantines_on_exception(self, mock_read, mock_quarantine):
        from cloud_functions.csv_processor.main import process_csv

        mock_read.side_effect = Exception("Connection error")

        event = MagicMock()
        event.data = {"bucket": "test-bucket", "name": "raw/csv_sales/pedido.csv"}

        process_csv(event)

        mock_quarantine.assert_called_once()
        error_msg = mock_quarantine.call_args[0][2]
        assert "Connection error" in error_msg


# ---------------------------------------------------------------------------
# read_csv_from_gcs
# ---------------------------------------------------------------------------

class TestReadCsvFromGcs:
    @patch("cloud_functions.csv_processor.main.storage.Client")
    def test_reads_semicolon_separated_csv(self, mock_storage_cls):
        from cloud_functions.csv_processor.main import read_csv_from_gcs

        client = MagicMock()
        mock_storage_cls.return_value = client
        bucket = MagicMock()
        client.bucket.return_value = bucket
        blob = MagicMock()
        bucket.blob.return_value = blob
        blob.download_as_text.return_value = "Id_Pedido;Status\nORD001;Finalizado\n"

        df = read_csv_from_gcs("test-bucket", "raw/csv_sales/pedido.csv")

        assert len(df) == 1
        assert "Id_Pedido" in df.columns
        assert df["Id_Pedido"].iloc[0] == "ORD001"
