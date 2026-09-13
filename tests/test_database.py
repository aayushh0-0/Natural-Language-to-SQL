"""
Unit tests for database connection handling, read-only guarantees, execution integrity, and query validation.
"""

import os
import sqlite3
import pytest

from src.database import DatabaseConnection
from src.executor import QueryExecutor
from src.validator import QueryValidator
from src.models import QueryStatus


class TestDatabaseConnection:
    """Tests for DatabaseConnection factory and read-only invariants."""

    def test_database_file_exists(self):
        db = DatabaseConnection("store.db")
        assert os.path.exists(db.abs_db_path)

    def test_nonexistent_database_raises_error(self):
        with pytest.raises(FileNotFoundError):
            DatabaseConnection("non_existent_db_12345.db")

    def test_health_check_succeeds(self):
        db = DatabaseConnection("store.db")
        assert db.test_connection() is True

    def test_read_only_blocks_writes_at_connection_level(self):
        db = DatabaseConnection("store.db")
        with db.connect_ro() as conn:
            cur = conn.cursor()
            # Attempt to create a table
            with pytest.raises(sqlite3.DatabaseError):
                cur.execute("CREATE TABLE test_table (id INT);")

    def test_read_only_blocks_insert_at_connection_level(self):
        db = DatabaseConnection("store.db")
        with db.connect_ro() as conn:
            cur = conn.cursor()
            # Attempt to insert
            with pytest.raises(sqlite3.DatabaseError):
                cur.execute("INSERT INTO artists (Name) VALUES ('Test Artist');")


class TestQueryExecutor:
    """Tests for QueryExecutor executing read-only queries with timeout and formatting."""

    def test_executor_executes_valid_query(self):
        executor = QueryExecutor("store.db")
        rows, duration = executor.execute("SELECT ArtistId, Name FROM artists ORDER BY ArtistId ASC LIMIT 3;")
        assert isinstance(rows, list)
        assert len(rows) == 3
        assert rows[0]["Name"] == "AC/DC"
        assert duration > 0.0


class TestQueryValidator:
    """Tests for QueryValidator combining AST checks with SQLite EXPLAIN bytecode verification."""

    def test_validator_accepts_valid_query(self):
        validator = QueryValidator("store.db")
        res = validator.validate("SELECT * FROM customers;")
        assert res.is_valid is True
        assert res.status == QueryStatus.OK

    def test_validator_rejects_invalid_syntax(self):
        validator = QueryValidator("store.db")
        res = validator.validate("SELECT * FORM customers;")
        assert res.is_valid is False
        assert "syntax error" in res.error_message.lower() or "near" in res.error_message.lower()

    def test_validator_rejects_nonexistent_column(self):
        validator = QueryValidator("store.db")
        res = validator.validate("SELECT NonExistentColumn123 FROM customers;")
        assert res.is_valid is False
        assert "no such column" in res.error_message.lower()
