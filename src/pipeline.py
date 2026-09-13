"""
End-to-end Text-to-SQL Pipeline Orchestrator.
Coordinates generation, AST validation, bounded self-correction, execution, and telemetry.
"""

import time
from typing import Optional

from src.config import config
from src.executor import QueryExecutionError, QueryExecutor
from src.generator import SQLGenerator
from src.llm import LLMClient
from src.models import PipelineResult, QueryStatus
from src.schema import SchemaEngine
from src.security import SecurityEngine
from src.validator import QueryValidator


class TextToSQLPipeline:
    """
    Production Text-to-SQL Pipeline with defense-in-depth security,
    approach selection, and bounded self-correction retries.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        llm_client: Optional[LLMClient] = None,
        approach: str = config.DEFAULT_APPROACH,
        max_retries: int = config.MAX_SELF_CORRECTION_RETRIES,
    ):
        self.db_path = db_path or config.DEFAULT_DB_PATH
        self.schema_engine = SchemaEngine(self.db_path)
        self.validator = QueryValidator(self.db_path)
        self.executor = QueryExecutor(self.db_path)
        self.llm_client = llm_client or LLMClient()
        self.generator = SQLGenerator(self.schema_engine, self.llm_client, approach=approach)
        self.max_retries = max_retries

    def run(
        self,
        question: str,
        approach: Optional[str] = None,
    ) -> PipelineResult:
        """
        Executes the full pipeline for a natural language question.

        Returns:
            PipelineResult matching the required output contract:
            {
                "sql": str | null,
                "results": list[dict] | null,
                "status": "OK" | "AMBIGUOUS" | "UNANSWERABLE" | "REFUSED",
                "note": str | null
            }
        """
        start_time = time.perf_counter()
        active_approach = approach or self.generator.approach
        catalog = self.schema_engine.get_catalog()

        total_prompt_tokens = 0
        total_completion_tokens = 0
        retries_count = 0

        # Step 1: Initial Generation
        llm_resp, schema_ctx = self.generator.generate(question, approach=active_approach)
        total_prompt_tokens += llm_resp.prompt_tokens
        total_completion_tokens += llm_resp.completion_tokens

        # Step 2: Handle Non-OK Classifications (AMBIGUOUS, UNANSWERABLE, REFUSED)
        if llm_resp.status != QueryStatus.OK or not llm_resp.sql:
            total_latency = (time.perf_counter() - start_time) * 1000.0
            return PipelineResult(
                sql=None,
                results=None,
                status=llm_resp.status,
                note=llm_resp.note or f"Query classified as {llm_resp.status.value}.",
                approach=active_approach,
                retries_count=0,
                latency_ms=total_latency,
                prompt_tokens=total_prompt_tokens,
                completion_tokens=total_completion_tokens,
                schema_tokens_estimated=len(schema_ctx) // 4,
            )

        # Step 3: Validation and Bounded Self-Correction Loop
        current_sql = SecurityEngine.extract_clean_sql(llm_resp.sql)
        validated_sql: Optional[str] = None
        last_error_message: Optional[str] = None

        while retries_count <= self.max_retries:
            # 3a. Validate AST and schema compliance
            val_result = self.validator.validate(current_sql, catalog=catalog)

            if val_result.status == QueryStatus.REFUSED:
                # Security violation is final - do not attempt self-correction
                total_latency = (time.perf_counter() - start_time) * 1000.0
                return PipelineResult(
                    sql=None,
                    results=None,
                    status=QueryStatus.REFUSED,
                    note=f"Security Refusal: {val_result.error_message}",
                    approach=active_approach,
                    retries_count=retries_count,
                    latency_ms=total_latency,
                    prompt_tokens=total_prompt_tokens,
                    completion_tokens=total_completion_tokens,
                    schema_tokens_estimated=len(schema_ctx) // 4,
                )

            if val_result.is_valid:
                validated_sql = val_result.sanitized_sql or current_sql
                break
            else:
                last_error_message = val_result.error_message
                retries_count += 1
                if retries_count > self.max_retries:
                    break

                # Self-correction re-prompt
                corr_resp = self.generator.generate_correction(
                    question=question,
                    failed_sql=current_sql,
                    error_message=last_error_message or "Invalid SQL syntax.",
                    schema_context=schema_ctx,
                )
                total_prompt_tokens += corr_resp.prompt_tokens
                total_completion_tokens += corr_resp.completion_tokens

                if corr_resp.status != QueryStatus.OK or not corr_resp.sql:
                    total_latency = (time.perf_counter() - start_time) * 1000.0
                    return PipelineResult(
                        sql=None,
                        results=None,
                        status=corr_resp.status,
                        note=corr_resp.note or "Self-correction reclassified query.",
                        approach=active_approach,
                        retries_count=retries_count,
                        latency_ms=total_latency,
                        prompt_tokens=total_prompt_tokens,
                        completion_tokens=total_completion_tokens,
                        schema_tokens_estimated=len(schema_ctx) // 4,
                    )

                current_sql = SecurityEngine.extract_clean_sql(corr_resp.sql)

        # If validation could not be satisfied within retry budget
        if not validated_sql:
            total_latency = (time.perf_counter() - start_time) * 1000.0
            return PipelineResult(
                sql=current_sql,
                results=None,
                status=QueryStatus.UNANSWERABLE,
                note=f"Validation failed after {self.max_retries} self-correction attempts. Last error: {last_error_message}",
                approach=active_approach,
                retries_count=retries_count,
                latency_ms=total_latency,
                prompt_tokens=total_prompt_tokens,
                completion_tokens=total_completion_tokens,
                schema_tokens_estimated=len(schema_ctx) // 4,
            )

        # Step 4: Safe Read-Only Execution
        try:
            results, exec_latency = self.executor.execute(validated_sql)
            total_latency = (time.perf_counter() - start_time) * 1000.0
            return PipelineResult(
                sql=validated_sql,
                results=results,
                status=QueryStatus.OK,
                note=None,
                approach=active_approach,
                retries_count=retries_count,
                latency_ms=total_latency,
                prompt_tokens=total_prompt_tokens,
                completion_tokens=total_completion_tokens,
                schema_tokens_estimated=len(schema_ctx) // 4,
            )
        except QueryExecutionError as e:
            total_latency = (time.perf_counter() - start_time) * 1000.0
            return PipelineResult(
                sql=validated_sql,
                results=None,
                status=QueryStatus.UNANSWERABLE,
                note=f"Execution error: {str(e)}",
                approach=active_approach,
                retries_count=retries_count,
                latency_ms=total_latency,
                prompt_tokens=total_prompt_tokens,
                completion_tokens=total_completion_tokens,
                schema_tokens_estimated=len(schema_ctx) // 4,
            )
