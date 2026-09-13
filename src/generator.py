"""
Text-to-SQL Generator implementing Approach A (Whole Schema) and Approach B (Table Selection).
"""

from typing import List, Optional, Tuple
from src.config import config
from src.llm import LLMClient
from src.models import ApproachType, LLMResponse, QueryStatus
from src.prompts import (
    APPROACH_A_PROMPT_TEMPLATE,
    APPROACH_B_PROMPT_TEMPLATE,
    SELF_CORRECTION_PROMPT_TEMPLATE,
    SYSTEM_PROMPT_BASE,
    TABLE_SELECTION_SYSTEM_PROMPT,
    TABLE_SELECTION_USER_TEMPLATE,
)
from src.schema import SchemaEngine
from src.security import SecurityEngine


class SQLGenerator:
    """
    Generates SQLite queries using Approach A (Whole Schema) or Approach B (Table Selection).
    """

    def __init__(
        self,
        schema_engine: SchemaEngine,
        llm_client: Optional[LLMClient] = None,
        approach: str = config.DEFAULT_APPROACH,
    ):
        self.schema_engine = schema_engine
        self.llm_client = llm_client or LLMClient()
        self.approach = approach

    def generate(
        self,
        question: str,
        approach: Optional[str] = None,
    ) -> Tuple[LLMResponse, str]:
        """
        Generates initial SQL candidate or status classification.

        Returns:
            Tuple of (LLMResponse, schema_context_used)
        """
        active_approach = approach or self.approach

        # 1. Early security screening of user question
        is_suspicious, sec_reason = SecurityEngine.inspect_prompt_injection(question)
        if is_suspicious:
            return LLMResponse(
                status=QueryStatus.REFUSED,
                sql=None,
                note=f"Security Refusal: {sec_reason}",
                latency_ms=0.5,
            ), ""

        # 2. Execute selected generation approach
        if active_approach == ApproachType.TABLE_SELECTION.value:
            return self._generate_table_selection(question)
        else:
            return self._generate_whole_schema(question)

    def _generate_whole_schema(self, question: str) -> Tuple[LLMResponse, str]:
        """
        Approach A: Prompting with the whole database schema.
        """
        schema_context = self.schema_engine.format_whole_schema_prompt(include_samples=True)
        user_prompt = APPROACH_A_PROMPT_TEMPLATE.format(
            schema_context=schema_context,
            question=question,
        )

        response = self.llm_client.complete(
            system_prompt=SYSTEM_PROMPT_BASE,
            user_prompt=user_prompt,
        )
        return response, schema_context

    def _generate_table_selection(self, question: str) -> Tuple[LLMResponse, str]:
        """
        Approach B: Two-stage generation via relevant table selection.
        """
        # Step 1: Select relevant tables
        table_overview = self.schema_engine.format_table_summary_prompt()
        select_user_prompt = TABLE_SELECTION_USER_TEMPLATE.format(
            table_overview=table_overview,
            question=question,
        )

        selection_response = self.llm_client.complete(
            system_prompt=TABLE_SELECTION_SYSTEM_PROMPT,
            user_prompt=select_user_prompt,
        )

        selected_tables = selection_response.selected_tables or []
        catalog = self.schema_engine.get_catalog()

        # Validate selected tables against real catalog
        valid_tables = [t for t in selected_tables if any(t.lower() == ct.lower() for ct in catalog.all_table_names)]
        if not valid_tables:
            # Fall back to all tables if selection returned nothing or invalid names
            valid_tables = catalog.all_table_names

        # Step 2: Generate query using focused schema context
        focused_schema_context = self.schema_engine.format_selected_tables_prompt(
            selected_tables=valid_tables,
            include_samples=True,
        )

        gen_user_prompt = APPROACH_B_PROMPT_TEMPLATE.format(
            focused_schema_context=focused_schema_context,
            question=question,
        )

        final_response = self.llm_client.complete(
            system_prompt=SYSTEM_PROMPT_BASE,
            user_prompt=gen_user_prompt,
        )

        # Aggregate metrics
        final_response.prompt_tokens += selection_response.prompt_tokens
        final_response.completion_tokens += selection_response.completion_tokens
        final_response.latency_ms += selection_response.latency_ms
        final_response.selected_tables = valid_tables

        return final_response, focused_schema_context

    def generate_correction(
        self,
        question: str,
        failed_sql: str,
        error_message: str,
        schema_context: str,
    ) -> LLMResponse:
        """
        Bounded Self-Correction step:
        Re-prompts LLM with the error diagnostic context to repair the SQL query.
        """
        user_prompt = SELF_CORRECTION_PROMPT_TEMPLATE.format(
            schema_context=schema_context,
            question=question,
            failed_sql=failed_sql,
            error_message=error_message,
        )

        response = self.llm_client.complete(
            system_prompt=SYSTEM_PROMPT_BASE,
            user_prompt=user_prompt,
        )
        return response
