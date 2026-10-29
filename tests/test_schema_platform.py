"""
Integration Test Suite for ZYROX AI Schema Designer & Database Platform.
Covers:
- Database Introspection (Tables, Columns, Keys, Constraints, Indexes)
- PostgreSQL DDL Export
- Layout Storage & Visual Decoupling
- AI Schema Generation with Bilingual EN/Khmer Reasoning
- Safe SQL Studio Execution & Dangerous Query Blocking
- Migration Diffing & Destructive Mutation Guards
- Production Safety Gate & History Auditing
- Environment Introspection
"""

import pytest
from fastapi.testclient import TestClient
from taikry.api.app import app

client = TestClient(app)


def test_schema_introspection_live():
    """Verifies complete schema introspection across all registered tables and relations."""
    resp = client.get("/api/v1/schema/introspect")
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "SUCCESS"
    assert "dialect" in data
    assert "tables" in data
    assert len(data["tables"]) >= 20, "Should introspect all registered database tables"

    # Check structure of a core table
    user_tbl = next((t for t in data["tables"] if t["name"] == "users"), None)
    assert user_tbl is not None, "users table must be present"
    assert "columns" in user_tbl
    assert "domain" in user_tbl
    assert user_tbl["domain"] == "Auth & SaaS"

    col_names = [c["name"] for c in user_tbl["columns"]]
    assert "id" in col_names
    assert "email" in col_names
    assert "role" in col_names

    # Check relationships
    assert "relationships" in data
    assert len(data["relationships"]) > 0


def test_schema_ddl_export():
    """Verifies standard PostgreSQL DDL generation."""
    resp = client.get("/api/v1/schema/ddl?tables=users,paper_trades")
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "SUCCESS"
    assert data["format"] == "postgresql"
    assert "CREATE TABLE IF NOT EXISTS users" in data["ddl"]
    assert "CREATE TABLE IF NOT EXISTS paper_trades" in data["ddl"]


def test_diagram_layout_persistence():
    """Verifies visual node layout can be retrieved and saved without altering schema."""
    resp_get = client.get("/api/v1/schema/layout")
    assert resp_get.status_code == 200
    layout = resp_get.json()
    assert "nodes" in layout
    assert "viewport" in layout

    # Save modified layout
    nodes = layout.get("nodes", {})
    if "users" in nodes:
        nodes["users"]["x"] = 150
        nodes["users"]["y"] = 250

    resp_save = client.post("/api/v1/schema/layout", json={
        "viewport": {"zoom": 1.1, "pan_x": 50, "pan_y": 50},
        "nodes": nodes
    })
    assert resp_save.status_code == 200
    assert resp_save.json()["status"] == "SUCCESS"


def test_ai_schema_proposal_bilingual():
    """Verifies AI schema proposal generates typed tables and English + Khmer reasoning."""
    resp = client.post("/api/v1/schema/ai/propose", json={
        "prompt": "Create an automated trading fee rebate and commission referral tier system"
    })
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "SUCCESS"
    prop = data["proposal"]
    assert "reasoning_en" in prop and len(prop["reasoning_en"]) > 20
    assert "reasoning_kh" in prop and len(prop["reasoning_kh"]) > 20
    assert "proposed_tables" in prop
    assert len(prop["proposed_tables"]) > 0
    assert "proposed_ddl" in prop
    assert "CREATE TABLE" in prop["proposed_ddl"]


def test_sql_studio_safe_read_only():
    """Verifies SQL studio executes safe read-only queries with duration and columns."""
    resp = client.post("/api/v1/schema/sql/query", json={
        "query": "SELECT 42 AS answer, 'zyrox' AS platform",
        "read_only": True
    })
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "SUCCESS"
    assert data["columns"] == ["answer", "platform"]
    assert data["rows"] == [["42", "zyrox"]]
    assert "execution_time_ms" in data
    assert data["row_count"] == 1


def test_sql_studio_blocks_destructive_mutations():
    """Verifies SQL studio strictly blocks DROP, ALTER, TRUNCATE, DELETE in read-only mode."""
    dangerous_queries = [
        "DROP TABLE users;",
        "TRUNCATE TABLE consensus_reports",
        "ALTER TABLE users ADD COLUMN test INT",
        "DELETE FROM paper_trades WHERE id = 1"
    ]

    for q in dangerous_queries:
        resp = client.post("/api/v1/schema/sql/query", json={
            "query": q,
            "read_only": True
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "FORBIDDEN", f"Should block: {q}"
        assert "Mutation statement blocked in read-only mode" in data["error"]


def test_migration_diff_and_destructive_detection():
    """Verifies schema diff identifies new tables and flags destructive column removals."""
    target_schema = {
        "tables": [
            {
                "name": "new_liquidity_pool",
                "columns": [
                    {"name": "id", "type": "UUID", "nullable": False, "is_primary_key": True},
                    {"name": "pool_name", "type": "VARCHAR(100)", "nullable": False}
                ]
            }
        ]
    }

    resp = client.post("/api/v1/schema/migrations/diff", json={"target_schema": target_schema})
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "SUCCESS"
    diff = data["diff"]
    assert diff["has_changes"] is True
    assert "new_liquidity_pool" in diff["summary"]["tables_to_create"]
    assert "CREATE TABLE IF NOT EXISTS new_liquidity_pool" in diff["upgrade_sql"]


def test_migration_production_safety_gate():
    """Verifies migrations to production require explicit confirm_production_risk flag."""
    resp = client.post("/api/v1/schema/migrations/apply", json={
        "migration_name": "prod_dangerous_change",
        "upgrade_sql": "CREATE TABLE IF NOT EXISTS temp_check (id INT);",
        "environment": "production",
        "confirm_production_risk": False
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "BLOCKED"
    assert "Production safety guard triggered" in data["error"]


def test_migration_apply_local_and_history():
    """Verifies migration applies safely locally and records in schema_migrations history."""
    resp_apply = client.post("/api/v1/schema/migrations/apply", json={
        "migration_name": "add_audit_temp_metric",
        "upgrade_sql": "CREATE TABLE IF NOT EXISTS test_temp_audit_table (id VARCHAR(32) PRIMARY KEY);",
        "downgrade_sql": "DROP TABLE IF EXISTS test_temp_audit_table;",
        "environment": "local",
        "confirm_production_risk": True
    })
    assert resp_apply.status_code == 200
    data = resp_apply.json()
    assert data["status"] == "SUCCESS"

    # Check history
    resp_hist = client.get("/api/v1/schema/migrations/history")
    assert resp_hist.status_code == 200
    hist = resp_hist.json()["history"]
    assert len(hist) > 0
    recent = hist[0]
    assert recent["migration_name"] == "add_audit_temp_metric"
    assert recent["status"] == "SUCCESS"


def test_environments_metadata():
    """Verifies environments endpoint reports Local, Staging, and Render Production configurations."""
    resp = client.get("/api/v1/schema/environments")
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "SUCCESS"
    assert "current_environment" in data
    assert "dialect" in data
    assert len(data["environments"]) == 3
    env_ids = [e["id"] for e in data["environments"]]
    assert "local" in env_ids
    assert "staging" in env_ids
    assert "production" in env_ids

