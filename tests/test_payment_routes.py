import json

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.payments import routes
from app.payments.providers.aba_payway import (
    ABAPayWayAdapter,
    PayWayAPIError,
    PayWaySettings,
)
from app.payments.routes import CheckoutRequest
from app.payments.service import create_invoice
from taikry.database.models import (
    Base,
    PaymentInvoice,
    PaymentWebhookEvent,
    SubscriptionPlan,
    User,
)


@pytest.fixture
def payment_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    user = User(
        email="route-test@example.test",
        hashed_password="test-hash",
        salt="test-salt",
        is_active=True,
    )
    plan = SubscriptionPlan(
        id="pro",
        name_en="Pro",
        name_kh="Pro",
        price_usd=29.0,
        amount=29,
        currency="USD",
        billing_interval="monthly",
        interval_count=1,
        trial_days=0,
        signal_alerts_target_min_per_day=5,
        max_signal_alerts_per_day=10,
        is_active=True,
    )
    db.add_all([user, plan])
    db.commit()
    yield db, user, plan
    db.close()
    engine.dispose()


def _adapter():
    settings = PayWaySettings(
        environment="sandbox",
        merchant_id="sandbox-merchant",
        api_key="sandbox-key",
        api_base_url="https://checkout-sandbox.payway.com.kh",
        checkout_url="https://checkout-sandbox.payway.com.kh/api/payment-gateway/v1/payments/purchase",
        callback_url="https://example.test/api/v1/payments/callback",
        return_url="https://example.test/dashboard/billing.html",
        rsa_private_key_pem="sandbox-test-private-key",
    )
    return ABAPayWayAdapter(settings)


def test_owner_cannot_read_another_users_invoice(payment_db):
    db, user, _plan = payment_db
    invoice, _created = create_invoice(db, user, "pro")
    db.commit()
    other_user = type(user)(
        email="another@example.test",
        hashed_password="test-hash",
        salt="test-salt",
        is_active=True,
    )
    db.add(other_user)
    db.commit()

    with pytest.raises(HTTPException) as exc:
        routes.get_my_invoice(invoice.id, user=other_user, db=db)
    assert exc.value.status_code == 404


def test_checkout_returns_signed_sandbox_form(payment_db, monkeypatch):
    db, user, _plan = payment_db
    monkeypatch.setattr(routes, "_adapter", _adapter)

    response = routes.create_checkout(CheckoutRequest(plan_id="pro"), user=user, db=db)

    assert response["success"] is True
    assert response["checkout"]["encoding"] == "multipart/form-data"
    assert response["checkout"]["fields"]["hash"]
    assert db.query(PaymentInvoice).count() == 1


def test_subscription_plan_catalog_exposes_active_paid_plans(payment_db):
    db, _user, _plan = payment_db

    result = routes.list_payment_plans(db=db)

    assert len(result["plans"]) == 1
    pro = result["plans"][0]
    assert pro["id"] == "pro"
    assert pro["amount"] == "29.00"
    assert pro["billing_interval"] == "monthly"
    assert "max_ai_scans_per_day" in pro["features"]
    assert pro["features"]["signal_alerts_target_min_per_day"] == 5
    assert pro["features"]["max_signal_alerts_per_day"] == 10


def test_checkout_requires_a_valid_session_before_creating_an_invoice():
    from taikry.api.app import app

    response = TestClient(app).post(
        "/api/v1/payments/checkout",
        json={"plan_id": "pro"},
    )

    assert response.status_code == 401


def test_unsigned_callback_is_audited_and_valid_retry_is_not_poisoned(payment_db, monkeypatch):
    db, user, _plan = payment_db
    adapter = _adapter()
    monkeypatch.setattr(routes, "_adapter", lambda: adapter)
    invoice, _created = create_invoice(db, user, "pro")
    db.commit()
    payload = {"status": "0", "tran_id": invoice.checkout_reference}
    raw_body = json.dumps(payload, separators=(",", ":")).encode()

    with pytest.raises(HTTPException) as exc:
        routes._process_payment_callback(db, payload, raw_body, "")
    assert exc.value.status_code == 401
    assert db.query(PaymentWebhookEvent).one().processing_status == "INVALID_SIGNATURE"

    signature = adapter.callback_signature(payload, adapter.settings.api_key)
    def unavailable(_invoice):
        raise PayWayAPIError("temporary test outage")

    monkeypatch.setattr(adapter, "verify_transaction_status", unavailable)
    response = routes._process_payment_callback(db, payload, raw_body, signature)
    assert response.status_code == 202
    assert db.query(PaymentWebhookEvent).one().processing_status == "PENDING_SERVER_VERIFICATION"
    assert invoice.status == "PENDING"
