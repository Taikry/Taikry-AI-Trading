"""Add payment-facing metadata to the existing plan catalog.

Payment invoice, transaction, and webhook tables are created from SQLAlchemy
metadata. This migration adds the missing payment-plan metadata to existing
``subscription_plans`` rows without changing user or subscription records.
"""
import logging

from sqlalchemy import inspect, text

logger = logging.getLogger("taikry.database.migrate_payments")

_NEW_COLUMNS = {
    "description": "TEXT",
    "amount": "NUMERIC(12, 2) NOT NULL DEFAULT 0",
    "currency": "VARCHAR(3) NOT NULL DEFAULT 'USD'",
    "interval_count": "INTEGER NOT NULL DEFAULT 1",
    "trial_days": "INTEGER NOT NULL DEFAULT 0",
    "updated_at": "TIMESTAMP NULL",
}
_PAYMENT_TABLES = (
    "payment_invoices",
    "payment_transactions",
    "payment_webhook_events",
)
_SUBSCRIPTION_COLUMNS = {
    "auto_renew": "BOOLEAN NOT NULL DEFAULT FALSE",
    "invoice_id": "INTEGER NULL REFERENCES payment_invoices(id)",
}


def _database_engine():
    # Import lazily because session.init_db() calls this migration while the
    # session module is still initializing its engine.
    from taikry.database.session import engine
    return engine


def run_payment_migration() -> None:
    """Idempotently add payment-plan fields on SQLite and PostgreSQL."""
    with _database_engine().begin() as connection:
        inspector = inspect(connection)
        if not inspector.has_table("subscription_plans"):
            raise RuntimeError("subscription_plans must exist before payment migration")

        columns = {column["name"] for column in inspector.get_columns("subscription_plans")}
        amount_added = False
        for name, definition in _NEW_COLUMNS.items():
            if name not in columns:
                connection.execute(text(
                    f"ALTER TABLE subscription_plans ADD COLUMN {name} {definition}"
                ))
                amount_added = amount_added or name == "amount"

        # Keep the old price field for API compatibility while backfilling a
        # fixed-precision payment price exactly once during schema upgrade.
        if amount_added:
            connection.execute(text(
                "UPDATE subscription_plans SET amount = COALESCE(price_usd, 0)"
            ))

        # Preserve the historic trial duration and populate audit timestamps for
        # existing rows. Existing plan prices and all user data stay untouched.
        connection.execute(text(
            "UPDATE subscription_plans SET trial_days = 14 "
            "WHERE id = 'free_trial' AND trial_days = 0"
        ))
        connection.execute(text(
            "UPDATE subscription_plans SET updated_at = created_at "
            "WHERE updated_at IS NULL"
        ))

        if inspector.has_table("user_subscriptions"):
            subscription_columns = {
                column["name"] for column in inspector.get_columns("user_subscriptions")
            }
            for name, definition in _SUBSCRIPTION_COLUMNS.items():
                if name not in subscription_columns:
                    connection.execute(text(
                        f"ALTER TABLE user_subscriptions ADD COLUMN {name} {definition}"
                    ))
            connection.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_user_subscriptions_invoice_id "
                "ON user_subscriptions (invoice_id)"
            ))

    logger.info("Payment plan metadata migration completed.")


def downgrade_payment_migration() -> None:
    """Remove additive payment schema only when no payment ledger data exists."""
    with _database_engine().begin() as connection:
        inspector = inspect(connection)
        for table_name in _PAYMENT_TABLES:
            if inspector.has_table(table_name):
                row_count = connection.execute(text(
                    f"SELECT COUNT(*) FROM {table_name}"
                )).scalar_one()
                if row_count:
                    raise RuntimeError(
                        f"Cannot downgrade while {table_name} contains payment records"
                    )
        if inspector.has_table("user_subscriptions"):
            connection.execute(text("DROP INDEX IF EXISTS ix_user_subscriptions_invoice_id"))
            subscription_columns = {
                column["name"] for column in inspect(connection).get_columns("user_subscriptions")
            }
            for name in reversed(tuple(_SUBSCRIPTION_COLUMNS)):
                if name in subscription_columns:
                    connection.execute(text(
                        f"ALTER TABLE user_subscriptions DROP COLUMN {name}"
                    ))

        for table_name in reversed(_PAYMENT_TABLES):
            if inspector.has_table(table_name):
                connection.execute(text(f"DROP TABLE {table_name}"))

        if not inspector.has_table("subscription_plans"):
            return
        columns = {column["name"] for column in inspector.get_columns("subscription_plans")}
        for name in reversed(tuple(_NEW_COLUMNS)):
            if name in columns:
                connection.execute(text(
                    f"ALTER TABLE subscription_plans DROP COLUMN {name}"
                ))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_payment_migration()
