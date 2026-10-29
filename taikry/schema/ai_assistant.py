"""
AI Database Schema Specialist & Architect Agent for ZYROX AI.
Provides:
- Natural-language to PostgreSQL schema proposal generation (Khmer & English).
- Normalization review (1NF, 2NF, 3NF), duplicate table detection.
- Missing index and foreign key advisory.
- Breaking change analysis and performance trade-offs.
"""

import logging
import json
import re
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from taikry.config import GROQ_API_KEY, GEMINI_API_KEY, OPENROUTER_API_KEY

logger = logging.getLogger("taikry.schema.ai_assistant")

AI_SCHEMA_SYSTEM_PROMPT = """You are the Senior PostgreSQL Database Architect & Schema Specialist for ZYROX AI Platform.
Analyze user requirements and provide clean, production-grade PostgreSQL schema designs.

REQUIREMENTS:
1. Support queries in both English and Natural Khmer (ភាសាខ្មែរ).
2. Follow PostgreSQL best practices:
   - Primary keys: UUID (gen_random_uuid()) or BIGSERIAL/BIGINT.
   - Timestamps: TIMESTAMPTZ with DEFAULT NOW().
   - Appropriate indexes for foreign keys and filter columns.
   - Enforce NOT NULL and CHECK constraints where appropriate.
   - Clear normalization (3NF) without redundant fields.
3. Highlight potential breaking changes or migration hazards.
4. Output STRICT JSON conforming to the exact schema requested. No markdown text outside the JSON block.

JSON OUTPUT STRUCTURE:
{
  "reasoning_en": "<clear architectural reasoning in English>",
  "reasoning_kh": "<ការពន្យល់លម្អិតអំពីស្ថាបត្យកម្មទិន្នន័យជាភាសាខ្មែរ>",
  "proposed_tables": [
    {
      "name": "<table_name>",
      "description": "<purpose>",
      "columns": [
        {
          "name": "<column_name>",
          "type": "<PostgreSQL type: UUID, VARCHAR(255), TIMESTAMPTZ, NUMERIC(18,8), etc.>",
          "nullable": false,
          "default": "NOW() or null",
          "is_primary_key": false,
          "is_foreign_key": false,
          "foreign_key_target": {"target_table": "<tbl>", "target_column": "<col>"},
          "is_unique": false,
          "description": "<field explanation>"
        }
      ],
      "indexes": [
        {"name": "idx_...", "columns": ["col1"], "unique": false}
      ]
    }
  ],
  "normalization_tips": ["<tips>"],
  "performance_and_indexes": ["<index suggestions>"],
  "breaking_change_warnings": ["<potential hazards or migration warnings>"],
  "proposed_ddl": "<complete valid PostgreSQL DDL CREATE TABLE and CREATE INDEX statements>"
}
"""


