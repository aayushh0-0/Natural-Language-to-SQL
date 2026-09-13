"""
Command Line Interface for Natural Language -> SQL.
Adheres strictly to the single-JSON stdout output specification.
"""

import argparse
import json
import sys
import os

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.llm import LLMClient
from src.models import QueryStatus
from src.pipeline import TextToSQLPipeline


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Natural Language -> SQL Engine: Query SQLite databases using natural language."
    )
    parser.add_argument(
        "--db",
        type=str,
        default="store.db",
        help="Path to SQLite database file (default: store.db)",
    )
    parser.add_argument(
        "--question",
        type=str,
        required=True,
        help="Natural language question to translate and execute",
    )
    parser.add_argument(
        "--approach",
        type=str,
        choices=["whole_schema", "table_selection"],
        default="whole_schema",
        help="Text-to-SQL approach: 'whole_schema' (Approach A) or 'table_selection' (Approach B)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="LLM model identifier (e.g. claude-3-5-sonnet-20241022, gpt-4o)",
    )
    parser.add_argument(
        "--provider",
        type=str,
        choices=["anthropic", "openai", "mock"],
        default=None,
        help="LLM provider (default: auto-detected from environment)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print diagnostic telemetry and debug logs to stderr",
    )

    args = parser.parse_args()

    if args.debug:
        sys.stderr.write(f"[DEBUG] Initializing pipeline on database '{args.db}' using approach '{args.approach}'...\n")

    try:
        llm_client = LLMClient(provider=args.provider, model=args.model)
        pipeline = TextToSQLPipeline(
            db_path=args.db,
            llm_client=llm_client,
            approach=args.approach,
        )

        result = pipeline.run(args.question, approach=args.approach)

        if args.debug:
            sys.stderr.write(f"[DEBUG] Pipeline completed in {result.latency_ms:.2f}ms with status {result.status.value}\n")
            sys.stderr.write(f"[DEBUG] Retries: {result.retries_count}, Prompt Tokens: {result.prompt_tokens}, Completion Tokens: {result.completion_tokens}\n")

        # Format exact output JSON contract
        output_payload = {
            "sql": result.sql,
            "results": result.results,
            "status": result.status.value,
            "note": result.note,
        }

        # Print strictly ONE JSON object to stdout
        sys.stdout.write(json.dumps(output_payload, indent=2, ensure_ascii=False) + "\n")
        sys.stdout.flush()
        return 0

    except Exception as e:
        if args.debug:
            sys.stderr.write(f"[ERROR] Fatal exception in ask.py: {str(e)}\n")

        error_payload = {
            "sql": None,
            "results": None,
            "status": QueryStatus.UNANSWERABLE.value,
            "note": f"System error: {str(e)}",
        }
        sys.stdout.write(json.dumps(error_payload, indent=2, ensure_ascii=False) + "\n")
        sys.stdout.flush()
        return 1


if __name__ == "__main__":
    sys.exit(main())
