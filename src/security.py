"""
Defense-in-depth security layer for Natural Language -> SQL.
Enforces multi-tier validation: prompt isolation, token-level AST inspection,
statement cardinality checks, and forbidden function blocking.
"""

import re
from typing import List, Optional, Set, Tuple
import sqlparse
from sqlparse.sql import Statement, Token, TokenList
from sqlparse.tokens import DDL, DML, Keyword, Punctuation

from src.models import QueryStatus, ValidationResult


# Explicitly forbidden SQL keyword tokens and statements
FORBIDDEN_KEYWORDS: Set[str] = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "CREATE",
    "TRUNCATE",
    "REPLACE",
    "ATTACH",
    "DETACH",
    "PRAGMA",
    "GRANT",
    "REVOKE",
    "VACUUM",
    "REINDEX",
    "EXEC",
    "EXECUTE",
    "UPSERT",
    "MERGE",
}

# Forbidden SQLite internal functions or exploit primitives
FORBIDDEN_FUNCTIONS: Set[str] = {
    "LOAD_EXTENSION",
    "READFILE",
    "WRITEFILE",
    "EDIT",
    "FTS3_TOKENIZER",
}

# Prompt injection heuristics (case-insensitive patterns)
PROMPT_INJECTION_PATTERNS: List[re.Pattern] = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", re.IGNORECASE),
    re.compile(r"system\s*:\s*you\s+are", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?rules", re.IGNORECASE),
    re.compile(r"drop\s+table", re.IGNORECASE),
    re.compile(r"delete\s+from", re.IGNORECASE),
    re.compile(r"insert\s+into", re.IGNORECASE),
    re.compile(r"update\s+\w+\s+set", re.IGNORECASE),
    re.compile(r"alter\s+table", re.IGNORECASE),
    re.compile(r"truncate\s+table", re.IGNORECASE),
    re.compile(r"attach\s+database", re.IGNORECASE),
    re.compile(r"pragma\s+\w+", re.IGNORECASE),
    re.compile(r"<\s*script\s*>", re.IGNORECASE),
    re.compile(r"\[\s*system\s*\]", re.IGNORECASE),
    re.compile(r"bypass\s+security", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
]


class SecurityEngine:
    """
    Security verification engine guarding input prompts and output SQL.
    """

    @staticmethod
    def inspect_prompt_injection(user_prompt: str) -> Tuple[bool, Optional[str]]:
        """
        Inspects raw user prompt for prompt injection patterns or explicit destruction requests.
        Returns (is_suspicious, reason).
        """
        prompt_clean = user_prompt.strip()

        for pattern in PROMPT_INJECTION_PATTERNS:
            if pattern.search(prompt_clean):
                return True, f"Suspicious prompt pattern detected matching security rule: {pattern.pattern}"

        return False, None

    @staticmethod
    def extract_clean_sql(raw_llm_text: str) -> str:
        """
        Extracts raw SQL from markdown code fences or plain text.
        Strips comments, trailing semicolons, and surrounding formatting.
        """
        if not raw_llm_text:
            return ""

        text = raw_llm_text.strip()

        # Extract from ```sql ... ``` or ``` ... ```
        fence_match = re.search(r"```(?:sql)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
        if fence_match:
            text = fence_match.group(1).strip()

        # Remove line comments and block comments
        text = re.sub(r"--.*$", "", text, flags=re.MULTILINE)
        text = re.sub(r"/\*[\s\S]*?\*/", "", text)

        # Strip trailing whitespace and semicolons
        text = text.strip()
        while text.endswith(";"):
            text = text[:-1].strip()

        return text

    @classmethod
    def validate_sql_ast(cls, sql_query: str) -> ValidationResult:
        """
        Performs deep AST parsing and lexical validation on candidate SQL.
        Guarantees:
        1. Query is non-empty.
        2. Exactly 1 SQL statement is present (no semicolon chaining / stacked queries).
        3. Root statement type is SELECT or WITH (CTE).
        4. Zero forbidden DML/DDL keywords are present anywhere in the token stream.
        5. Zero dangerous functions/pragmas are invoked.
        """
        if not sql_query or not sql_query.strip():
            return ValidationResult(
                is_valid=False,
                status=QueryStatus.REFUSED,
                error_message="Empty SQL query provided.",
            )

        clean_sql = sql_query.strip()

        # 1. Parse AST with sqlparse
        parsed = sqlparse.parse(clean_sql)
        if not parsed:
            return ValidationResult(
                is_valid=False,
                status=QueryStatus.REFUSED,
                error_message="Failed to parse SQL into valid AST statements.",
            )

        # 2. Enforce single-statement rule (reject multi-query execution)
        non_empty_statements = [s for s in parsed if str(s).strip() and str(s).strip() != ";"]
        if len(non_empty_statements) != 1:
            return ValidationResult(
                is_valid=False,
                status=QueryStatus.REFUSED,
                error_message=f"Multi-statement execution rejected ({len(non_empty_statements)} statements found). Only single SELECT queries are permitted.",
            )

        stmt = non_empty_statements[0]

        # 3. Verify root statement type is SELECT or WITH
        stmt_type = stmt.get_type().upper()
        if stmt_type not in ("SELECT", "UNKNOWN"):
            return ValidationResult(
                is_valid=False,
                status=QueryStatus.REFUSED,
                error_message=f"Forbidden statement type '{stmt_type}'. Only SELECT statements are permitted.",
            )

        # Check first token for CTE (WITH) or SELECT
        first_token = stmt.token_first(skip_ws=True, skip_cm=True)
        if not first_token:
            return ValidationResult(
                is_valid=False,
                status=QueryStatus.REFUSED,
                error_message="No executable SQL tokens found in statement.",
            )

        first_token_val = first_token.value.upper()
        if first_token_val not in ("SELECT", "WITH", "EXPLAIN"):
            return ValidationResult(
                is_valid=False,
                status=QueryStatus.REFUSED,
                error_message=f"Statement must begin with SELECT or WITH, found '{first_token_val}'.",
            )

        # 4. Deep recursive token stream inspection for forbidden keywords & functions
        referenced_tables: List[str] = []

        def inspect_tokens(token_list: TokenList) -> Optional[str]:
            for token in token_list.tokens:
                # Check for sub-token lists (recursively)
                if token.is_group:
                    err = inspect_tokens(token)
                    if err:
                        return err

                # Token value checks
                val = token.value.strip().upper()
                if not val:
                    continue

                # Keyword check
                if val in FORBIDDEN_KEYWORDS:
                    return f"Forbidden keyword detected in SQL AST: '{val}'"

                # Function name check
                clean_fn_name = re.sub(r"[\(\)]", "", val)
                if clean_fn_name in FORBIDDEN_FUNCTIONS:
                    return f"Dangerous function invocation detected: '{clean_fn_name}'"

            return None

        forbidden_error = inspect_tokens(stmt)
        if forbidden_error:
            return ValidationResult(
                is_valid=False,
                status=QueryStatus.REFUSED,
                error_message=forbidden_error,
            )

        # 5. Regex sanity check across entire statement text for hidden dangerous keywords
        raw_upper = clean_sql.upper()
        for kw in FORBIDDEN_KEYWORDS:
            if re.search(rf"\b{kw}\b", raw_upper):
                return ValidationResult(
                    is_valid=False,
                    status=QueryStatus.REFUSED,
                    error_message=f"Forbidden keyword '{kw}' detected in query text.",
                )

        return ValidationResult(
            is_valid=True,
            status=QueryStatus.OK,
            sanitized_sql=clean_sql,
            referenced_tables=referenced_tables,
        )
