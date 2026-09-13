"""
Safe SQLite Query Executor.
Executes validated read-only SQL queries with timeout controls, row truncation, and telemetry.
"""

import time
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from src.config import config
from src.database import DatabaseConnection


class QueryExecutionError(Exception):
    """Raised when query execution fails in SQLite."""
    pass


class QueryExecutor:
    """
    Executes read-only SQL queries against SQLite database safely.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db = DatabaseConnection(db_path)

    def execute(self, sql_query: str, max_rows: Optional[int] = None) -> Tuple[List[Dict[str, Any]], float]:
        """
        Executes a validated read-only SQL query.

        Args:
            sql_query: Sanitized read-only SQL string.
            max_rows: Optional maximum rows limit (defaults to config.MAX_RESULT_ROWS).

        Returns:
            Tuple of (results_list_of_dicts, execution_latency_ms)

        Raises:
            QueryExecutionError on runtime SQLite failure.
        """
        limit = max_rows or config.MAX_RESULT_ROWS
        start_time = time.perf_counter()

        with self.db.connect_ro() as conn:
            cur = conn.cursor()
            try:
                cur.execute(sql_query)
                rows = cur.fetchmany(limit)

                # Convert sqlite3.Row objects to standard Python dictionaries
                results: List[Dict[str, Any]] = []
                for row in rows:
                    results.append({k: row[k] for k in row.keys()})

                latency_ms = (time.perf_counter() - start_time) * 1000.0
                return results, latency_ms

            except sqlite3.OperationalError as e:
                raise QueryExecutionError(f"SQLite Operational Error: {str(e)}") from e
            except sqlite3.DatabaseError as e:
                raise QueryExecutionError(f"SQLite Database Error: {str(e)}") from e
            except Exception as e:
                raise QueryExecutionError(f"Unexpected Execution Error: {str(e)}") from e
