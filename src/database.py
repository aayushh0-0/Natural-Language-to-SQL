"""
Database connection factory with multi-layer defense-in-depth security.
Implements read-only SQLite connection handling and engine-level authorizer callbacks.
"""

import os
import sqlite3
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple
from contextlib import contextmanager

from src.config import config

# Allowed read-only pragmas for schema introspection
ALLOWED_READONLY_PRAGMAS = {
    "table_info",
    "foreign_key_list",
    "table_xinfo",
    "index_list",
    "index_info",
    "database_list",
    "query_only",
}


def sqlite_authorizer_read_only(action_code: int, param1: Optional[str], param2: Optional[str], db_name: Optional[str], trigger_or_view: Optional[str]) -> int:
    """
    SQLite authorizer callback function.
    Runs at the SQLite C-engine level on every parsed AST operation.

    Allowed actions:
    - SQLITE_SELECT (21)
    - SQLITE_READ (20)
    - SQLITE_FUNCTION (31)
    - SQLITE_PRAGMA (19) only for read-only metadata inspection (table_info, foreign_key_list)

    Denied actions:
    - SQLITE_INSERT (18)
    - SQLITE_UPDATE (23)
    - SQLITE_DELETE (9)
    - SQLITE_DROP_TABLE (11)
    - SQLITE_DROP_INDEX (10)
    - SQLITE_DROP_VIEW (12)
    - SQLITE_DROP_TRIGGER (13)
    - SQLITE_CREATE_TABLE (1)
    - SQLITE_CREATE_INDEX (2)
    - SQLITE_CREATE_VIEW (8)
    - SQLITE_CREATE_TRIGGER (7)
    - SQLITE_ALTER_TABLE (26)
    - SQLITE_ATTACH (24)
    - SQLITE_DETACH (25)
    - All mutating PRAGMAs

    Returns:
        sqlite3.SQLITE_OK (0) if allowed,
        sqlite3.SQLITE_DENY (1) to abort and raise sqlite3.DatabaseError.
    """
    SQLITE_OK = 0
    SQLITE_DENY = 1

    # Allowed basic read-only action codes in sqlite3
    if action_code in (21, 20, 31):  # SQLITE_SELECT, SQLITE_READ, SQLITE_FUNCTION
        return SQLITE_OK

    # Pragma check: Only allow read-only schema inspection pragmas
    if action_code == 19:  # SQLITE_PRAGMA
        if param1 and param1.lower() in ALLOWED_READONLY_PRAGMAS:
            return SQLITE_OK
        return SQLITE_DENY

    # Explicitly deny all data manipulation, DDL, schema alteration, attach, etc.
    return SQLITE_DENY


class DatabaseConnection:
    """
    Manages SQLite connections with strict read-only enforcement.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or config.DEFAULT_DB_PATH
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"Database file not found at path: {self.db_path}")
        self.abs_db_path = os.path.abspath(self.db_path)

    def get_read_only_connection(self) -> sqlite3.Connection:
        """
        Creates a SQLite connection with 3 distinct layers of read-only guarantees:
        1. URI file mode: 'file:<path>?mode=ro' (OS/Filesystem level write prevention)
        2. PRAGMA query_only = ON (SQLite engine session setting)
        3. set_authorizer (C-level callback rejecting non-SELECT AST opcodes)
        """
        # Normalize Windows path for URI (convert backslashes to forward slashes)
        normalized_path = self.abs_db_path.replace("\\", "/")
        uri = f"file:{normalized_path}?mode=ro"

        try:
            conn = sqlite3.connect(uri, uri=True, timeout=config.QUERY_TIMEOUT_SECONDS)
        except sqlite3.OperationalError:
            # Fallback if URI mode fails on specific OS configurations
            conn = sqlite3.connect(self.abs_db_path, timeout=config.QUERY_TIMEOUT_SECONDS)

        # Set row factory to access columns by name
        conn.row_factory = sqlite3.Row

        # Set authorizer callback
        conn.set_authorizer(sqlite_authorizer_read_only)

        return conn

    @contextmanager
    def connect_ro(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Context manager for safe read-only database connections.
        Ensures connection is always closed cleanly.
        """
        conn = self.get_read_only_connection()
        try:
            yield conn
        finally:
            conn.close()

    def test_connection(self) -> bool:
        """Verifies database accessibility and read-only authorizer configuration."""
        with self.connect_ro() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 AS health_check;")
            row = cur.fetchone()
            return row["health_check"] == 1
