"""
Configuration management for the Natural Language -> SQL engine.
Handles environment variables, default model selection, timeouts, and security settings.
"""

import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    # LLM Settings
    DEFAULT_PROVIDER: str = os.getenv("LLM_PROVIDER", "anthropic")  # anthropic | openai | mock
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    OPENAI_BASE_URL: Optional[str] = os.getenv("OPENAI_BASE_URL")

    DEFAULT_MODEL: str = os.getenv("LLM_MODEL", "claude-3-5-sonnet-20241022")
    DEFAULT_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.0"))
    MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "1024"))

    # Engine & Security Settings
    DEFAULT_DB_PATH: str = os.getenv("DB_PATH", "store.db")
    MAX_SELF_CORRECTION_RETRIES: int = int(os.getenv("MAX_RETRIES", "2"))
    QUERY_TIMEOUT_SECONDS: float = float(os.getenv("QUERY_TIMEOUT_SECONDS", "5.0"))
    MAX_RESULT_ROWS: int = int(os.getenv("MAX_RESULT_ROWS", "100"))
    DEFAULT_APPROACH: str = os.getenv("DEFAULT_APPROACH", "whole_schema")  # whole_schema | table_selection

    # Sample row limits for schema introspection
    SCHEMA_SAMPLE_ROWS: int = int(os.getenv("SCHEMA_SAMPLE_ROWS", "3"))


config = Config()
