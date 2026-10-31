"""
FastAPI Routes for ZYROX AI Schema Studio & Database Platform.
Provides endpoints for introspection, interactive diagram layouts,
AI schema generation, safe SQL execution, and versioned migration management.
"""

import os
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Literal

from taikry.api.saas_routes import get_current_admin
from taikry.config import ENVIRONMENT

from taikry.schema.introspector import schema_introspector
from taikry.schema.layout_store import diagram_layout_store
from taikry.schema.ai_assistant import ai_schema_assistant
from taikry.schema.sql_studio import sql_studio_engine
from taikry.schema.migration_engine import migration_engine

schema_router = APIRouter(
    prefix="/api/v1/schema",
    tags=["Schema Studio"],
    dependencies=[Depends(get_current_admin)],
)


# --- Request / Response Models ---
class SaveLayoutRequest(BaseModel):
    viewport: Optional[Dict[str, Any]] = Field(default_factory=dict)
    nodes: Dict[str, Any] = Field(default_factory=dict)
    custom_relationships: Optional[List[Dict[str, Any]]] = Field(default_factory=list)


class AIProposeRequest(BaseModel):
    prompt: str = Field(..., min_length=3, max_length=5000, description="Natural language schema description (Khmer or English)")
    provider: Optional[str] = Field(default="auto", description="LLM provider: auto, groq, gemini, openrouter")


class ExecuteSQLRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=10000, description="SQL query to execute")
    read_only: Literal[True] = Field(default=True, description="Schema Studio SQL is always read-only")
    max_rows: Optional[int] = Field(default=200, ge=1, le=500, description="Maximum returned rows")
    explain_plan: Optional[bool] = Field(default=False, description="Run EXPLAIN query plan")


class MigrationDiffRequest(BaseModel):
    target_schema: Dict[str, Any] = Field(..., description="Target schema containing tables and columns")


class ApplyMigrationRequest(BaseModel):
    migration_name: str = Field(..., min_length=3, max_length=255)
    upgrade_sql: str = Field(..., min_length=5)
    downgrade_sql: Optional[str] = None
    # Retained for older clients, but never trusted. The server selects the target environment.
    environment: Optional[str] = Field(default=None, description="Ignored; target is selected by server configuration")
    confirm_production_risk: Optional[bool] = Field(default=False, description="Production migrations are not allowed through this API")


# --- Endpoint Handlers ---

@schema_router.get("/introspect")
def get_schema_introspection():
    """Returns complete database introspection: tables, columns, constraints, foreign keys, indexes."""
    return schema_introspector.introspect_all()


@schema_router.get("/ddl")
def export_postgresql_ddl(tables: Optional[str] = None):
    """Exports clean PostgreSQL DDL script for all or specified tables."""
    table_filter = [t.strip() for t in tables.split(",") if t.strip()] if tables else None
    ddl = schema_introspector.generate_postgresql_ddl(table_filter)
    return {
        "status": "SUCCESS",
        "format": "postgresql",
        "ddl": ddl
    }


@schema_router.get("/layout")
def get_diagram_layout():
    """Loads visual canvas layout (node coordinates, zoom, pan) decoupled from DDL."""
    return diagram_layout_store.load_layout()


@schema_router.post("/layout")
def save_diagram_layout(req: SaveLayoutRequest):
    """Saves visual canvas positions safely without executing database mutations."""
    success = diagram_layout_store.save_layout(req.model_dump())
    if not success:
        raise HTTPException(status_code=500, detail="Failed to persist diagram layout.")
    return {"status": "SUCCESS", "message": "Diagram layout saved."}


@schema_router.post("/ai/propose")
def propose_schema_with_ai(req: AIProposeRequest):
    """Generates PostgreSQL schema proposal with bilingual EN & Khmer architectural reasoning."""
    proposal = ai_schema_assistant.analyze_and_generate(
        prompt=req.prompt,
        provider=req.provider or "auto"
    )
    return {
        "status": "SUCCESS",
        "proposal": proposal
    }


@schema_router.post("/sql/query")
def execute_sql_query(req: ExecuteSQLRequest):
    """Safely executes SQL query with read-only default and bounds enforcement."""
    res = sql_studio_engine.execute_query(
        sql_query=req.query,
        read_only=req.read_only,
        max_rows=req.max_rows or 200,
        explain_plan=req.explain_plan
    )
    return res


@schema_router.post("/migrations/diff")
def calculate_schema_diff(req: MigrationDiffRequest):
    """Calculates diff between current live DB and target design, producing upgrade/downgrade DDL."""
    diff = migration_engine.calculate_diff(req.target_schema)
    return {
        "status": "SUCCESS",
        "diff": diff
    }


@schema_router.post("/migrations/apply")
def apply_schema_migration(req: ApplyMigrationRequest, admin=Depends(get_current_admin)):
    """Applies reviewed migration and records in audit history."""
    env = (os.getenv("ENVIRONMENT") or ENVIRONMENT or "production").strip().lower()
    res = migration_engine.apply_migration(
        migration_name=req.migration_name,
        upgrade_sql=req.upgrade_sql,
        downgrade_sql=req.downgrade_sql,
        environment=env,
        applied_by=getattr(admin, "email", None) or str(getattr(admin, "id", "admin")),
        confirm_production_risk=bool(req.confirm_production_risk)
    )
    return res


@schema_router.get("/migrations/history")
def get_migration_history(limit: int = 50):
    """Retrieves audit trail of applied and failed database migrations."""
    history = migration_engine.get_migration_history(limit=limit)
    return {
        "status": "SUCCESS",
        "total": len(history),
        "history": history
    }


@schema_router.get("/environments")
def get_environments_info():
    """Returns metadata for Local, Staging, and Render Production environments."""
    current_env = (os.getenv("ENVIRONMENT") or ENVIRONMENT or "production").strip().lower()
    dialect = schema_introspector.get_dialect_name()

    return {
        "status": "SUCCESS",
        "current_environment": current_env,
        "dialect": dialect,
        "is_production": current_env == "production",
        "environments": [
            {
                "id": "local",
                "name": "Local Development",
                "type": "SQLite / Local Postgres",
                "is_active": current_env in ("local", "development"),
                "status": "CONNECTED",
                "read_only": False
            },
            {
                "id": "staging",
                "name": "Staging (Preview)",
                "type": "PostgreSQL 16",
                "is_active": current_env == "staging",
                "status": "CONFIG_PENDING" if current_env != "staging" else "CONNECTED",
                "read_only": False
            },
            {
                "id": "production",
                "name": "Render Production",
                "type": "PostgreSQL 16 (Render Managed)",
                "is_active": current_env == "production",
                "status": "CONNECTED" if current_env == "production" else "PROTECTED",
                "read_only": current_env != "production"
            }
        ]
    }