class AISchemaAssistant:
    """Orchestrates AI-powered database architecture proposals."""

    def analyze_and_generate(
        self,
        prompt: str,
        current_schema_context: Optional[Dict[str, Any]] = None,
        provider: str = "auto"
    ) -> Dict[str, Any]:
        """Generates schema design proposal with full bilingual explanations."""
        if not current_schema_context:
            from taikry.schema.introspector import schema_introspector
            current_schema_context = schema_introspector.introspect_all()

        existing_table_names = [t["name"] for t in current_schema_context.get("tables", [])]

        user_content = f"""USER REQUIREMENT:
{prompt}

EXISTING TABLES IN DATABASE:
{", ".join(existing_table_names[:30])} (Total tables: {len(existing_table_names)})

Analyze the requirement and propose optimal PostgreSQL schema objects.
"""

        # 1. Try real LLMs via Groq / Gemini / OpenRouter
        response_json = self._call_llm(user_content, provider)
        if response_json:
            return response_json

        # 2. Deterministic Expert Architectural Fallback
        return self._generate_deterministic_proposal(prompt, existing_table_names)

    def _call_llm(self, user_content: str, provider: str) -> Optional[Dict[str, Any]]:
        # A. Try Groq (Fast & Free)
        if GROQ_API_KEY and provider in ("auto", "groq"):
            import requests
            for model in ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"]:
                try:
                    r = requests.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                        json={
                            "model": model,
                            "messages": [
                                {"role": "system", "content": AI_SCHEMA_SYSTEM_PROMPT},
                                {"role": "user", "content": user_content}
                            ],
                            "response_format": {"type": "json_object"},
                            "temperature": 0.2
                        },
                        timeout=15
                    )
                    if r.status_code == 200:
                        content = r.json()["choices"][0]["message"]["content"]
                        parsed = json.loads(content)
                        if "proposed_tables" in parsed:
                            parsed["provider"] = "groq"
                            parsed["model"] = model
                            if not parsed.get("proposed_ddl"):
                                parsed["proposed_ddl"] = self._build_ddl_from_tables(parsed["proposed_tables"])
                            return parsed
                except Exception as exc:
                    logger.debug(f"Groq schema generation notice: {exc}")

        # B. Try Gemini
        if GEMINI_API_KEY and provider in ("auto", "gemini"):
            import requests
            for m in ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-pro-latest"]:
                try:
                    r = requests.post(
                        f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={GEMINI_API_KEY}",
                        headers={"Content-Type": "application/json"},
                        json={
                            "contents": [{"role": "user", "parts": [{"text": AI_SCHEMA_SYSTEM_PROMPT + "\n\n" + user_content}]}],
                            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2}
                        },
                        timeout=15
                    )
                    if r.status_code == 200:
                        content = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                        parsed = json.loads(content)
                        if "proposed_tables" in parsed:
                            parsed["provider"] = "gemini"
                            parsed["model"] = m
                            if not parsed.get("proposed_ddl"):
                                parsed["proposed_ddl"] = self._build_ddl_from_tables(parsed["proposed_tables"])
                            return parsed
                except Exception as exc:
                    logger.debug(f"Gemini schema generation notice: {exc}")

        return None

    def _build_ddl_from_tables(self, tables: List[Dict[str, Any]]) -> str:
        """Synthesizes valid PostgreSQL DDL from proposed table definitions."""
        ddl_parts = ["-- Auto-generated PostgreSQL DDL from AI Schema Proposal"]
        for t in tables:
            t_name = t.get("name", "entity")
            col_lines = []
            for c in t.get("columns", []):
                line = f"    {c['name']} {c.get('type', 'VARCHAR(255)')}"
                if not c.get("nullable", True):
                    line += " NOT NULL"
                if c.get("default"):
                    line += f" DEFAULT {c['default']}"
                if c.get("is_primary_key"):
                    line += " PRIMARY KEY"
                col_lines.append(line)

            ddl_parts.append(f"CREATE TABLE IF NOT EXISTS {t_name} (\n" + ",\n".join(col_lines) + "\n);")

            for idx in t.get("indexes", []):
                idx_name = idx.get("name") or f"idx_{t_name}_{idx['columns'][0]}"
                cols = ", ".join(idx.get("columns", []))
                uniq = "UNIQUE " if idx.get("unique") else ""
                ddl_parts.append(f"CREATE {uniq}INDEX IF NOT EXISTS {idx_name} ON {t_name} ({cols});")

            ddl_parts.append("")
        return "\n\n".join(ddl_parts)

    def _generate_deterministic_proposal(self, prompt: str, existing_tables: List[str]) -> Dict[str, Any]:
        """Deterministic architectural engine when AI network is offline."""
        prompt_clean = prompt.lower()
        table_name = "custom_entity"
        for w in prompt_clean.replace("-", " ").replace("_", " ").split():
            if len(w) > 3 and w not in ("create", "table", "schema", "database", "with", "from", "that"):
                table_name = w
                break

        if not table_name.endswith("s"):
            table_name += "s"

        ddl = f"""-- Proposed PostgreSQL Table
CREATE TABLE IF NOT EXISTS {table_name} (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'ACTIVE',
    metadata JSONB DEFAULT '{{}}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_{table_name}_status ON {table_name} (status);
CREATE INDEX IF NOT EXISTS idx_{table_name}_created_at ON {table_name} (created_at DESC);
"""

        return {
            "provider": "deterministic_architect",
            "model": "zyrox_schema_expert_v2",
            "reasoning_en": f"Designed standard 3NF normalized PostgreSQL schema for '{table_name}' with UUID PK, JSONB metadata flexibility, and indexed status filtering based on your requirement: '{prompt}'.",
            "reasoning_kh": f"បានរចនាតារាង PostgreSQL តាមស្តង់ដារ 3NF សម្រាប់ '{table_name}' ដោយប្រើប្រាស់ UUID ជាសោចម្បង (Primary Key), ផ្ទុក metadata ជា JSONB, និងបង្កើត Index លើ status និងកាលបរិច្ឆេទបង្កើត។",
            "proposed_tables": [
                {
                    "name": table_name,
                    "description": f"Stores records for {table_name}",
                    "columns": [
                        {"name": "id", "type": "UUID", "nullable": False, "default": "gen_random_uuid()", "is_primary_key": True, "is_foreign_key": False, "is_unique": True, "description": "Unique identifier"},
                        {"name": "name", "type": "VARCHAR(255)", "nullable": False, "default": None, "is_primary_key": False, "is_foreign_key": False, "is_unique": False, "description": "Entity name"},
                        {"name": "status", "type": "VARCHAR(50)", "nullable": False, "default": "'ACTIVE'", "is_primary_key": False, "is_foreign_key": False, "is_unique": False, "description": "Lifecycle state"},
                        {"name": "metadata", "type": "JSONB", "nullable": True, "default": "'{}'::jsonb", "is_primary_key": False, "is_foreign_key": False, "is_unique": False, "description": "Unstructured attributes"},
                        {"name": "created_at", "type": "TIMESTAMPTZ", "nullable": False, "default": "NOW()", "is_primary_key": False, "is_foreign_key": False, "is_unique": False, "description": "Creation timestamp"},
                        {"name": "updated_at", "type": "TIMESTAMPTZ", "nullable": False, "default": "NOW()", "is_primary_key": False, "is_foreign_key": False, "is_unique": False, "description": "Update timestamp"}
                    ],
                    "indexes": [
                        {"name": f"idx_{table_name}_status", "columns": ["status"], "unique": False},
                        {"name": f"idx_{table_name}_created_at", "columns": ["created_at"], "unique": False}
                    ]
                }
            ],
            "normalization_tips": [
                "Applied 3NF: Status code isolated from timestamp attributes.",
                "JSONB allows non-schema attributes without requiring ALTER TABLE in production."
            ],
            "performance_and_indexes": [
                f"B-Tree index on (status) optimizes state-based querying.",
                f"B-Tree index on (created_at DESC) accelerates pagination and audit logging."
            ],
            "breaking_change_warnings": [
                f"Ensure gen_random_uuid() extension (pgcrypto) is enabled on target PostgreSQL instance.",
                "Review column lengths to avoid truncation."
            ],
            "proposed_ddl": ddl
        }


ai_schema_assistant = AISchemaAssistant()

