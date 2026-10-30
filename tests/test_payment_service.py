import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from taikry.database.models import (
    Base,
    PaymentInvoice,
    PaymentTransaction,
    PaymentWebhookEvent,
    SubscriptionPlan,
    User,
    UserSubscription,
)
from app.payments.service import (
    PaymentDomainError,
    VerifiedPayment,
    apply_verified_payment,
    create_invoice,
    cancel_auto_renewal,
    record_webhook_event,
)


@pytest.fixture
def payment_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = session_factory()
    user = User(
        email="payment-test@example.test",
        hashed_password="test-hash",
        salt="test-salt",
        is_active=True,
    )
    plan = SubscriptionPlan(
        id="pro",
        name_en="Pro",
        name_kh="Pro",
        price_usd=29.0,
        amount=Decimal("29.00"),
        currency="USD",
        billing_interval="monthly",
        interval_count=1,
        trial_days=0,
        is_active=True,
    )
    db.add_all([user, plan])
    db.commit()
    yield db, user, plan
    db.close()
    engine.dispose()


def verified(invoice, **overrides):
    values = {
        "merchant_id": "sandbox-merchant",
        "provider_transaction_id": invoice.checkout_reference,
        "invoice_reference": invoice.checkout_reference,
        "payment_status": "APPROVED",
        "payment_status_code": 0,
        "amount": Decimal("29.00"),
        "currency": "USD",
        "provider_reference": "BANK-REF-1",
        "redacted_response": {
            "tran_id": invoice.checkout_reference,
            "payment_status": "APPROVED",
            "payment_status_code": 0,
            "payment_amount": 29.0,
            "payment_currency": "USD",
            "payer_account": "should-not-be-stored",
            "email": "payer@example.test",
        },
    }
    values.update(overrides)
    return VerifiedPayment(**values)


def test_duplicate_checkout_reuses_one_pending_invoice(payment_db):
    db, user, _plan = payment_db
    now = datetime.datetime(2026, 10, 30, tzinfo=datetime.timezone.utc)

    first, created = create_invoice(db, user, "pro", now=now)
    second, created_again = create_invoice(db, user, "pro", now=now)

    assert created is True
    assert created_again is False
    assert first.id == second.id
    assert first.amount == Decimal("29.00")
    assert len(db.query(PaymentInvoice).all()) == 1


def test_verified_payment_activates_subscription_exactly_once(payment_db):
    db, user, _plan = payment_db
    now = datetime.datetime(2026, 10, 30, tzinfo=datetime.timezone.utc)
    invoice, _created = create_invoice(db, user, "pro", now=now)

    result = apply_verified_payment(
        db,
        invoice.id,
        verified(invoice),
        expected_merchant_id="sandbox-merchant",
        now=now + datetime.timedelta(minutes=1),
    )
    db.commit()

    subscription = db.query(UserSubscription).filter_by(user_id=user.id).one()
    assert result["activated"] is True
    assert subscription.status == "active_paid"
    assert subscription.plan_id == "pro"
    assert subscription.auto_renew is False
    assert subscription.invoice_id == invoice.id
    assert subscription.current_period_expires_at.date() == datetime.date(2026, 11, 30)
    assert invoice.status == "PAID"
    assert db.query(PaymentTransaction).count() == 1
    raw = db.query(PaymentTransaction).one().raw_response_redacted
    assert "payer_account" not in raw
    assert "email" not in raw

    second_result = apply_verified_payment(
        db,
        invoice.id,
        verified(invoice),
        expected_merchant_id="sandbox-merchant",
        now=now + datetime.timedelta(minutes=2),
    )
    assert second_result["idempotent"] is True
    assert db.query(PaymentTransaction).count() == 1


def test_pending_provider_status_keeps_invoice_payable(payment_db):
    db, user, _plan = payment_db
    now = datetime.datetime(2026, 10, 30, tzinfo=datetime.timezone.utc)
    invoice, _created = create_invoice(db, user, "pro", now=now)

    pending = verified(
        invoice,
        payment_status="PENDING",
        payment_status_code=2,
        provider_reference=None,
    )
    result = apply_verified_payment(
        db,
        invoice.id,
        pending,
        expected_merchant_id="sandbox-merchant",
        now=now + datetime.timedelta(minutes=1),
    )
    db.commit()

    assert result["status"] == "PENDING"
    assert result["activated"] is False
    assert invoice.status == "PENDING"
    assert db.query(UserSubscription).filter_by(user_id=user.id).first() is None
    assert db.query(PaymentTransaction).one().status == "PENDING"

    second_result = apply_verified_payment(
        db,
        invoice.id,
        verified(invoice),
        expected_merchant_id="sandbox-merchant",
        now=now + datetime.timedelta(minutes=2),
    )
    assert second_result["status"] == "PAID"
    assert second_result["activated"] is True
    assert invoice.status == "PAID"
    assert db.query(PaymentTransaction).count() == 1
    assert db.query(PaymentTransaction).one().status == "APPROVED"


