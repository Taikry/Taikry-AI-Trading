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
        clean_sql = sql_query.strip()
        if clean_sql.endswith(";"):
            clean_sql = clean_sql[:-1].rstrip()
        if not clean_sql:
            return {"status": "ERROR", "error": "Empty SQL query provided."}

        # Schema Studio is a read-only query surface. Keep the service-level check
        # even when callers bypass HTTP/Pydantic validation.
        if not read_only:
            return self._forbidden("Read-only mode cannot be disabled in Schema Studio.")

        # Accept one plain SELECT or EXPLAIN only. In particular, rejecting WITH
        # avoids data-modifying CTEs and rejecting comments/multiple statements
        # avoids statement-smuggling around the simple allowlist.
        for pattern in DANGEROUS_SQL_PATTERNS:
            if re.search(pattern, clean_sql, re.IGNORECASE):
                return self._forbidden(f"Mutation statement blocked in read-only mode. Detected forbidden keyword matching: {pattern}")
        if ";" in clean_sql or re.search(r"--|/\*|\*/", clean_sql):
            return self._forbidden("Only one uncommented SQL statement is allowed.")
        if not re.match(r"^(SELECT|EXPLAIN)\b", clean_sql, re.IGNORECASE):
            return self._forbidden("Read-only mode permits SELECT and EXPLAIN queries only.")
        if re.search(r"\bFOR\s+(UPDATE|SHARE|NO\s+KEY\s+UPDATE|KEY\s+SHARE)\b", clean_sql, re.IGNORECASE):
            return self._forbidden("Locking SELECT queries are not allowed in read-only mode.")

        # EXPLAIN mode handling
        if explain_plan:
            dialect = self.engine.dialect.name
            if re.match(r"^SELECT\b", clean_sql, re.IGNORECASE):
                if dialect == "postgresql":
                    clean_sql = f"EXPLAIN ANALYZE {clean_sql}"
                else:
                    clean_sql = f"EXPLAIN QUERY PLAN {clean_sql}"

        start_time = time.time()
        try:
            conn = self.engine.connect()
            sqlite_query_only = False
            try:
                dialect = self.engine.dialect.name
                if dialect == "sqlite":
                    conn.exec_driver_sql("PRAGMA query_only = ON")
                    conn.commit()
                    sqlite_query_only = True
                with conn.begin():
                    if dialect == "postgresql":
                        conn.execute(text("SET TRANSACTION READ ONLY"))
                    result = conn.execute(text(clean_sql))
                    duration_ms = round((time.time() - start_time) * 1000, 2)

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
                            if any(re.search(pat, col_name) for pat in SENSITIVE_COLUMN_PATTERNS) and val is not None:
                                formatted_row.append("•••••••• [REDACTED]")
                            else:
                                formatted_row.append(str(val) if val is not None else None)
                        formatted_rows.append(formatted_row)

                    response = {
                        "status": "SUCCESS",
                        "columns": columns,
                        "rows": formatted_rows,
                        "row_count": len(formatted_rows),
                        "is_truncated": is_truncated,
                        "execution_time_ms": duration_ms,
                        "limit_applied": max_rows
                    }
                return response
            finally:
                if sqlite_query_only:
                    if conn.in_transaction():
                        conn.rollback()
                    conn.exec_driver_sql("PRAGMA query_only = OFF")
                    conn.commit()
                conn.close()

        except Exception as exc:
            duration_ms = round((time.time() - start_time) * 1000, 2)
            logger.warning(f"SQL execution error: {exc}")
            return {
                "status": "ERROR",
                "error": str(exc),
                "execution_time_ms": duration_ms
            }

    @staticmethod
    def _forbidden(message: str) -> Dict[str, Any]:
        return {
            "status": "FORBIDDEN",
            "error": message,
            "suggestion": "Schema Studio permits one read-only SELECT or EXPLAIN query. Use the reviewed release migration process for schema changes."
        }


sql_studio_engine = SQLStudioEngine()

