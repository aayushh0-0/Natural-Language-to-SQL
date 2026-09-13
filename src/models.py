"""
Data models and type definitions for Natural Language -> SQL.
Enforces type safety and strict schema validation across the entire system.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class QueryStatus(str, Enum):
    OK = "OK"
    AMBIGUOUS = "AMBIGUOUS"
    UNANSWERABLE = "UNANSWERABLE"
    REFUSED = "REFUSED"


class ApproachType(str, Enum):
    WHOLE_SCHEMA = "whole_schema"
    TABLE_SELECTION = "table_selection"


class ColumnInfo(BaseModel):
    name: str
    data_type: str
    nullable: bool = True
    is_primary_key: bool = False
    default_value: Optional[str] = None


class ForeignKeyInfo(BaseModel):
    from_column: str
    to_table: str
    to_column: str


class TableSchema(BaseModel):
    table_name: str
    columns: List[ColumnInfo]
    foreign_keys: List[ForeignKeyInfo] = Field(default_factory=list)
    sample_rows: List[Dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0


class DatabaseCatalog(BaseModel):
    db_path: str
    tables: Dict[str, TableSchema] = Field(default_factory=dict)
    all_table_names: List[str] = Field(default_factory=list)


class LLMResponse(BaseModel):
    status: QueryStatus
    sql: Optional[str] = None
    note: Optional[str] = None
    selected_tables: Optional[List[str]] = None
    raw_response: Optional[str] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0


class ValidationResult(BaseModel):
    is_valid: bool
    status: QueryStatus = QueryStatus.OK
    error_message: Optional[str] = None
    sanitized_sql: Optional[str] = None
    referenced_tables: List[str] = Field(default_factory=list)


class PipelineResult(BaseModel):
    """
    Standard output payload for the CLI contract and downstream applications.
    Matches the required JSON specification:
    {
      "sql": str | null,
      "results": list[dict] | null,
      "status": "OK" | "AMBIGUOUS" | "UNANSWERABLE" | "REFUSED",
      "note": str | null
    }
    """
    sql: Optional[str] = None
    results: Optional[List[Dict[str, Any]]] = None
    status: QueryStatus
    note: Optional[str] = None

    # Telemetry metadata (internal diagnostics, omitted in compact CLI JSON)
    approach: Optional[str] = None
    retries_count: int = 0
    latency_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    schema_tokens_estimated: int = 0


class EvaluationTestCase(BaseModel):
    id: str
    category: str  # simple, join, aggregation, date_filter, ambiguous, unanswerable, destructive, injection
    question: str
    ground_truth_sql: Optional[str] = None
    expected_status: QueryStatus = QueryStatus.OK
    difficulty: str = "medium"
    notes: Optional[str] = None


class EvaluationResult(BaseModel):
    test_id: str
    category: str
    question: str
    approach: str
    expected_status: QueryStatus
    actual_status: QueryStatus
    status_match: bool
    ground_truth_sql: Optional[str] = None
    generated_sql: Optional[str] = None
    execution_match: bool
    error: Optional[str] = None
    latency_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    retries_count: int = 0
