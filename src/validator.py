"""
SQL query validator combining security AST inspection with SQLite EXPLAIN dry-runs.
Catches syntax errors, hallucinated tables/columns, and security violations prior to execution.
"""

import sqlite3
from typing import Optional, Set

from src.database import DatabaseConnection
from src.models import DatabaseCatalog, QueryStatus, ValidationResult
from src.security import SecurityEngine


class QueryValidator:
    """
    Validates candidate SQL queries across security AST and SQLite schema compliance.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db = DatabaseConnection(db_path)

    def validate(self, sql_query: str, catalog: Optional[DatabaseCatalog] = None) -> ValidationResult:
        """
        Validates SQL through a 3-step pipeline:
        1. Security AST & Forbidden Token Inspection (SecurityEngine)
        2. Schema Entity Validation (Checking for completely invalid/hallucinated tables)
        3. SQLite EXPLAIN Dry-Run (Verifies syntax and column existence in engine)
        """
        # Step 1: Security AST Validation
        ast_result = SecurityEngine.validate_sql_ast(sql_query)
        if not ast_result.is_valid:
            return ast_result

        sanitized_sql = ast_result.sanitized_sql or sql_query

        # Step 2: SQLite EXPLAIN Dry-Run (catches syntax errors and schema mismatches safely)
        with self.db.connect_ro() as conn:
            cur = conn.cursor()
            try:
                # EXPLAIN prepares the statement bytecode without evaluating data or scans
                cur.execute(f"EXPLAIN {sanitized_sql}")
                cur.fetchall()
            except sqlite3.OperationalError as e:
                err_msg = str(e)
                # Check if it was blocked by our read-only authorizer or a real syntax error
                if "not authorized" in err_msg.lower():
                    return ValidationResult(
                        is_valid=False,
                        status=QueryStatus.REFUSED,
                        error_message=f"Database Authorizer Security Violation: {err_msg}",
                    )
                return ValidationResult(
                    is_valid=False,
                    status=QueryStatus.OK,  # Will trigger self-correction retry
                    error_message=f"SQLite Syntax/Schema Error: {err_msg}",
                )
            except sqlite3.DatabaseError as e:
                return ValidationResult(
                    is_valid=False,
                    status=QueryStatus.REFUSED if "authoriz" in str(e).lower() else QueryStatus.OK,
                    error_message=f"SQLite Database Error: {str(e)}",
                )

        return ValidationResult(
            is_valid=True,
            status=QueryStatus.OK,
            sanitized_sql=sanitized_sql,
        )
