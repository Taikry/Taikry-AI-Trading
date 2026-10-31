"""Add optional ownership to the paper-trade ledger for personal accounts."""

import logging

from sqlalchemy import inspect, text

logger = logging.getLogger("taikry.database.migrate_user_paper_trades")


def run_migration(database_engine=None) -> None:
    """Add a nullable user_id column while preserving legacy shared trades."""
    if database_engine is None:
        from taikry.database.session import engine
        database_engine = engine

    with database_engine.begin() as connection:
        inspector = inspect(connection)
        if not inspector.has_table("paper_trades"):
            raise RuntimeError("paper_trades must exist before the user-trade migration")

        columns = {column["name"] for column in inspector.get_columns("paper_trades")}
        if "user_id" not in columns:
            connection.execute(text(
                "ALTER TABLE paper_trades ADD COLUMN user_id INTEGER NULL REFERENCES users(id)"
            ))
        connection.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_paper_trades_user_id ON paper_trades (user_id)"
        ))

    logger.info("User paper-trade ownership migration completed.")
