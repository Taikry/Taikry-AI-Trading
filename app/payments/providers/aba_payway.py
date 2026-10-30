"""Fail-closed ABA PayWay eCommerce Checkout adapter.

The official public developer suite documents Purchase fields and callback
signing. An older official sandbox PDF includes a Purchase hash sequence, but
the current rendered Purchase and Check Transaction-2 references omit their
request-hash recipes. The merchant-specific guide must confirm that the older
Purchase sequence still applies and provide the current status-query recipe.
This module deliberately does not guess either signature.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import urlsplit


class PayWayConfigurationError(RuntimeError):
    """Raised when sandbox configuration is incomplete or inconsistent."""


class PayWayIntegrationIncomplete(RuntimeError):
    """Raised when a required provider signing rule is not verified."""


@dataclass(frozen=True)
class PayWaySettings:
    environment: str
    merchant_id: str
    api_key: str
    api_base_url: str
    checkout_url: str
    callback_url: str
    return_url: str
    rsa_private_key_pem: str = ""

    @classmethod
    def from_env(cls) -> "PayWaySettings":
        environment = os.getenv("ABA_PAYWAY_ENV", "sandbox").strip().lower()
        if environment not in {"sandbox", "production"}:
            raise PayWayConfigurationError("ABA_PAYWAY_ENV must be sandbox or production")

        default_host = (
            "https://checkout-sandbox.payway.com.kh"
            if environment == "sandbox"
            else "https://checkout.payway.com.kh"
        )
        expected_host = default_host
        api_base_url = os.getenv("ABA_PAYWAY_API_BASE_URL", default_host).strip().rstrip("/")
        checkout_url = os.getenv(
            "ABA_PAYWAY_CHECKOUT_URL",
            f"{default_host}/api/payment-gateway/v1/payments/purchase",
        ).strip()

        # Do not let an environment label silently send credentials to another
        # host, or let a sandbox deployment target production.
        if api_base_url != expected_host:
            raise PayWayConfigurationError("ABA PayWay API base URL does not match the selected environment")
        expected_checkout = f"{expected_host}/api/payment-gateway/v1/payments/purchase"
        if checkout_url != expected_checkout:
            raise PayWayConfigurationError("ABA PayWay checkout URL does not match the selected environment")

        callback_url = os.getenv("ABA_PAYWAY_CALLBACK_URL", "").strip()
        return_url = os.getenv("ABA_PAYWAY_RETURN_URL", "").strip()
        # Render and dotenv can store PEM newlines as literal ``\\n`` escapes.
        rsa_private_key_pem = os.getenv("ABA_PAYWAY_RSA_PRIVATE_KEY", "").strip().replace("\\n", "\n")
        for label, candidate in (("callback", callback_url), ("return", return_url)):
            if not candidate:
                continue
            parsed = urlsplit(candidate)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
                raise PayWayConfigurationError(f"ABA PayWay {label} URL must be an absolute HTTPS URL")

        return cls(
            environment=environment,
            merchant_id=os.getenv("ABA_PAYWAY_MERCHANT_ID", "").strip(),
            api_key=os.getenv("ABA_PAYWAY_API_KEY", "").strip(),
            api_base_url=api_base_url,
            checkout_url=checkout_url,
            callback_url=callback_url,
            return_url=return_url,
            rsa_private_key_pem=rsa_private_key_pem,
        )

    @property
    def credentials_present(self) -> bool:
        return bool(self.merchant_id and self.api_key and self.rsa_private_key_pem)

    @property
    def checkout_endpoint(self) -> str:
        return self.checkout_url

    @property
    def check_transaction_endpoint(self) -> str:
        return f"{self.api_base_url}/api/payment-gateway/v1/payments/check-transaction-2"


class ABAPayWayAdapter:
    """Adapter for one-time customer-initiated eCommerce payments."""

    callback_signature_header = "X-PayWay-Hmac-Sha512"

    def __init__(self, settings: PayWaySettings | None = None):
        self.settings = settings or PayWaySettings.from_env()

    @property
    def is_ready(self) -> bool:
        """False until ABA confirms the request and status-query hash recipes."""
        return False

    def ensure_ready(self) -> None:
        if not self.settings.credentials_present:
            raise PayWayConfigurationError("ABA PayWay merchant credentials are not configured")
        raise PayWayIntegrationIncomplete(
            "TODO(ABA): confirm the Purchase hash sequence still applies to the current endpoint "
            "and provide the Check Transaction-2 hash recipe before enabling checkout."
        )

    def build_purchase_request(self, **fields: Any) -> dict[str, Any]:
        """Build a signed Purchase request after ABA confirms its exact hash order."""
        self.ensure_ready()
        raise AssertionError("unreachable")

    def build_status_check_request(self, *, req_time: str, tran_id: str) -> dict[str, str]:
        """Build a signed Check Transaction request after ABA confirms its hash recipe."""
        self.ensure_ready()
        raise AssertionError("unreachable")

    def verify_transaction_status(self, invoice: Any):
        """Query ABA's status API after its current request signature is confirmed."""
        self.ensure_ready()
        raise AssertionError("unreachable")

    @staticmethod
    def callback_signature(payload: Mapping[str, Any], api_key: str) -> str:
        """Return the documented PayWay callback HMAC-SHA512 signature.

        ABA's public guide specifies sorting response keys ascending, concatenating
        values (JSON-encoding nested arrays), and Base64-encoding the raw HMAC.
        """
        if not api_key:
            raise PayWayConfigurationError("ABA PayWay API key is not configured")
        canonical = "".join(
            json.dumps(value, separators=(",", ":"), ensure_ascii=True)
            if isinstance(value, (dict, list))
            else "" if value is None
            else str(value)
            for _, value in sorted(payload.items(), key=lambda item: str(item[0]))
        )
        digest = hmac.new(api_key.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha512).digest()
        return base64.b64encode(digest).decode("ascii")

    @classmethod
    def verify_callback_signature(
        cls,
        payload: Mapping[str, Any],
        received_signature: str,
        api_key: str,
    ) -> bool:
        if not received_signature or not api_key:
            return False
        expected = cls.callback_signature(payload, api_key)
        return hmac.compare_digest(expected, received_signature.strip())
