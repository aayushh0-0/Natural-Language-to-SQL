"""
Unit tests for dynamic SQLite schema introspection and table selection.
"""

import pytest

from src.schema import SchemaEngine
from src.models import DatabaseCatalog, TableSchema


class TestSchemaIntrospection:
    """Tests for dynamic catalog extraction without hardcoding."""

    @pytest.fixture(scope="class")
    def engine(self):
        return SchemaEngine("store.db")

    @pytest.fixture(scope="class")
    def catalog(self, engine):
        return engine.get_catalog()

    def test_discovers_all_tables(self, catalog: DatabaseCatalog):
        expected_tables = {
            "artists",
            "albums",
            "tracks",
            "genres",
            "media_types",
            "invoices",
            "invoice_items",
            "customers",
            "employees",
            "playlists",
            "playlist_track",
        }
        discovered_tables = set(catalog.tables.keys())
        assert expected_tables.issubset(discovered_tables)
        assert len(discovered_tables) == 11

    def test_discovers_column_metadata(self, catalog: DatabaseCatalog):
        customers_table = catalog.tables["customers"]
        column_names = [c.name for c in customers_table.columns]
        assert "CustomerId" in column_names
        assert "FirstName" in column_names
        assert "LastName" in column_names
        assert "Email" in column_names
        assert "Country" in column_names

        # Check primary key
        pk_col = next(c for c in customers_table.columns if c.name == "CustomerId")
        assert pk_col.is_primary_key is True

    def test_discovers_foreign_keys(self, catalog: DatabaseCatalog):
        albums_table = catalog.tables["albums"]
        fk_artists = [fk for fk in albums_table.foreign_keys if fk.to_table == "artists"]
        assert len(fk_artists) == 1
        assert fk_artists[0].from_column == "ArtistId"
        assert fk_artists[0].to_column == "ArtistId"

        invoices_table = catalog.tables["invoices"]
        fk_customers = [fk for fk in invoices_table.foreign_keys if fk.to_table == "customers"]
        assert len(fk_customers) == 1
        assert fk_customers[0].from_column == "CustomerId"

    def test_retrieves_exact_row_counts(self, catalog: DatabaseCatalog):
        assert catalog.tables["artists"].row_count > 0
        assert catalog.tables["tracks"].row_count > 0
        assert catalog.tables["invoices"].row_count > 0

    def test_retrieves_sample_rows(self, catalog: DatabaseCatalog):
        assert len(catalog.tables["artists"].sample_rows) > 0
        assert len(catalog.tables["customers"].sample_rows) > 0

    def test_format_whole_schema_prompt(self, engine: SchemaEngine):
        schema_text = engine.format_whole_schema_prompt()
        assert "Table: `artists`" in schema_text
        assert "Table: `customers`" in schema_text
        assert "Table: `invoices`" in schema_text
        assert "Foreign Keys" in schema_text
        assert "Sample Rows" in schema_text

    def test_format_table_summary_prompt(self, engine: SchemaEngine):
        summary = engine.format_table_summary_prompt()
        assert "Available Tables & Column Overview" in summary
        assert "`artists`" in summary
        assert "`invoices`" in summary

    def test_format_selected_tables_prompt(self, engine: SchemaEngine):
        selected = ["artists", "albums"]
        schema_text = engine.format_selected_tables_prompt(selected)
        assert "Table: `artists`" in schema_text
        assert "Table: `albums`" in schema_text
        assert "Table: `customers`" not in schema_text
