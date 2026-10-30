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


def test_adapter_fails_closed_when_provider_request_hash_rules_are_unconfirmed():
    settings = PayWaySettings(
        environment="sandbox",
        merchant_id="sandbox-merchant",
        api_key="sandbox-key",
        api_base_url="https://checkout-sandbox.payway.com.kh",
        checkout_url="https://checkout-sandbox.payway.com.kh/api/payment-gateway/v1/payments/purchase",
        callback_url="https://example.test/api/v1/billing/webhook",
        return_url="https://example.test/dashboard/",
        rsa_private_key_pem="sandbox-test-private-key",
    )
    adapter = ABAPayWayAdapter(settings)

    assert adapter.is_ready is False
    with pytest.raises(PayWayIntegrationIncomplete, match="confirm the Purchase hash sequence"):
        adapter.build_purchase_request()
    with pytest.raises(PayWayIntegrationIncomplete, match="confirm the Purchase hash sequence"):
        adapter.build_status_check_request(req_time="20261030000000", tran_id="T1")


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
