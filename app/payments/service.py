"""Database operations for one-time ABA PayWay subscriptions."""
from __future__ import annotations

import calendar
import datetime
import hashlib
import secrets
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Mapping

from sqlalchemy import func
from sqlalchemy.orm import Session

from taikry.database.models import (
    PaymentInvoice,
    PaymentTransaction,
    PaymentWebhookEvent,
    SubscriptionPlan,
    User,
    UserSubscription,
)

CENT = Decimal("0.01")
REDACTED_RESPONSE_FIELDS = {
    "tran_id", "status", "payment_status", "payment_status_code", "apv", "bank_ref",
    "original_amount", "original_currency", "payment_amount", "payment_currency",
    "total_amount", "discount_amount", "transaction_date", "payment_type",
    "status_code", "status_message",
}


class PaymentDomainError(ValueError):
    """Expected client or payment-state error."""


@dataclass(frozen=True)
class VerifiedPayment:
    """Provider status returned by a trusted server-side check."""
    merchant_id: str
    provider_transaction_id: str
    invoice_reference: str
    payment_status: str
    payment_status_code: int | None
    amount: Decimal
    currency: str
    provider_reference: str | None
    redacted_response: dict[str, Any]


def utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def normalize_utc(value: datetime.datetime | None) -> datetime.datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=datetime.timezone.utc)
    return value.astimezone(datetime.timezone.utc)


def money(value: Any) -> Decimal:
    try:
        result = Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise PaymentDomainError("Invalid monetary amount") from exc
    if not result.is_finite() or result < 0:
        raise PaymentDomainError("Invalid monetary amount")
    return result


def redact_provider_response(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Whitelist non-sensitive reconciliation fields; discard payer/card data."""
    return {key: payload[key] for key in REDACTED_RESPONSE_FIELDS if key in payload}


def _new_reference() -> str:
    # PayWay's published tran_id limit is 20 characters.
    return secrets.token_hex(10).upper()


def create_invoice(
    db: Session,
    user: User,
    plan_slug: str,
    *,
    now: datetime.datetime | None = None,
) -> tuple[PaymentInvoice, bool]:
    """Create or reuse the user's pending invoice for one eligible plan."""
    now = normalize_utc(now or utc_now())
    plan = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.id == plan_slug,
        SubscriptionPlan.is_active.is_(True),
    ).with_for_update().first()
    if not plan:
        raise PaymentDomainError("Selected payment plan is unavailable")
    if plan.billing_interval not in {"monthly", "yearly"}:
        raise PaymentDomainError("Only monthly and annual paid plans can be purchased")
    amount = money(plan.amount)
    if amount <= 0:
        raise PaymentDomainError("Selected plan does not require payment")
    currency = (plan.currency or "USD").upper()
    if currency not in {"USD", "KHR"}:
        raise PaymentDomainError("Plan currency is not supported by ABA PayWay")

    # Serialize check/create for this account on PostgreSQL. The partial unique
    # index on pending (user, plan) invoices is the final race guard.
    db.query(User).filter(User.id == user.id).with_for_update().first()
    stale = db.query(PaymentInvoice).filter(
        PaymentInvoice.user_id == user.id,
        PaymentInvoice.plan_id == plan.id,
        PaymentInvoice.status == "PENDING",
        PaymentInvoice.expires_at <= now,
    ).all()
    for invoice in stale:
        invoice.status = "EXPIRED"

    existing = db.query(PaymentInvoice).filter(
        PaymentInvoice.user_id == user.id,
        PaymentInvoice.plan_id == plan.id,
        PaymentInvoice.status == "PENDING",
        PaymentInvoice.expires_at > now,
    ).with_for_update().first()
    if existing:
        db.flush()
        return existing, False

    recent_attempts = db.query(func.count(PaymentInvoice.id)).filter(
        PaymentInvoice.user_id == user.id,
        PaymentInvoice.created_at >= now - datetime.timedelta(minutes=10),
    ).scalar() or 0
    if recent_attempts >= 5:
        raise PaymentDomainError("Too many checkout attempts. Please try again later.")

    reference = _new_reference()
    invoice = PaymentInvoice(
        user_id=user.id,
        plan_id=plan.id,
        invoice_number=f"ZYR-{now.strftime('%Y%m%d')}-{reference}",
        amount=amount,
        currency=currency,
        provider="aba_payway",
        status="PENDING",
        checkout_reference=reference,
        expires_at=now + datetime.timedelta(minutes=30),
    )
    db.add(invoice)
    db.flush()
    return invoice, True


