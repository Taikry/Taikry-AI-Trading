import base64
import hashlib
import hmac
import json
from decimal import Decimal
from types import SimpleNamespace

import httpx
import pytest

from app.payments.providers.aba_payway import (
    ABAPayWayAdapter,
    PayWayConfigurationError,
    PayWayIntegrationIncomplete,
    PayWaySettings,
)


def test_callback_signature_matches_documented_hmac_sha512_vector():
    payload = {"tran_id": "T1", "status": "0", "extra": {"a": 1}}
    signature = "SbqbS7zsix3MSlqqBAdJh4f6wivOLu/XUZNw0NvrY/kqMg7X/Iijk+WZibpQOcU0jSaLDdFoi0ykfoBT9A+HoA=="

    assert ABAPayWayAdapter.callback_signature(payload, "test-key") == signature
    assert ABAPayWayAdapter.verify_callback_signature(payload, signature, "test-key")
    assert not ABAPayWayAdapter.verify_callback_signature(payload, "invalid", "test-key")


def test_purchase_request_matches_documented_hmac_sequence(monkeypatch):
    settings = PayWaySettings(
        environment="sandbox",
        merchant_id="sandbox-merchant",
        api_key="sandbox-key",
        api_base_url="https://checkout-sandbox.payway.com.kh",
        checkout_url="https://checkout-sandbox.payway.com.kh/api/payment-gateway/v1/payments/purchase",
        callback_url="https://example.test/api/v1/payments/callback",
        return_url="https://example.test/dashboard/",
    )
    adapter = ABAPayWayAdapter(settings)
    monkeypatch.setattr("app.payments.providers.aba_payway._req_time_now", lambda: "20261030000000")
    invoice = SimpleNamespace(
        checkout_reference="TESTREF001",
        amount=Decimal("29.00"),
        currency="USD",
        plan_id="pro",
    )
    user = SimpleNamespace(full_name="Jane Doe", email="jane@example.test")

    assert adapter.is_ready is True
    fields = adapter.build_purchase_request(invoice=invoice, user=user)
    assert fields["return_url"] == base64.b64encode(settings.callback_url.encode()).decode()
    assert fields["continue_success_url"] == settings.return_url
    assert json.loads(base64.b64decode(fields["items"]))[0]["price"] == "29.00"

    ordered_fields = (
        "req_time", "merchant_id", "tran_id", "amount", "items", "shipping",
        "firstname", "lastname", "email", "phone", "type", "payment_option",
        "return_url", "cancel_url", "continue_success_url", "return_deeplink",
        "currency", "custom_fields", "return_params", "payout", "lifetime",
        "additional_params", "google_pay_token", "skip_success_page",
    )
    message = "".join(fields.get(key, "") for key in ordered_fields)
    expected = base64.b64encode(
        hmac.new(settings.api_key.encode(), message.encode(), hashlib.sha512).digest()
    ).decode()
    assert fields["hash"] == expected
    assert fields["view_type"] == "hosted_view"
    assert fields["payment_gate"] == "0"
    assert "shipping" not in fields
    assert "phone" not in fields


def test_check_transaction_2_request_hash_uses_json_body_fields():
    settings = PayWaySettings(
        environment="sandbox",
        merchant_id="sandbox-merchant",
        api_key="sandbox-key",
        api_base_url="https://checkout-sandbox.payway.com.kh",
        checkout_url="https://checkout-sandbox.payway.com.kh/api/payment-gateway/v1/payments/purchase",
        callback_url="https://example.test/api/v1/payments/callback",
        return_url="https://example.test/dashboard/",
    )
    adapter = ABAPayWayAdapter(settings)
    fields = adapter.build_status_check_request(req_time="20261030000000", tran_id="T1")
    expected = base64.b64encode(
        hmac.new(
            settings.api_key.encode(),
            b"20261030000000sandbox-merchantT1",
            hashlib.sha512,
        ).digest()
    ).decode()
    assert fields == {
        "req_time": "20261030000000",
        "merchant_id": "sandbox-merchant",
        "tran_id": "T1",
        "hash": expected,
    }


