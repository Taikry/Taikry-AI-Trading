"""
Migration Center & Versioned Schema Diff Engine for ZYROX AI Platform.
Calculates structural diffs, generates forward/rollback PostgreSQL DDL,
detects destructive changes, and enforces production preflight safety gates.
"""

import os
import time
import uuid
import datetime
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy import text
from taikry.config import ENVIRONMENT as DEFAULT_ENVIRONMENT
from taikry.database.session import engine

logger = logging.getLogger("taikry.schema.migration_engine")


class MigrationEngine:
    """Manages schema diffing, DDL generation, and versioned migration logs."""

    def __init__(self):
        self.engine = engine
        self._ensure_migration_table()

    def _ensure_migration_table(self):
        """Creates schema_migrations tracking table idempotently."""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        id VARCHAR(64) PRIMARY KEY,
                        migration_name VARCHAR(255) NOT NULL,
                        environment VARCHAR(50) NOT NULL,
                        applied_by VARCHAR(255) NOT NULL,
                        applied_at TIMESTAMPTZ NOT NULL,
                        duration_ms FLOAT NOT NULL,
                        upgrade_sql TEXT NOT NULL,
                        downgrade_sql TEXT,
                        is_destructive BOOLEAN NOT NULL DEFAULT FALSE,
                        status VARCHAR(50) NOT NULL,
                        error_message TEXT
                    );
                """))
                conn.commit()
        except Exception as exc:
            logger.warning(f"Notice during schema_migrations initialization: {exc}")

    def calculate_diff(
        self,
        target_schema: Dict[str, Any],
        source_schema: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Compares source schema (current live DB) against target schema (diagram or AI proposal).
        Returns detailed structural diff with destructive flags.
        """
        if not source_schema:
            from taikry.schema.introspector import schema_introspector
            source_schema = schema_introspector.introspect_all()

        current_tables = {t["name"]: t for t in source_schema.get("tables", [])}
        target_tables = {t["name"]: t for t in target_schema.get("tables", [])}

        tables_to_create = []
        tables_to_drop = []
        columns_to_add = []
        columns_to_drop = []
        destructive_warnings = []
        upgrade_statements = []
        downgrade_statements = []

        # 1. New Tables
        for t_name, t_def in target_tables.items():
            if t_name not in current_tables:
                tables_to_create.append(t_name)
                # Build CREATE TABLE statement
                col_defs = []
                for c in t_def.get("columns", []):
                    c_line = f"    {c['name']} {c['type']}"
                    if not c.get("nullable", True):
                        c_line += " NOT NULL"
                    if c.get("default"):
                        c_line += f" DEFAULT {c['default']}"
                    col_defs.append(c_line)

                pks = [c["name"] for c in t_def.get("columns", []) if c.get("is_primary_key")]
                if pks:
                    col_defs.append(f"    CONSTRAINT pk_{t_name} PRIMARY KEY ({', '.join(pks)})")

                stmt = f"CREATE TABLE IF NOT EXISTS {t_name} (\n" + ",\n".join(col_defs) + "\n);"
                upgrade_statements.append(stmt)
                downgrade_statements.append(f"DROP TABLE IF EXISTS {t_name} CASCADE;")

            else:
                # 2. Existing table: check column diffs
                curr_cols = {c["name"]: c for c in current_tables[t_name].get("columns", [])}
                tgt_cols = {c["name"]: c for c in t_def.get("columns", [])}

                for col_name, c_def in tgt_cols.items():
                    if col_name not in curr_cols:
                        columns_to_add.append(f"{t_name}.{col_name}")
                        add_stmt = f"ALTER TABLE {t_name} ADD COLUMN IF NOT EXISTS {col_name} {c_def['type']}"
                        if not c_def.get("nullable", True) and c_def.get("default"):
                            add_stmt += f" NOT NULL DEFAULT {c_def['default']}"
                        upgrade_statements.append(add_stmt + ";")
                        downgrade_statements.append(f"ALTER TABLE {t_name} DROP COLUMN IF EXISTS {col_name};")

                for col_name in curr_cols.keys():
                    if col_name not in tgt_cols:
                        columns_to_drop.append(f"{t_name}.{col_name}")
                        destructive_warnings.append(f"CRITICAL: Dropping column {t_name}.{col_name} will permanently delete existing data.")
                        upgrade_statements.append(f"ALTER TABLE {t_name} DROP COLUMN IF EXISTS {col_name};")

        # 3. Check for dropped tables
        for t_name in current_tables.keys():
            if t_name not in target_tables and target_tables:  # only if target is not empty
                # Avoid dropping core system tables unless explicitly commanded
                tables_to_drop.append(t_name)
                destructive_warnings.append(f"HIGH RISK: Table {t_name} is absent from target schema. Dropping will destroy all records.")

        is_destructive = bool(columns_to_drop or tables_to_drop or destructive_warnings)

        return {
            "has_changes": bool(upgrade_statements),
            "is_destructive": is_destructive,
            "destructive_warnings": destructive_warnings,
            "summary": {
                "tables_to_create": tables_to_create,
                "tables_to_drop": tables_to_drop,
                "columns_to_add": columns_to_add,
                "columns_to_drop": columns_to_drop
            },
            "upgrade_sql": "\n\n".join(upgrade_statements) if upgrade_statements else "-- No schema alterations required; target matches live database.",
            "downgrade_sql": "\n\n".join(downgrade_statements) if downgrade_statements else "-- No rollback statements required."
        }

    def apply_migration(
        self,
        migration_name: str,
        upgrade_sql: str,
        downgrade_sql: Optional[str] = None,
        environment: str = "local",
        applied_by: str = "admin",
        confirm_production_risk: bool = False
    ) -> Dict[str, Any]:
        """Executes reviewed migration and records in audit history."""
        # The active database environment is server configuration. Ignore any
        # caller-supplied environment value, and never permit production DDL
        # through this request-facing migration service.
        environment = (os.getenv("ENVIRONMENT") or DEFAULT_ENVIRONMENT or "production").strip().lower()
        if environment == "production":
            return {
                "status": "BLOCKED",
                "error": "Production migrations are blocked through Schema Studio. Use the reviewed release migration process."
            }

        mig_id = str(uuid.uuid4())[:8]
        start_time = time.time()
        is_destructive = "DROP " in upgrade_sql.upper()

        statements = [s.strip() for s in upgrade_sql.split(";") if s.strip()]
        try:
            with self.engine.connect() as conn:
                for stmt in statements:
                    conn.execute(text(stmt))
                conn.commit()

            duration_ms = round((time.time() - start_time) * 1000, 2)
            self._record_history(
                mig_id=mig_id,
                name=migration_name,
                env=environment,
                applied_by=applied_by,
                duration_ms=duration_ms,
                upgrade_sql=upgrade_sql,
                downgrade_sql=downgrade_sql,
                is_destructive=is_destructive,
                status="SUCCESS",
                error_msg=None
            )

            return {
                "status": "SUCCESS",
                "migration_id": mig_id,
                "statements_executed": len(statements),
                "duration_ms": duration_ms
            }

        except Exception as exc:
            duration_ms = round((time.time() - start_time) * 1000, 2)
            logger.error(f"Migration execution failed: {exc}")
            self._record_history(
                mig_id=mig_id,
                name=migration_name,
                env=environment,
                applied_by=applied_by,
                duration_ms=duration_ms,
                upgrade_sql=upgrade_sql,
                downgrade_sql=downgrade_sql,
                is_destructive=is_destructive,
                status="FAILED",
                error_msg=str(exc)
            )
            return {
                "status": "ERROR",
                "migration_id": mig_id,
                "error": str(exc),
                "duration_ms": duration_ms
            }

    def _record_history(
        self,
        mig_id: str,
        name: str,
        env: str,
        applied_by: str,
        duration_ms: float,
        upgrade_sql: str,
        downgrade_sql: Optional[str],
        is_destructive: bool,
        status: str,
        error_msg: Optional[str]
    ):
        try:
            with self.engine.connect() as conn:
                conn.execute(text("""
                    INSERT INTO schema_migrations (
                        id, migration_name, environment, applied_by, applied_at,
                        duration_ms, upgrade_sql, downgrade_sql, is_destructive,
                        status, error_message
                    ) VALUES (
                        :id, :name, :env, :applied_by, :applied_at,
                        :duration_ms, :upgrade_sql, :downgrade_sql, :is_destructive,
                        :status, :error_message
                    )
                """), {
                    "id": mig_id,
                    "name": name,
                    "env": env,
                    "applied_by": applied_by,
                    "applied_at": datetime.datetime.now(datetime.timezone.utc),
                    "duration_ms": duration_ms,
                    "upgrade_sql": upgrade_sql,
                    "downgrade_sql": downgrade_sql,
                    "is_destructive": is_destructive,
                    "status": status,
                    "error_message": error_msg
                })
                conn.commit()
        except Exception as exc:
            logger.warning(f"Could not record migration in history table: {exc}")

    def get_migration_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves list of applied and failed schema migrations."""
        try:
            with self.engine.connect() as conn:
                res = conn.execute(text(f"""
                    SELECT id, migration_name, environment, applied_by, applied_at,
                           duration_ms, upgrade_sql, downgrade_sql, is_destructive, status, error_message
                    FROM schema_migrations
                    ORDER BY applied_at DESC
                    LIMIT {limit}
                """))
                rows = []
                for r in res.fetchall():
                    rows.append({
                        "id": r[0],
                        "migration_name": r[1],
                        "environment": r[2],
                        "applied_by": r[3],
                        "applied_at": str(r[4]),
                        "duration_ms": r[5],
                        "upgrade_sql": r[6],
                        "downgrade_sql": r[7],
                        "is_destructive": bool(r[8]),
                        "status": r[9],
                        "error_message": r[10]
                    })
                return rows
        except Exception as exc:
            logger.debug(f"Could not fetch migration history: {exc}")
            return []


migration_engine = MigrationEngine()

