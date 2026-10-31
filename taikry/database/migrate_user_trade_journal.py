"""Add per-trade journal fields and user-configurable TP/SL alert preference."""

import logging

from sqlalchemy import inspect, text

logger = logging.getLogger("taikry.database.migrate_user_trade_journal")


def run_migration(database_engine=None) -> None:
    if database_engine is None:
        from taikry.database.session import engine
        database_engine = engine

    with database_engine.begin() as connection:
        inspector = inspect(connection)
        if not inspector.has_table("paper_trades"):
            raise RuntimeError("paper_trades must exist before the journal migration")
        columns = {column["name"] for column in inspector.get_columns("paper_trades")}
        for name, definition in {
            "journal_notes": "TEXT NULL",
            "journal_tags": "JSON NULL",
            "emotion_tag": "VARCHAR(40) NULL",
            "mistake_tag": "VARCHAR(40) NULL",
        }.items():
            if name not in columns:
                connection.execute(text(
                    f"ALTER TABLE paper_trades ADD COLUMN {name} {definition}"
                ))

        if inspector.has_table("notification_preferences"):
            preference_columns = {
                column["name"] for column in inspector.get_columns("notification_preferences")
            }
            if "paper_trade_alerts" not in preference_columns:
                connection.execute(text(
                    "ALTER TABLE notification_preferences ADD COLUMN "
                    "paper_trade_alerts BOOLEAN NOT NULL DEFAULT TRUE"
                ))

    logger.info("User trade journal and alert preference migration completed.")
