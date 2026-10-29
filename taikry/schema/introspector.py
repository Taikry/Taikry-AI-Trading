"""
Database Introspector for ZYROX AI Schema Platform.
Extracts schema metadata (tables, columns, types, primary keys, foreign keys,
unique constraints, indexes, record counts) across PostgreSQL and SQLite,
with fallback to SQLAlchemy Base metadata.
"""

import logging
from typing import Dict, Any, List, Optional
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from taikry.database.session import engine
from taikry.database.models import Base

logger = logging.getLogger("taikry.schema.introspector")


class SchemaIntrospector:
    """Introspects live database engines or registered SQLAlchemy models."""

    def __init__(self, target_engine: Optional[Engine] = None):
        self.engine = target_engine or engine

    def get_dialect_name(self) -> str:
        try:
            return self.engine.dialect.name
        except Exception:
            return "sqlite"

    def introspect_all(self) -> Dict[str, Any]:
        """
        Extracts complete schema structure:
        - tables: list of table schemas
        - views: list of views
        - relationships: inferred foreign key relationships
        - stats: table count, column count, relationship count
        """
        dialect = self.get_dialect_name()
        tables: List[Dict[str, Any]] = []
        views: List[Dict[str, Any]] = []
        relationships: List[Dict[str, Any]] = []

        try:
            inspector = inspect(self.engine)
            table_names = inspector.get_table_names()
            view_names = inspector.get_view_names()

            for t_name in table_names:
                table_info = self._introspect_table(inspector, t_name, dialect)
                tables.append(table_info)

                # Collect relationships from foreign keys
                for fk in table_info.get("foreign_keys", []):
                    relationships.append({
                        "id": f"rel_{t_name}_{fk['constrained_columns'][0]}_{fk['referred_table']}",
                        "source_table": t_name,
                        "source_column": fk["constrained_columns"][0] if fk["constrained_columns"] else "id",
                        "target_table": fk["referred_table"],
                        "target_column": fk["referred_columns"][0] if fk["referred_columns"] else "id",
                        "type": "one_to_many"
                    })

            for v_name in view_names:
                views.append({"name": v_name, "type": "view"})

        except Exception as exc:
            logger.warning(f"Live engine introspection notice: {exc}. Falling back to Base metadata.")
            return self._introspect_from_base_metadata()

        # If live database has no tables yet, populate from Base metadata
        if not tables:
            return self._introspect_from_base_metadata()

        total_cols = sum(len(t.get("columns", [])) for t in tables)
        return {
            "status": "SUCCESS",
            "dialect": dialect,
            "database_name": getattr(self.engine.url, "database", "taikry_market"),
            "table_count": len(tables),
            "column_count": total_cols,
            "relationship_count": len(relationships),
            "tables": tables,
            "views": views,
            "relationships": relationships
        }

    def _introspect_table(self, inspector, table_name: str, dialect: str) -> Dict[str, Any]:
        columns: List[Dict[str, Any]] = []
        pk_constraint = inspector.get_pk_constraint(table_name) or {}
        pk_cols = set(pk_constraint.get("constrained_columns", []))

        raw_cols = inspector.get_columns(table_name)
        fks = inspector.get_foreign_keys(table_name)
        indexes = inspector.get_indexes(table_name)
        uniques = inspector.get_unique_constraints(table_name)

        fk_map = {}
        for fk in fks:
            for src_col, tgt_col in zip(fk.get("constrained_columns", []), fk.get("referred_columns", [])):
                fk_map[src_col] = {
                    "target_table": fk.get("referred_table"),
                    "target_column": tgt_col
                }

        unique_cols = set()
        for u in uniques:
            for c in u.get("column_names", []):
                unique_cols.add(c)
        for idx in indexes:
            if idx.get("unique"):
                for c in idx.get("column_names", []):
                    unique_cols.add(c)

        for col in raw_cols:
            c_name = col["name"]
            is_pk = c_name in pk_cols
            is_fk = c_name in fk_map
            is_unique = c_name in unique_cols

            col_entry = {
                "name": c_name,
                "type": str(col["type"]),
                "nullable": bool(col.get("nullable", True)),
                "default": str(col.get("default", "")) if col.get("default") is not None else None,
                "is_primary_key": is_pk,
                "is_foreign_key": is_fk,
                "is_unique": is_unique,
                "foreign_key_target": fk_map.get(c_name)
            }
            columns.append(col_entry)

        row_count = self._get_approx_row_count(table_name, dialect)

        # Infer domain category for organizational grouping
        domain = self._infer_domain(table_name)

        return {
            "name": table_name,
            "domain": domain,
            "row_count": row_count,
            "columns": columns,
            "primary_key": list(pk_cols),
            "foreign_keys": fks,
            "indexes": indexes
        }

    def _get_approx_row_count(self, table_name: str, dialect: str) -> int:
        try:
            with self.engine.connect() as conn:
                res = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                return int(res.scalar() or 0)
        except Exception:
            return 0

    def _infer_domain(self, table_name: str) -> str:
        name = table_name.lower()
        if any(w in name for w in ("market", "price", "candle", "quote", "tick")):
            return "Market Data"
        if any(w in name for w in ("agent", "opinion", "consensus", "debate", "learning", "research")):
            return "AI & Intelligence"
        if any(w in name for w in ("trade", "order", "signal", "backtest", "lifecycle")):
            return "Trading & Signals"
        if any(w in name for w in ("user", "session", "token", "plan", "subscription", "trial")):
            return "Auth & SaaS"
        if any(w in name for w in ("telegram", "notify", "notification", "alert", "ticket")):
            return "Notifications"
        if any(w in name for w in ("audit", "health", "system", "log")):
            return "System & Audit"
        return "Core"

    def _introspect_from_base_metadata(self) -> Dict[str, Any]:
        """Reads schema directly from registered SQLAlchemy models."""
        tables: List[Dict[str, Any]] = []
        relationships: List[Dict[str, Any]] = []

        for t_name, table in Base.metadata.tables.items():
            columns = []
            pk_cols = [c.name for c in table.primary_key.columns]

            for c in table.columns:
                is_pk = c.name in pk_cols
                is_fk = bool(c.foreign_keys)
                fk_target = None
                if is_fk:
                    fk = next(iter(c.foreign_keys))
                    target_table = fk.column.table.name
                    target_column = fk.column.name
                    fk_target = {"target_table": target_table, "target_column": target_column}
                    relationships.append({
                        "id": f"rel_{t_name}_{c.name}_{target_table}",
                        "source_table": t_name,
                        "source_column": c.name,
                        "target_table": target_table,
                        "target_column": target_column,
                        "type": "one_to_many"
                    })

                columns.append({
                    "name": c.name,
                    "type": str(c.type),
                    "nullable": bool(c.nullable),
                    "default": str(c.default.arg) if c.default is not None and hasattr(c.default, "arg") else None,
                    "is_primary_key": is_pk,
                    "is_foreign_key": is_fk,
                    "is_unique": bool(c.unique),
                    "foreign_key_target": fk_target
                })

            tables.append({
                "name": t_name,
                "domain": self._infer_domain(t_name),
                "row_count": 0,
                "columns": columns,
                "primary_key": pk_cols,
                "foreign_keys": [{"constrained_columns": [c.name], "referred_table": c.foreign_keys.__iter__().__next__().column.table.name} for c in table.columns if c.foreign_keys],
                "indexes": [{"name": idx.name, "column_names": [c.name for c in idx.columns], "unique": idx.unique} for idx in table.indexes]
            })

        total_cols = sum(len(t.get("columns", [])) for t in tables)
        return {
            "status": "SUCCESS",
            "dialect": "postgresql",
            "database_name": "taikry_market",
            "table_count": len(tables),
            "column_count": total_cols,
            "relationship_count": len(relationships),
            "tables": tables,
            "views": [],
            "relationships": relationships
        }

    def generate_postgresql_ddl(self, tables_filter: Optional[List[str]] = None) -> str:
        """Exports clean, standard PostgreSQL DDL for all or selected tables."""
        meta = self.introspect_all()
        ddl_parts: List[str] = [
            "-- =====================================================================",
            "-- ZYROX AI TRADING — POSTGRESQL SCHEMA DDL EXPORT",
            f"-- Generated: {self.get_dialect_name().upper()} Introspection",
            "-- =====================================================================\n"
        ]

        for t in meta.get("tables", []):
            t_name = t["name"]
            if tables_filter and t_name not in tables_filter:
                continue

            ddl_parts.append(f"CREATE TABLE IF NOT EXISTS {t_name} (")
            col_lines = []
            for col in t["columns"]:
                line = f"    {col['name']} {col['type']}"
                if not col["nullable"]:
                    line += " NOT NULL"
                if col.get("default"):
                    line += f" DEFAULT {col['default']}"
                col_lines.append(line)

            if t.get("primary_key"):
                pk_str = ", ".join(t["primary_key"])
                col_lines.append(f"    CONSTRAINT pk_{t_name} PRIMARY KEY ({pk_str})")

            ddl_parts.append(",\n".join(col_lines))
            ddl_parts.append(");\n")

            # Indexes
            for idx in t.get("indexes", []):
                idx_name = idx.get("name") or f"idx_{t_name}_custom"
                cols = ", ".join(idx.get("column_names", []))
                uniq = "UNIQUE " if idx.get("unique") else ""
                if cols:
                    ddl_parts.append(f"CREATE {uniq}INDEX IF NOT EXISTS {idx_name} ON {t_name} ({cols});")

            ddl_parts.append("")

        return "\n".join(ddl_parts)


schema_introspector = SchemaIntrospector()