def _add_interval(start: datetime.datetime, plan: SubscriptionPlan) -> datetime.datetime | None:
    count = max(1, int(plan.interval_count or 1))
    if plan.billing_interval == "monthly":
        month_index = start.month - 1 + count
        year = start.year + month_index // 12
        month = month_index % 12 + 1
        return start.replace(year=year, month=month, day=min(start.day, calendar.monthrange(year, month)[1]))
    if plan.billing_interval == "yearly":
        year = start.year + count
        return start.replace(year=year, day=min(start.day, calendar.monthrange(year, start.month)[1]))
    if plan.billing_interval == "lifetime":
        return None
    raise PaymentDomainError("Plan has no supported paid billing interval")


def _record_transaction(
    db: Session,
    invoice: PaymentInvoice,
    verified: VerifiedPayment,
    verification_status: str,
    status: str,
) -> PaymentTransaction | None:
    if verified.provider_transaction_id:
        existing = db.query(PaymentTransaction).filter(
            PaymentTransaction.provider == "aba_payway",
            PaymentTransaction.provider_transaction_id == verified.provider_transaction_id,
        ).with_for_update().first()
        if existing:
            if existing.invoice_id == invoice.id:
                existing.provider_reference = verified.provider_reference
                existing.amount = money(verified.amount)
                existing.currency = verified.currency.upper()
                existing.status = status
                existing.verification_status = verification_status
                existing.raw_response_redacted = redact_provider_response(verified.redacted_response)
            return existing
    transaction = PaymentTransaction(
        invoice_id=invoice.id,
        provider="aba_payway",
        provider_transaction_id=verified.provider_transaction_id or None,
        provider_reference=verified.provider_reference,
        amount=money(verified.amount),
        currency=verified.currency.upper(),
        status=status,
        verification_status=verification_status,
        raw_response_redacted=redact_provider_response(verified.redacted_response),
    )
    db.add(transaction)
    db.flush()
    return None


def apply_verified_payment(
    db: Session,
    invoice_id: int,
    verified: VerifiedPayment,
    *,
    expected_merchant_id: str,
    now: datetime.datetime | None = None,
) -> dict[str, Any]:
    """Apply only a successful provider status check, atomically and once."""
    now = normalize_utc(now or utc_now())
    invoice = db.query(PaymentInvoice).filter(
        PaymentInvoice.id == invoice_id
    ).with_for_update().first()
    if not invoice:
        raise PaymentDomainError("Invoice not found")
    if invoice.status == "PAID":
        return {"status": "PAID", "activated": True, "idempotent": True}

    approved = verified.payment_status.upper() == "APPROVED" and verified.payment_status_code == 0
    expected_amount = money(invoice.amount)
    received_amount = money(verified.amount)
    expected_reference = invoice.checkout_reference
    mismatches = []
    if verified.merchant_id != expected_merchant_id:
        mismatches.append("merchant")
    if verified.invoice_reference != expected_reference:
        mismatches.append("invoice")
    if verified.provider_transaction_id != expected_reference:
        mismatches.append("transaction_reference")
    if received_amount != expected_amount:
        mismatches.append("amount")
    if verified.currency.upper() != invoice.currency.upper():
        mismatches.append("currency")
    if not verified.provider_transaction_id:
        mismatches.append("transaction")

    if verified.provider_transaction_id:
        previous = db.query(PaymentTransaction).filter(
            PaymentTransaction.provider == "aba_payway",
            PaymentTransaction.provider_transaction_id == verified.provider_transaction_id,
        ).with_for_update().first()
        if previous and previous.invoice_id != invoice.id:
            mismatches.append("duplicate_transaction")

    if not approved:
        _record_transaction(db, invoice, verified, "VERIFIED_NOT_APPROVED", verified.payment_status.upper())
        invoice.status = "FAILED"
        db.flush()
        return {"status": "FAILED", "activated": False, "idempotent": False}

    if mismatches:
        _record_transaction(db, invoice, verified, "MISMATCH", "APPROVED")
        invoice.status = "REVIEW"
        db.flush()
        return {"status": "REVIEW", "activated": False, "reason": ",".join(mismatches)}

    expires = normalize_utc(invoice.expires_at)
    if expires and now >= expires:
        _record_transaction(db, invoice, verified, "VERIFIED_AFTER_EXPIRY", "APPROVED")
        invoice.status = "REVIEW"
        db.flush()
        return {"status": "REVIEW", "activated": False, "reason": "invoice_expired"}

    # A retry of a transaction already recorded for this same invoice is safe;
    # successful subscription activation and invoice state share this DB commit.
    existing_transaction = db.query(PaymentTransaction).filter(
        PaymentTransaction.provider == "aba_payway",
        PaymentTransaction.provider_transaction_id == verified.provider_transaction_id,
    ).with_for_update().first()
    if existing_transaction:
        if existing_transaction.invoice_id != invoice.id:
            invoice.status = "REVIEW"
            return {"status": "REVIEW", "activated": False, "reason": "duplicate_transaction"}
        _record_transaction(db, invoice, verified, "VERIFIED", "APPROVED")
    else:
        _record_transaction(db, invoice, verified, "VERIFIED", "APPROVED")

    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == invoice.plan_id).first()
    if not plan:
        invoice.status = "REVIEW"
        return {"status": "REVIEW", "activated": False, "reason": "plan_missing"}

    subscription = db.query(UserSubscription).filter(
        UserSubscription.user_id == invoice.user_id
    ).with_for_update().first()
    starts_at = now
    if subscription and subscription.status == "active_paid":
        current_expiry = normalize_utc(subscription.current_period_expires_at)
        if current_expiry and current_expiry > now:
            starts_at = current_expiry
    ends_at = _add_interval(starts_at, plan)
    if not subscription:
        subscription = UserSubscription(
            user_id=invoice.user_id,
            plan_id=plan.id,
            status="active_paid",
            current_period_starts_at=starts_at,
            current_period_expires_at=ends_at,
            cancel_at_period_end=False,
            auto_renew=False,
            invoice_id=invoice.id,
        )
        db.add(subscription)
    else:
        subscription.plan_id = plan.id
        subscription.status = "active_paid"
        subscription.current_period_starts_at = starts_at
        subscription.current_period_expires_at = ends_at
        subscription.cancel_at_period_end = False
        subscription.auto_renew = False
        subscription.invoice_id = invoice.id
        subscription.updated_at = now

    invoice.status = "PAID"
    invoice.provider_transaction_id = verified.provider_transaction_id
    invoice.paid_at = now
    invoice.updated_at = now
    db.flush()
    return {"status": "PAID", "activated": True, "idempotent": False}


