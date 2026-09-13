"""
Schema introspection and catalog management.
Dynamically extracts tables, columns, data types, foreign keys, and representative sample rows.
"""

import json
import sqlite3
from typing import Dict, List, Optional, Set

from src.database import DatabaseConnection
from src.models import ColumnInfo, DatabaseCatalog, ForeignKeyInfo, TableSchema
from src.config import config


class SchemaEngine:
    """
    Introspects SQLite database metadata to build structured schema catalogs
    and generate optimal context prompts for LLMs.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db = DatabaseConnection(db_path)
        self._catalog: Optional[DatabaseCatalog] = None

    def get_catalog(self, force_refresh: bool = False) -> DatabaseCatalog:
        """
        Retrieves or inspects the database schema catalog.
        Caches catalog in memory to avoid repeated PRAGMA overhead.
        """
        if self._catalog is not None and not force_refresh:
            return self._catalog

        tables_dict: Dict[str, TableSchema] = {}
        all_table_names: List[str] = []

        with self.db.connect_ro() as conn:
            cur = conn.cursor()

            # 1. Discover all user tables
            cur.execute("""
                SELECT name
                FROM sqlite_master
                WHERE type='table'
                  AND name NOT LIKE 'sqlite_%'
                ORDER BY name;
            """)
            table_rows = cur.fetchall()
            all_table_names = [row["name"] for row in table_rows]

            for tbl_name in all_table_names:
                # 2. Extract column metadata via PRAGMA table_info
                cur.execute(f"PRAGMA table_info('{tbl_name}');")
                col_rows = cur.fetchall()
                columns = [
                    ColumnInfo(
                        name=col["name"],
                        data_type=col["type"] or "TEXT",
                        nullable=not bool(col["notnull"]),
                        is_primary_key=bool(col["pk"]),
                        default_value=str(col["dflt_value"]) if col["dflt_value"] is not None else None,
                    )
                    for col in col_rows
                ]

                # 3. Extract foreign key relationships via PRAGMA foreign_key_list
                cur.execute(f"PRAGMA foreign_key_list('{tbl_name}');")
                fk_rows = cur.fetchall()
                foreign_keys = [
                    ForeignKeyInfo(
                        from_column=fk["from"],
                        to_table=fk["table"],
                        to_column=fk["to"],
                    )
                    for fk in fk_rows
                ]

                # 4. Extract row count
                cur.execute(f"SELECT COUNT(*) AS total_rows FROM '{tbl_name}';")
                row_count = cur.fetchone()["total_rows"]

                # 5. Extract sample rows (up to configured limit)
                sample_rows = []
                if row_count > 0:
                    cur.execute(f"SELECT * FROM '{tbl_name}' LIMIT {config.SCHEMA_SAMPLE_ROWS};")
                    sample_records = cur.fetchall()
                    for r in sample_records:
                        row_dict = {}
                        for k in r.keys():
                            val = r[k]
                            # Truncate overly long text fields in samples to save prompt tokens
                            if isinstance(val, str) and len(val) > 60:
                                val = val[:57] + "..."
                            row_dict[k] = val
                        sample_rows.append(row_dict)

                tables_dict[tbl_name] = TableSchema(
                    table_name=tbl_name,
                    columns=columns,
                    foreign_keys=foreign_keys,
                    sample_rows=sample_rows,
                    row_count=row_count,
                )

        self._catalog = DatabaseCatalog(
            db_path=self.db.db_path,
            tables=tables_dict,
            all_table_names=all_table_names,
        )
        return self._catalog

    def format_table_schema(self, table: TableSchema, include_samples: bool = True) -> str:
        """Formats a single table's schema, constraints, and sample data into clean markdown."""
        lines = [f"### Table: `{table.table_name}` ({table.row_count} total rows)"]

        # Columns
        lines.append("**Columns:**")
        for col in table.columns:
            pk_badge = " [PK]" if col.is_primary_key else ""
            null_badge = " NOT NULL" if not col.nullable else ""
            lines.append(f"- `{col.name}` ({col.data_type}){pk_badge}{null_badge}")

        # Foreign Keys
        if table.foreign_keys:
            lines.append("**Foreign Keys / Relationships:**")
            for fk in table.foreign_keys:
                lines.append(f"- `{table.table_name}.{fk.from_column}` -> `{fk.to_table}.{fk.to_column}`")

        # Sample rows
        if include_samples and table.sample_rows:
            lines.append("**Sample Rows:**")
            lines.append("```json")
            lines.append(json.dumps(table.sample_rows, indent=2, default=str))
            lines.append("```")

        return "\n".join(lines)

    def format_whole_schema_prompt(self, include_samples: bool = True) -> str:
        """
        Approach A (Whole Schema):
        Formats the complete database catalog into a structured context string.
        """
        catalog = self.get_catalog()
        sections = [
            "## Database Schema (SQLite)",
            f"Database contains {len(catalog.all_table_names)} tables: {', '.join([f'`{t}`' for t in catalog.all_table_names])}\n"
        ]

        for tbl_name in catalog.all_table_names:
            tbl = catalog.tables[tbl_name]
            sections.append(self.format_table_schema(tbl, include_samples=include_samples))
            sections.append("---")

        return "\n\n".join(sections)

    def format_table_summary_prompt(self) -> str:
        """
        Generates a concise overview of all available tables and their column names
        for the Table Selection LLM step in Approach B.
        """
        catalog = self.get_catalog()
        lines = ["## Available Tables & Column Overview:"]
        for tbl_name in catalog.all_table_names:
            tbl = catalog.tables[tbl_name]
            col_list = ", ".join([c.name for c in tbl.columns])
            lines.append(f"- **`{tbl_name}`**: ({col_list})")
        return "\n".join(lines)

    def format_selected_tables_prompt(self, selected_tables: List[str], include_samples: bool = True) -> str:
        """
        Approach B (Table Selection):
        Formats only the specified subset of tables, plus relevant foreign key targets.
        """
        catalog = self.get_catalog()
        valid_selected: Set[str] = set()

        for t in selected_tables:
            # Case-insensitive matching against real table names
            for actual_tbl in catalog.all_table_names:
                if t.strip().lower() == actual_tbl.lower():
                    valid_selected.add(actual_tbl)
                    break

        # If no valid tables matched, fall back to all tables safely
        if not valid_selected:
            valid_selected = set(catalog.all_table_names)

        # Include linked foreign key tables to prevent join errors
        expanded_tables = set(valid_selected)
        for tbl_name in valid_selected:
            tbl = catalog.tables[tbl_name]
            for fk in tbl.foreign_keys:
                if fk.to_table in catalog.tables:
                    expanded_tables.add(fk.to_table)

        sections = [
            "## Focused Database Schema (Selected Subgraph)",
            f"Included Tables: {', '.join([f'`{t}`' for t in sorted(expanded_tables)])}\n"
        ]

        for tbl_name in sorted(expanded_tables):
            tbl = catalog.tables[tbl_name]
            sections.append(self.format_table_schema(tbl, include_samples=include_samples))
            sections.append("---")

        return "\n\n".join(sections)
