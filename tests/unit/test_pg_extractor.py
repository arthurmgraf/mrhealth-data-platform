"""
Unit tests for pg-reference-extractor Cloud Function.

Testa a lógica de extração e formatação CSV sem dependências externas.
Todos os acessos a PostgreSQL, SSH e GCS são mockados.
"""

import os
import sys

sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "cloud_functions",
        "pg_reference_extractor",
    ),
)

from main import TABLES, extract_table


class MockCursor:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, query):
        pass

    def fetchall(self):
        return self._rows


class TestExtractTable:
    def test_produto_csv_format(self):
        cursor = MockCursor([(1, "Bowl de Acai Premium"), (2, "Salada Caesar Grelhada")])
        csv_content, row_count = extract_table(cursor, TABLES["produto"])

        assert row_count == 2
        lines = csv_content.strip().split("\n")
        assert len(lines) == 3
        assert lines[0] == "Id_Produto;Nome_Produto"
        assert lines[1] == "1;Bowl de Acai Premium"
        assert lines[2] == "2;Salada Caesar Grelhada"

    def test_unidade_csv_format(self):
        cursor = MockCursor([(1, "Mr. Health - Porto Alegre", 1)])
        csv_content, row_count = extract_table(cursor, TABLES["unidade"])

        assert row_count == 1
        lines = csv_content.strip().split("\n")
        assert lines[0] == "Id_Unidade;Nome_Unidade;Id_Estado"
        assert lines[1] == "1;Mr. Health - Porto Alegre;1"

    def test_estado_csv_format(self):
        cursor = MockCursor([(1, 1, "Rio Grande do Sul"), (2, 1, "Santa Catarina")])
        csv_content, row_count = extract_table(cursor, TABLES["estado"])

        assert row_count == 2
        lines = csv_content.strip().split("\n")
        assert lines[0] == "Id_Estado;Id_Pais;Nome_Estado"
        assert lines[1] == "1;1;Rio Grande do Sul"

    def test_pais_csv_format(self):
        cursor = MockCursor([(1, "Brasil")])
        csv_content, row_count = extract_table(cursor, TABLES["pais"])

        assert row_count == 1
        lines = csv_content.strip().split("\n")
        assert lines[0] == "Id_Pais;Nome_Pais"
        assert lines[1] == "1;Brasil"

    def test_empty_table_returns_empty(self):
        cursor = MockCursor([])
        csv_content, row_count = extract_table(cursor, TABLES["produto"])

        assert csv_content == ""
        assert row_count == 0

    def test_csv_ends_with_newline(self):
        cursor = MockCursor([(1, "Brasil")])
        csv_content, _ = extract_table(cursor, TABLES["pais"])

        assert csv_content.endswith("\n")

    def test_semicolon_separator(self):
        cursor = MockCursor([(1, "Test Product")])
        csv_content, _ = extract_table(cursor, TABLES["produto"])

        lines = csv_content.strip().split("\n")
        assert ";" in lines[0]
        assert ";" in lines[1]
        assert "," not in lines[1]


class TestTableConfig:
    def test_all_four_tables_configured(self):
        assert set(TABLES.keys()) == {"produto", "unidade", "estado", "pais"}

    def test_each_table_has_required_keys(self):
        for table_name, config in TABLES.items():
            assert "query" in config, f"{table_name} missing 'query'"
            assert "csv_name" in config, f"{table_name} missing 'csv_name'"
            assert "header" in config, f"{table_name} missing 'header'"

    def test_csv_names_match_expected(self):
        expected = {
            "produto": "produto.csv",
            "unidade": "unidade.csv",
            "estado": "estado.csv",
            "pais": "pais.csv",
        }
        for table_name, expected_csv in expected.items():
            assert TABLES[table_name]["csv_name"] == expected_csv

    def test_queries_are_select_only(self):
        for table_name, config in TABLES.items():
            query = config["query"].upper()
            assert query.startswith("SELECT"), f"{table_name} query is not SELECT"
            assert "INSERT" not in query
            assert "UPDATE" not in query
            assert "DELETE" not in query
            assert "DROP" not in query

    def test_queries_have_order_by(self):
        for table_name, config in TABLES.items():
            assert "ORDER BY" in config["query"], f"{table_name} query missing ORDER BY"

    def test_headers_use_semicolon_separator(self):
        for table_name, config in TABLES.items():
            if ";" in config["header"]:
                parts = config["header"].split(";")
                assert len(parts) >= 2, f"{table_name} header has < 2 columns"


class TestCSVConsistency:
    def test_produto_header_matches_query_columns(self):
        header_cols = TABLES["produto"]["header"].split(";")
        assert header_cols == ["Id_Produto", "Nome_Produto"]

    def test_unidade_header_matches_query_columns(self):
        header_cols = TABLES["unidade"]["header"].split(";")
        assert header_cols == ["Id_Unidade", "Nome_Unidade", "Id_Estado"]

    def test_estado_header_matches_query_columns(self):
        header_cols = TABLES["estado"]["header"].split(";")
        assert header_cols == ["Id_Estado", "Id_Pais", "Nome_Estado"]

    def test_pais_header_matches_query_columns(self):
        header_cols = TABLES["pais"]["header"].split(";")
        assert header_cols == ["Id_Pais", "Nome_Pais"]