@pytest.mark.parametrize(
    "overrides",
    [
        {"merchant_id": "wrong-merchant"},
        {"amount": Decimal("28.99")},
        {"currency": "KHR"},
        {"invoice_reference": "other-reference"},
    ],
)
def test_mismatched_verified_payment_never_activates(payment_db, overrides):
    db, user, _plan = payment_db
    now = datetime.datetime(2026, 10, 30, tzinfo=datetime.timezone.utc)
    invoice, _created = create_invoice(db, user, "pro", now=now)

    result = apply_verified_payment(
        db,
        invoice.id,
        verified(invoice, **overrides),
        expected_merchant_id="sandbox-merchant",
        now=now + datetime.timedelta(minutes=1),
    )
    db.commit()

    assert result["activated"] is False
    assert result["status"] == "REVIEW"
    assert invoice.status == "REVIEW"
    assert db.query(UserSubscription).filter_by(user_id=user.id).first() is None


def test_success_after_invoice_expiry_is_recorded_for_review_without_entitlement(payment_db):
    db, user, _plan = payment_db
    now = datetime.datetime(2026, 10, 30, tzinfo=datetime.timezone.utc)
    invoice, _created = create_invoice(db, user, "pro", now=now)

    result = apply_verified_payment(
        db,
        invoice.id,
        verified(invoice),
        expected_merchant_id="sandbox-merchant",
        now=now + datetime.timedelta(minutes=31),
    )
    db.commit()

    assert result["reason"] == "invoice_expired"
    assert invoice.status == "REVIEW"
    assert db.query(UserSubscription).filter_by(user_id=user.id).first() is None


def test_duplicate_webhook_body_is_recorded_once(payment_db):
    db, _user, _plan = payment_db
    raw_body = b'{"status":"0","tran_id":"ABC"}'

    event, created = record_webhook_event(
        db,
        raw_body=raw_body,
        event_type="PAYMENT_CALLBACK",
        valid_signature=True,
    )
    repeated, created_again = record_webhook_event(
        db,
        raw_body=raw_body,
        event_type="PAYMENT_CALLBACK",
        valid_signature=True,
    )
    db.commit()

    assert created is True
    assert created_again is False
    assert event.id == repeated.id
    assert db.query(PaymentWebhookEvent).count() == 1


def test_cancel_schedules_end_of_access_without_claiming_provider_cancellation(payment_db):
    db, user, _plan = payment_db
    expiry = datetime.datetime(2026, 12, 1, tzinfo=datetime.timezone.utc)
    subscription = UserSubscription(
        user_id=user.id,
        plan_id="pro",
        status="active_paid",
        current_period_starts_at=datetime.datetime(2026, 10, 1, tzinfo=datetime.timezone.utc),
        current_period_expires_at=expiry,
        auto_renew=False,
    )
    db.add(subscription)
    db.commit()

    result = cancel_auto_renewal(db, user.id)
    db.commit()

    assert result["cancel_at_period_end"] is True
    assert subscription.status == "active_paid"
    assert subscription.auto_renew is False
    assert subscription.current_period_expires_at is not None


def test_cancel_does_not_schedule_free_trial_as_paid_cancellation(payment_db):
    db, user, _plan = payment_db
    db.add(UserSubscription(
        user_id=user.id,
        plan_id="free_trial",
        status="trial_active",
        current_period_starts_at=datetime.datetime(2026, 10, 1),
        current_period_expires_at=datetime.datetime(2026, 11, 1),
    ))
    db.commit()

    with pytest.raises(PaymentDomainError, match="active paid subscription"):
        cancel_auto_renewal(db, user.id)


def test_paid_subscription_expiration_removes_entitlement(payment_db):
    from taikry.saas.trial_service import get_user_trial_status

    db, user, _plan = payment_db
    subscription = UserSubscription(
        user_id=user.id,
        plan_id="pro",
        status="active_paid",
        current_period_starts_at=datetime.datetime(2020, 1, 1),
        current_period_expires_at=datetime.datetime(2020, 2, 1),
        auto_renew=False,
    )
    db.add(subscription)
    db.commit()

    entitlement = get_user_trial_status(db, user.id)

    assert entitlement["status"] == "past_due"
    assert entitlement["is_active"] is False


def test_free_or_inactive_plan_cannot_create_invoice(payment_db):
    db, user, plan = payment_db
    plan.is_active = False
    db.commit()
    with pytest.raises(PaymentDomainError, match="unavailable"):
        create_invoice(db, user, "pro")
