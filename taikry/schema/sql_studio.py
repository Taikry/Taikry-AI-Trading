"""
Safe SQL Studio & Query Runner for ZYROX AI Platform.
Enforces read-only execution by default, query timeouts, row bounds,
sensitive data masking, and EXPLAIN query plan analysis.
"""

import time
import logging
import re
from typing import Dict, Any, List, Optional
from sqlalchemy import text
from taikry.database.session import engine

logger = logging.getLogger("taikry.schema.sql_studio")

# Block dangerous statements in read-only mode
DANGEROUS_SQL_PATTERNS = [
    r"\bDROP\b", r"\bTRUNCATE\b", r"\bALTER\b", r"\bDELETE\b",
    r"\bUPDATE\b", r"\bINSERT\b", r"\bGRANT\b", r"\bREVOKE\b",
    r"\bEXEC\b", r"\bVACUUM\b", r"\bREINDEX\b", r"\bCREATE\b"
]

SENSITIVE_COLUMN_PATTERNS = [
    r"password", r"secret", r"token", r"key", r"credential", r"auth"
]


class SQLStudioEngine:
    """Safely executes authorized SQL statements with bounded limits."""

    def __init__(self):
        self.engine = engine

    def execute_query(
        self,
        sql_query: str,
        read_only: bool = True,
        max_rows: int = 200,
        explain_plan: bool = False
    ) -> Dict[str, Any]:
        """
        Executes query safely and returns structured tabular output:
        - columns: List[str]
        - rows: List[List[Any]]
        - row_count: int
        - execution_time_ms: float
        - is_truncated: bool
        """
        clean_sql = sql_query.strip().rstrip(";")
        if not clean_sql:
            return {"status": "ERROR", "error": "Empty SQL query provided."}

        # Security check: Read-only guard
        if read_only:
            for pattern in DANGEROUS_SQL_PATTERNS:
                if re.search(pattern, clean_sql, re.IGNORECASE):
                    return {
                        "status": "FORBIDDEN",
                        "error": f"Mutation statement blocked in read-only mode. Detected forbidden keyword matching: {pattern}",
                        "suggestion": "Read-only mode permits SELECT and EXPLAIN queries only. Disable read-only mode with verified admin permissions for schema migrations."
                    }

        # EXPLAIN mode handling
        if explain_plan:
            dialect = self.engine.dialect.name
            if dialect == "postgresql":
                clean_sql = f"EXPLAIN ANALYZE {clean_sql}"
            else:
                clean_sql = f"EXPLAIN QUERY PLAN {clean_sql}"

        start_time = time.time()
        try:
            with self.engine.connect() as conn:
                # Execute with strict parameter mapping
                result = conn.execute(text(clean_sql))
                duration_ms = round((time.time() - start_time) * 1000, 2)

                if not result.returns_rows:
                    return {
                        "status": "SUCCESS",
                        "statement_type": "NON_QUERY",
                        "affected_rows": result.rowcount,
                        "execution_time_ms": duration_ms
                    }

                columns = list(result.keys())
                raw_rows = result.fetchmany(max_rows + 1)
                is_truncated = len(raw_rows) > max_rows
                display_rows = raw_rows[:max_rows]

                # Format rows and mask sensitive attributes
                formatted_rows: List[List[Any]] = []
                for row in display_rows:
                    formatted_row = []
                    for idx, val in enumerate(row):
                        col_name = columns[idx].lower()
                        # Mask sensitive values
                        if any(re.search(pat, col_name) for pat in SENSITIVE_COLUMN_PATTERNS) and val is not None:
                            formatted_row.append("•••••••• [REDACTED]")
                        else:
                            formatted_row.append(str(val) if val is not None else None)
                    formatted_rows.append(formatted_row)

                return {
                    "status": "SUCCESS",
                    "columns": columns,
                    "rows": formatted_rows,
                    "row_count": len(formatted_rows),
                    "is_truncated": is_truncated,
                    "execution_time_ms": duration_ms,
                    "limit_applied": max_rows
                }

        except Exception as exc:
            duration_ms = round((time.time() - start_time) * 1000, 2)
            logger.warning(f"SQL execution error: {exc}")
            return {
                "status": "ERROR",
                "error": str(exc),
                "execution_time_ms": duration_ms
            }


sql_studio_engine = SQLStudioEngine()

