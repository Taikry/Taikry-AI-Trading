"""Add a version marker so legacy synthetic learning rows are not reused."""
import logging

from sqlalchemy import text

from taikry.database.session import SessionLocal, engine

logger = logging.getLogger("taikry.database.migrate_learning")


def run_learning_migration() -> None:
    """Mark pre-validation agent weights as legacy while preserving their rows."""
    db = SessionLocal()
    try:
        if engine.dialect.name == "sqlite":
            columns = db.execute(text("PRAGMA table_info(agent_learning_models)")).fetchall()
            if columns and "training_version" not in {row[1] for row in columns}:
                db.execute(text(
                    "ALTER TABLE agent_learning_models "
                    "ADD COLUMN training_version INTEGER NOT NULL DEFAULT 0"
                ))
                db.commit()
        else:
            db.execute(text(
                "ALTER TABLE agent_learning_models "
                "ADD COLUMN IF NOT EXISTS training_version INTEGER NOT NULL DEFAULT 0"
            ))
            db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    logger.info("Agent-learning schema migration completed.")