def cancel_auto_renewal(db: Session, user_id: int) -> dict[str, Any]:
    """Schedule entitlement cancellation; preserve access through the paid period."""
    subscription = db.query(UserSubscription).filter(
        UserSubscription.user_id == user_id
    ).with_for_update().first()
    if not subscription:
        raise PaymentDomainError("No subscription was found")
    if subscription.status != "active_paid":
        raise PaymentDomainError("Only an active paid subscription can be canceled")
    if subscription.cancel_at_period_end:
        return {
            "status": subscription.status,
            "auto_renew": False,
            "cancel_at_period_end": True,
            "access_expires_at": subscription.current_period_expires_at.isoformat()
            if subscription.current_period_expires_at else None,
            "message": "Cancellation is already scheduled for the end of the current access period.",
        }
    if not subscription.current_period_expires_at:
        raise PaymentDomainError("This subscription has no scheduled end date; contact support to change it")
    subscription.auto_renew = False
    subscription.cancel_at_period_end = True
    subscription.updated_at = utc_now()
    db.flush()
    return {
        "status": subscription.status,
        "auto_renew": False,
        "cancel_at_period_end": True,
        "access_expires_at": subscription.current_period_expires_at.isoformat()
        if subscription.current_period_expires_at else None,
        "message": "Cancellation scheduled for period end. No automatic charge will be attempted; access remains through the current period.",
    }


def callback_event_reference(raw_body: bytes) -> str:
    return hashlib.sha256(raw_body).hexdigest()


def record_webhook_event(
    db: Session,
    *,
    raw_body: bytes,
    event_type: str | None,
    valid_signature: bool,
    error_message: str | None = None,
) -> tuple[PaymentWebhookEvent, bool]:
    reference = callback_event_reference(raw_body)
    existing = db.query(PaymentWebhookEvent).filter(
        PaymentWebhookEvent.provider == "aba_payway",
        PaymentWebhookEvent.event_reference == reference,
    ).with_for_update().first()
    if existing:
        return existing, False
    event = PaymentWebhookEvent(
        provider="aba_payway",
        event_reference=reference,
        event_type=event_type,
        processing_status="RECEIVED" if valid_signature else "INVALID_SIGNATURE",
        processed_at=utc_now() if not valid_signature else None,
        error_message=error_message if not valid_signature else None,
    )
    db.add(event)
    db.flush()
    return event, True
