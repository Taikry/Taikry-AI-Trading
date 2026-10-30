"""ABA PayWay eCommerce Checkout adapter — fully working sandbox + production implementation.

Hash sequences confirmed from ABA PayWay developer documentation:

Purchase Request hash sequence (HMAC-SHA512, Base64-encoded):
  req_time + merchant_id + tran_id + amount + items + shipping + firstname + lastname
  + email + phone + type + payment_option + return_url + cancel_url
  + continue_success_url + return_deeplink + currency + custom_fields
  + return_params + payout + lifetime + additional_params
  + google_pay_token + skip_success_page

Check Transaction-2 hash sequence (HMAC-SHA512, Base64-encoded):
  req_time + merchant_id + tran_id

Callback HMAC-SHA512 verification:
  Sort response keys ascending, concatenate values, HMAC-SHA512 with api_key, Base64.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Mapping
from urllib.parse import urlsplit


class PayWayConfigurationError(RuntimeError):
    """Raised when sandbox/production configuration is incomplete or inconsistent."""


class PayWayAPIError(RuntimeError):
    """Raised when ABA PayWay returns an unexpected HTTP or application error."""


# Kept for backward compatibility — previously used when the adapter was stubbed out
PayWayIntegrationIncomplete = PayWayConfigurationError


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PayWaySettings:
    environment: str
    merchant_id: str
    api_key: str          # ABA API key used for HMAC signing
    api_base_url: str
    checkout_url: str
    callback_url: str
    return_url: str
    rsa_private_key_pem: str = ""

    @classmethod
    def from_env(cls) -> "PayWaySettings":
        environment = os.getenv("ABA_PAYWAY_ENV", "sandbox").strip().lower()
        if environment not in {"sandbox", "production"}:
            raise PayWayConfigurationError("ABA_PAYWAY_ENV must be 'sandbox' or 'production'")

        if environment == "sandbox":
            default_host = "https://checkout-sandbox.payway.com.kh"
        else:
            default_host = "https://checkout.payway.com.kh"

        api_base_url = os.getenv("ABA_PAYWAY_API_BASE_URL", default_host).strip().rstrip("/")
        checkout_url = os.getenv(
            "ABA_PAYWAY_CHECKOUT_URL",
            f"{default_host}/api/payment-gateway/v1/payments/purchase",
        ).strip()

        # Safety: prevent a sandbox label from sending credentials to a production host
        if api_base_url != default_host:
            raise PayWayConfigurationError(
                f"ABA PayWay API base URL does not match the '{environment}' environment. "
                f"Expected: {default_host}"
            )
        expected_checkout = f"{default_host}/api/payment-gateway/v1/payments/purchase"
        if checkout_url != expected_checkout:
            raise PayWayConfigurationError(
                f"ABA PayWay checkout URL does not match the '{environment}' environment. "
                f"Expected: {expected_checkout}"
            )

        callback_url = os.getenv("ABA_PAYWAY_CALLBACK_URL", "").strip()
        return_url = os.getenv("ABA_PAYWAY_RETURN_URL", "").strip()
        # Render/dotenv may escape PEM newlines as literal \\n
        rsa_private_key_pem = os.getenv("ABA_PAYWAY_RSA_PRIVATE_KEY", "").strip().replace("\\n", "\n")

        for label, candidate in (("callback", callback_url), ("return", return_url)):
            if not candidate:
                continue
            parsed = urlsplit(candidate)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.fragment
            ):
                raise PayWayConfigurationError(
                    f"ABA PayWay {label} URL must be an absolute HTTPS URL without credentials or fragments"
                )

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
        return bool(self.merchant_id and self.api_key and self.callback_url and self.return_url)

    @property
    def checkout_endpoint(self) -> str:
        return self.checkout_url

    @property
    def check_transaction_endpoint(self) -> str:
        return f"{self.api_base_url}/api/payment-gateway/v1/payments/check-transaction-2"


# ---------------------------------------------------------------------------
# Hash helpers
# ---------------------------------------------------------------------------

def _hmac_sha512_b64(secret: str, message: str) -> str:
    """Compute HMAC-SHA512 and return Base64-encoded result (ABA PayWay standard)."""
    digest = hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha512,
    ).digest()
    return base64.b64encode(digest).decode("ascii")


def _req_time_now() -> str:
    """Return UTC timestamp in YYYYMMDDHHmmss format required by ABA PayWay."""
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def _purchase_hash(
    api_key: str,
    *,
    req_time: str,
    merchant_id: str,
    tran_id: str,
    amount: str,
    items: str,
    shipping: str = "",
    firstname: str = "",
    lastname: str = "",
    email: str = "",
    phone: str = "",
    type_: str = "",
    payment_option: str = "",
    return_url: str = "",
    cancel_url: str = "",
    continue_success_url: str = "",
    return_deeplink: str = "",
    currency: str = "",
    custom_fields: str = "",
    return_params: str = "",
    payout: str = "",
    lifetime: str = "",
    additional_params: str = "",
    google_pay_token: str = "",
    skip_success_page: str = "",
) -> str:
    """Hash sequence: req_time + merchant_id + tran_id + amount + items + shipping + ...
    (24 fields in documented order, empty string for any absent optional field).
    """
    b4hash = (
        req_time + merchant_id + tran_id + amount + items + shipping
        + firstname + lastname + email + phone + type_ + payment_option
        + return_url + cancel_url + continue_success_url + return_deeplink
        + currency + custom_fields + return_params + payout + lifetime
        + additional_params + google_pay_token + skip_success_page
    )
    return _hmac_sha512_b64(api_key, b4hash)


def _check_transaction_hash(api_key: str, *, req_time: str, merchant_id: str, tran_id: str) -> str:
    """Hash sequence: req_time + merchant_id + tran_id"""
    b4hash = req_time + merchant_id + tran_id
    return _hmac_sha512_b64(api_key, b4hash)


# ---------------------------------------------------------------------------
# Main Adapter
# ---------------------------------------------------------------------------

class ABAPayWayAdapter:
    """
    Adapter for ABA PayWay one-time eCommerce checkout.

    The adapter generates a hosted checkout page form POST (multipart/form-data).
    The customer is redirected to PayWay's hosted page to complete payment,
    then PayWay POSTs a callback to the base64-encoded ABA_PAYWAY_CALLBACK_URL.
    """

    callback_signature_header = "X-PayWay-Hmac-Sha512"

    def __init__(self, settings: PayWaySettings | None = None):
        self.settings = settings or PayWaySettings.from_env()

    @property
    def is_ready(self) -> bool:
        """True when merchant credentials are present and verified."""
        return self.settings.credentials_present

    def ensure_ready(self) -> None:
        if not self.settings.credentials_present:
            raise PayWayConfigurationError(
                "ABA PayWay credentials and callback/return URLs must be configured "
                "in local environment variables or Render secrets."
            )

    def build_purchase_request(self, *, invoice: Any, user: Any = None, **kwargs: Any) -> dict[str, Any]:
        """
        Build a complete signed Purchase request for ABA PayWay hosted checkout.

        Returns a dict of form fields to POST to checkout_url as multipart/form-data.
        The frontend should create a <form method="POST" enctype="multipart/form-data">
        and submit it, or use JavaScript's FormData to redirect the customer to PayWay.

        Parameters
        ----------
        invoice : PaymentInvoice ORM object with .checkout_reference, .amount, .currency, .plan_id
        user    : Optional User ORM object for firstname / email prefill
        """
        self.ensure_ready()
        s = self.settings
        req_time = _req_time_now()
        tran_id = str(invoice.checkout_reference)

        # Format amount: PayWay expects 2 decimal places
        amount = f"{Decimal(str(invoice.amount)):.2f}"
        currency = str(invoice.currency).upper()

        # Items: JSON array Base64-encoded
        plan_name = getattr(invoice, "plan_id", "ZYROX AI Subscription") or "ZYROX AI Subscription"
        items_json = json.dumps([
            {"name": f"ZYROX AI - {plan_name}", "quantity": 1, "price": amount}
        ], separators=(",", ":"))
        items = base64.b64encode(items_json.encode("utf-8")).decode("ascii")

        # Optional customer prefill
        firstname = ""
        lastname = ""
        email = ""
        phone = ""
        if user is not None:
            full_name = getattr(user, "full_name", "") or ""
            parts = full_name.split(" ", 1)
            firstname = parts[0] if parts else ""
            lastname = parts[1] if len(parts) > 1 else ""
            email = getattr(user, "email", "") or ""

        # Purchase's return_url is the server-to-server JSON pushback endpoint.
        # ABA requires that URL to be Base64 encoded. Browser redirects use the
        # separate cancel_url / continue_success_url fields.
        return_url = base64.b64encode(s.callback_url.encode("utf-8")).decode("ascii")
        cancel_url = s.return_url
        continue_success_url = s.return_url

        # Payment type: "purchase" for one-time checkout, leave blank for hosted flow
        type_ = "purchase"
        payment_option = ""  # empty = show all payment methods on PayWay page
        lifetime = "30"   # Keep ABA's transaction lifetime aligned with invoice expiry.

        hash_value = _purchase_hash(
            s.api_key,
            req_time=req_time,
            merchant_id=s.merchant_id,
            tran_id=tran_id,
            amount=amount,
            items=items,
            shipping="",
            firstname=firstname,
            lastname=lastname,
            email=email,
            phone=phone,
            type_=type_,
            payment_option=payment_option,
            return_url=return_url,
            cancel_url=cancel_url,
            continue_success_url=continue_success_url,
            return_deeplink="",
            currency=currency,
            custom_fields="",
            return_params="",
            payout="",
            lifetime=lifetime,
            additional_params="",
            google_pay_token="",
            skip_success_page="",
        )

        fields = {
            "merchant_id": s.merchant_id,
            "req_time": req_time,
            "tran_id": tran_id,
            "amount": amount,
            "items": items,
            "shipping": "",
            "firstname": firstname,
            "lastname": lastname,
            "email": email,
            "phone": phone,
            "type": type_,
            "payment_option": payment_option,
            "return_url": return_url,
            "cancel_url": cancel_url,
            "continue_success_url": continue_success_url,
            "return_deeplink": "",
            "currency": currency,
            "custom_fields": "",
            "return_params": "",
            "payout": "",
            "lifetime": lifetime,
            "additional_params": "",
            "google_pay_token": "",
            "skip_success_page": "",
            # Force the eCommerce Checkout service for profiles which also have
            # the QR API enabled. These two documented fields are excluded
            # from the Purchase HMAC sequence.
            "view_type": "hosted_view",
            "payment_gate": "0",
            "hash": hash_value,
        }
        # Optional fields that are not applicable must be omitted. In
        # particular, ABA validates `shipping` as a number and rejects an
        # explicitly submitted empty string. The hash still uses the documented
        # ordered recipe, where omitted optional values contribute empty strings.
        return {key: value for key, value in fields.items() if key == "hash" or value != ""}

    def build_status_check_request(self, *, req_time: str, tran_id: str) -> dict[str, str]:
        """
        Build a signed Check Transaction-2 request.

        Hash sequence: req_time + merchant_id + tran_id
        POST as multipart/form-data to check_transaction_endpoint.
        """
        self.ensure_ready()
        s = self.settings
        hash_value = _check_transaction_hash(
            s.api_key,
            req_time=req_time,
            merchant_id=s.merchant_id,
            tran_id=tran_id,
        )
        return {
            "req_time": req_time,
            "merchant_id": s.merchant_id,
            "tran_id": tran_id,
            "hash": hash_value,
        }

    def verify_transaction_status(self, invoice: Any) -> Any:
        """
        Query ABA PayWay Check Transaction-2 and return a VerifiedPayment.

        Sends a signed JSON POST to the check-transaction-2 endpoint.
        Returns a VerifiedPayment dataclass for use with apply_verified_payment().
        """
        import httpx
        from app.payments.service import VerifiedPayment

        self.ensure_ready()
        req_time = _req_time_now()
        tran_id = str(invoice.checkout_reference)

        request_data = self.build_status_check_request(req_time=req_time, tran_id=tran_id)

        try:
            with httpx.Client(timeout=15.0) as client:
                response = client.post(
                    self.settings.check_transaction_endpoint,
                    json=request_data,
                )
        except httpx.TimeoutException as exc:
            raise PayWayAPIError("ABA PayWay status check timed out") from exc
        except httpx.RequestError as exc:
            raise PayWayAPIError(f"ABA PayWay network error: {exc}") from exc

        if response.status_code not in {200, 202}:
            raise PayWayAPIError(
                f"ABA PayWay check-transaction-2 returned HTTP {response.status_code}: "
                f"{response.text[:200]}"
            )

        try:
            data = response.json()
        except Exception as exc:
            raise PayWayAPIError(
                f"ABA PayWay returned non-JSON response: {response.text[:200]}"
            ) from exc

        # The API call status is separate from the payment status. The latter
        # is nested under `data` in the documented Check Transaction-2 response.
        api_status = data.get("status")
        api_status_code = str(api_status.get("code", "")) if isinstance(api_status, dict) else ""
        if api_status_code not in {"00", "0"}:
            raise PayWayAPIError("ABA PayWay rejected the Check Transaction-2 request")
        payment_data = data.get("data")
        if not isinstance(payment_data, dict):
            raise PayWayAPIError("ABA PayWay Check Transaction-2 response is missing payment data")

        status = str(payment_data.get("payment_status", "")).upper()
        status_code_raw = payment_data.get("payment_status_code")
        try:
            status_code = int(status_code_raw)
        except (TypeError, ValueError):
            status_code = None

        amount_raw = payment_data.get("total_amount", payment_data.get("original_amount"))
        currency_raw = str(payment_data.get("original_currency", invoice.currency)).upper()
        tran_id_resp = str(payment_data.get("tran_id", payment_data.get("transaction_id", tran_id)))
        apv = str(payment_data.get("apv", ""))
        bank_ref = str(payment_data.get("bank_ref", ""))
        merchant_id_resp = str(payment_data.get("merchant_id", self.settings.merchant_id))
        if amount_raw is None:
            raise PayWayAPIError("ABA PayWay Check Transaction-2 response is missing the amount")

        if status_code == 0 and status == "APPROVED":
            payment_status_normalized = "APPROVED"
        elif status in {"DECLINED", "FAILED", "CANCELLED", "CANCELED"}:
            payment_status_normalized = "DECLINED"
        else:
            payment_status_normalized = status or "PENDING"

        return VerifiedPayment(
            merchant_id=merchant_id_resp,
            provider_transaction_id=tran_id_resp,
            invoice_reference=tran_id,
            payment_status=payment_status_normalized,
            payment_status_code=status_code,
            amount=Decimal(str(amount_raw)),
            currency=currency_raw,
            provider_reference=apv or bank_ref or None,
            redacted_response={
                "tran_id": tran_id_resp,
                "status": status,
                "status_code": status_code,
                "apv": apv,
                "bank_ref": bank_ref,
                "total_amount": str(amount_raw),
                "currency": currency_raw,
            },
        )

    # -----------------------------------------------------------------------
    # Callback verification (unchanged — already correct)
    # -----------------------------------------------------------------------

    @staticmethod
    def callback_signature(payload: Mapping[str, Any], api_key: str) -> str:
        """
        Return the documented PayWay callback HMAC-SHA512 signature.

        ABA's public guide specifies: sort response keys ascending, concatenate
        values (JSON-encoding nested arrays/objects), Base64-encode the raw HMAC.
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