def test_status_check_sends_json_and_reads_nested_payment_status(monkeypatch):
    settings = PayWaySettings(
        environment="sandbox",
        merchant_id="sandbox-merchant",
        api_key="sandbox-key",
        api_base_url="https://checkout-sandbox.payway.com.kh",
        checkout_url="https://checkout-sandbox.payway.com.kh/api/payment-gateway/v1/payments/purchase",
        callback_url="https://example.test/api/v1/payments/callback",
        return_url="https://example.test/dashboard/",
    )
    adapter = ABAPayWayAdapter(settings)
    monkeypatch.setattr("app.payments.providers.aba_payway._req_time_now", lambda: "20261030000000")
    invoice = SimpleNamespace(checkout_reference="TESTREF001", amount=Decimal("29.00"), currency="USD")

    class MockResponse:
        status_code = 200
        text = ""

        @staticmethod
        def json():
            return {
                "status": {"code": "00", "message": "Success!"},
                "data": {
                    "tran_id": "TESTREF001",
                    "payment_status_code": 0,
                    "payment_status": "APPROVED",
                    "total_amount": 29.0,
                    "original_currency": "USD",
                    "apv": "123456",
                },
            }

    class MockClient:
        def __init__(self, timeout):
            assert timeout == 15.0

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, *, json, **kwargs):
            assert url == adapter.settings.check_transaction_endpoint
            assert json["tran_id"] == "TESTREF001"
            return MockResponse()

    monkeypatch.setattr(httpx, "Client", MockClient)
    verified = adapter.verify_transaction_status(invoice)
    assert verified.payment_status == "APPROVED"
    assert verified.payment_status_code == 0
    assert verified.amount == Decimal("29.0")
    assert verified.currency == "USD"


def test_adapter_rejects_production_url_when_sandbox_is_selected(monkeypatch):
    monkeypatch.setenv("ABA_PAYWAY_ENV", "sandbox")
    monkeypatch.setenv("ABA_PAYWAY_API_BASE_URL", "https://checkout.payway.com.kh")
    monkeypatch.delenv("ABA_PAYWAY_CHECKOUT_URL", raising=False)

    with pytest.raises(PayWayConfigurationError, match="API base URL does not match"):
        PayWaySettings.from_env()


def test_adapter_rejects_non_https_callback_url(monkeypatch):
    monkeypatch.setenv("ABA_PAYWAY_ENV", "sandbox")
    monkeypatch.setenv("ABA_PAYWAY_API_BASE_URL", "https://checkout-sandbox.payway.com.kh")
    monkeypatch.setenv(
        "ABA_PAYWAY_CHECKOUT_URL",
        "https://checkout-sandbox.payway.com.kh/api/payment-gateway/v1/payments/purchase",
    )
    monkeypatch.setenv("ABA_PAYWAY_CALLBACK_URL", "https://example.test/callback")
    monkeypatch.setenv("ABA_PAYWAY_RETURN_URL", "https://example.test/billing/")
    monkeypatch.setenv("ABA_PAYWAY_CALLBACK_URL", "http://example.test/callback")

    with pytest.raises(PayWayConfigurationError, match="absolute HTTPS URL"):
        PayWaySettings.from_env()


def test_settings_expand_escaped_pem_newlines_without_logging_secret(monkeypatch):
    monkeypatch.setenv("ABA_PAYWAY_ENV", "sandbox")
    monkeypatch.setenv("ABA_PAYWAY_MERCHANT_ID", "sandbox-merchant")
    monkeypatch.setenv("ABA_PAYWAY_API_KEY", "sandbox-api-key")
    monkeypatch.setenv(
        "ABA_PAYWAY_RSA_PRIVATE_KEY",
        "-----BEGIN RSA PRIVATE KEY-----\\nTEST-ONLY\\n-----END RSA PRIVATE KEY-----",
    )
    monkeypatch.setenv("ABA_PAYWAY_API_BASE_URL", "https://checkout-sandbox.payway.com.kh")
    monkeypatch.setenv(
        "ABA_PAYWAY_CHECKOUT_URL",
        "https://checkout-sandbox.payway.com.kh/api/payment-gateway/v1/payments/purchase",
    )

    settings = PayWaySettings.from_env()

    assert settings.credentials_present
    assert "\nTEST-ONLY\n" in settings.rsa_private_key_pem
