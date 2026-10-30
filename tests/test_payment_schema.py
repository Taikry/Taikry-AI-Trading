from decimal import Decimal

from sqlalchemy import create_engine, inspect, text

from taikry.database.models import (
    PaymentInvoice,
    PaymentPlan,
    PaymentTransaction,
    PaymentWebhookEvent,
    SubscriptionPlan,
)
from taikry.database import migrate_payment_models


def test_payment_models_reuse_saas_plans_and_store_decimal_amounts():
    assert PaymentPlan is SubscriptionPlan
    assert {"description", "amount", "currency", "interval_count", "trial_days", "updated_at"} <= {
        column.name for column in PaymentPlan.__table__.columns
    }
    assert PaymentInvoice.__table__.c.amount.type.precision == 12
    assert PaymentInvoice.__table__.c.amount.type.scale == 2
    assert PaymentTransaction.__table__.c.amount.type.precision == 12
    assert PaymentTransaction.__table__.c.raw_response_redacted.type.__class__.__name__ == "JSON"

    invoice_foreign_keys = {fk.target_fullname for fk in PaymentInvoice.__table__.foreign_keys}
    assert {"users.id", "subscription_plans.id"} <= invoice_foreign_keys
    transaction_foreign_keys = {fk.target_fullname for fk in PaymentTransaction.__table__.foreign_keys}
    assert "payment_invoices.id" in transaction_foreign_keys


def test_payment_uniqueness_constraints_prevent_duplicate_provider_events_and_transactions():
    transaction_constraints = {
        constraint.name for constraint in PaymentTransaction.__table__.constraints
    }
    webhook_constraints = {
        constraint.name for constraint in PaymentWebhookEvent.__table__.constraints
    }
    assert "uq_payment_provider_transaction" in transaction_constraints
    assert "uq_payment_webhook_provider_event" in webhook_constraints
    assert PaymentInvoice.__table__.c.invoice_number.unique is True
    assert PaymentInvoice.__table__.c.checkout_reference.unique is True


def test_default_saas_plans_seed_fixed_precision_payment_prices():
    from taikry.database.session import SessionLocal
    from taikry.saas.entitlement_service import get_all_plans, init_default_plans

    db = SessionLocal()
    try:
        init_default_plans(db)
        plan = db.query(PaymentPlan).filter(PaymentPlan.id == "pro").one()
        assert plan.amount == Decimal("29.00")
        assert next(p for p in get_all_plans(db) if p["id"] == "pro")["price_usd"] == 29.0
    finally:
        db.close()


def test_payment_migration_is_idempotent_and_reversible(monkeypatch):
    test_engine = create_engine("sqlite:///:memory:")
    with test_engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE subscription_plans ("
            "id VARCHAR(30) PRIMARY KEY, name_en VARCHAR(50) NOT NULL, "
            "name_kh VARCHAR(50) NOT NULL, price_usd FLOAT, "
            "billing_interval VARCHAR(20), created_at TIMESTAMP)"
        ))
        connection.execute(text(
            "CREATE TABLE payment_invoices (id INTEGER PRIMARY KEY)"
        ))
        connection.execute(text(
            "CREATE TABLE user_subscriptions ("
            "id INTEGER PRIMARY KEY, user_id INTEGER, plan_id VARCHAR(30), "
            "status VARCHAR(30))"
        ))
        connection.execute(text(
            "INSERT INTO subscription_plans "
            "(id, name_en, name_kh, price_usd, billing_interval, created_at) "
            "VALUES ('free_trial', 'Free Trial', 'Trial', 0, 'trial', '2026-01-01 00:00:00')"
        ))
        connection.execute(text(
            "INSERT INTO subscription_plans "
            "(id, name_en, name_kh, price_usd, billing_interval, created_at) "
            "VALUES ('pro', 'Pro', 'Pro', 29.0, 'monthly', '2026-01-01 00:00:00')"
        ))

    monkeypatch.setattr(migrate_payment_models, "_database_engine", lambda: test_engine)
    migrate_payment_models.run_payment_migration()
    migrate_payment_models.run_payment_migration()

    with test_engine.connect() as connection:
        columns = {column["name"] for column in inspect(connection).get_columns("subscription_plans")}
        assert {"description", "amount", "currency", "interval_count", "trial_days", "updated_at"} <= columns
        subscription_columns = {
            column["name"] for column in inspect(connection).get_columns("user_subscriptions")
        }
        assert {"auto_renew", "invoice_id"} <= subscription_columns
        row = connection.execute(text(
            "SELECT currency, interval_count, trial_days, updated_at, amount "
            "FROM subscription_plans WHERE id = 'free_trial'"
        )).one()
        assert row.currency == "USD"
        assert row.interval_count == 1
        assert row.trial_days == 14
        assert row.updated_at is not None
        paid_amount = connection.execute(text(
            "SELECT amount FROM subscription_plans WHERE id = 'pro'"
        )).scalar_one()
        assert paid_amount == 29

    migrate_payment_models.downgrade_payment_migration()
    with test_engine.connect() as connection:
        columns = {column["name"] for column in inspect(connection).get_columns("subscription_plans")}
        assert not {"description", "amount", "currency", "interval_count", "trial_days", "updated_at"} & columns
        subscription_columns = {
            column["name"] for column in inspect(connection).get_columns("user_subscriptions")
        }
        assert not {"auto_renew", "invoice_id"} & subscription_columns
        assert not inspect(connection).has_table("payment_invoices")
        assert connection.execute(text(
            "SELECT COUNT(*) FROM subscription_plans WHERE id = 'free_trial'"
        )).scalar_one() == 1

    test_engine.dispose()
