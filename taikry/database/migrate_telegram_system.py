"""Add Telegram signal provenance columns without rewriting existing rows."""
from sqlalchemy import inspect, text


def run_migration(bind=None) -> None:
    if bind is None:
        from taikry.database.session import engine
        bind = engine

    inspector = inspect(bind)
    table_columns = {
        "xauusd_telegram_signals": {
            "bid_price": "ALTER TABLE xauusd_telegram_signals ADD COLUMN bid_price FLOAT",
            "ask_price": "ALTER TABLE xauusd_telegram_signals ADD COLUMN ask_price FLOAT",
            "midpoint_price": "ALTER TABLE xauusd_telegram_signals ADD COLUMN midpoint_price FLOAT",
            "quote_timestamp": "ALTER TABLE xauusd_telegram_signals ADD COLUMN quote_timestamp TIMESTAMP",
        },
        "signal_lifecycles": {
            "take_profit_3": "ALTER TABLE signal_lifecycles ADD COLUMN take_profit_3 FLOAT",
        },
        "telegram_analysis_runs": {
            "signal_candidate_id": "ALTER TABLE telegram_analysis_runs ADD COLUMN signal_candidate_id VARCHAR(64)",
            "message_type": "ALTER TABLE telegram_analysis_runs ADD COLUMN message_type VARCHAR(20) NOT NULL DEFAULT 'text'",
        },
        "notification_preferences": {
            "macro_events": "ALTER TABLE notification_preferences ADD COLUMN macro_events BOOLEAN DEFAULT TRUE",
        },
        "subscription_plans": {
            "signal_alerts_target_min_per_day": "ALTER TABLE subscription_plans ADD COLUMN signal_alerts_target_min_per_day INTEGER",
            "max_signal_alerts_per_day": "ALTER TABLE subscription_plans ADD COLUMN max_signal_alerts_per_day INTEGER",
        },
    }
    with bind.begin() as connection:
        available_tables = set(inspector.get_table_names())
        for table_name, statements in table_columns.items():
            if table_name not in available_tables:
                continue
            existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
            added_columns = set()
            for column_name, statement in statements.items():
                if column_name not in existing_columns:
                    connection.execute(text(statement))
                    added_columns.add(column_name)

            # Seed the newly introduced plan caps once, preserving any values
            # administrators may configure after this migration.
            if table_name == "subscription_plans":
                if "signal_alerts_target_min_per_day" in added_columns:
                    connection.execute(text(
                        "UPDATE subscription_plans SET signal_alerts_target_min_per_day = "
                        "CASE id WHEN 'free_trial' THEN 2 WHEN 'pro' THEN 5 WHEN 'premium' THEN 10 ELSE 0 END "
                        "WHERE signal_alerts_target_min_per_day IS NULL"
                    ))
                if "max_signal_alerts_per_day" in added_columns:
                    connection.execute(text(
                        "UPDATE subscription_plans SET max_signal_alerts_per_day = "
                        "CASE id WHEN 'free_trial' THEN 4 WHEN 'pro' THEN 10 WHEN 'premium' THEN 15 ELSE 0 END "
                        "WHERE max_signal_alerts_per_day IS NULL"
                    ))
