"""Authenticated payment, invoice, subscription, and admin API routes."""
from __future__ import annotations

import datetime
import json
import logging
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.payments.providers.aba_payway import (
    ABAPayWayAdapter,
    PayWayConfigurationError,
    PayWayIntegrationIncomplete,
)
from app.payments.service import (
    PaymentDomainError,
    VerifiedPayment,
    apply_verified_payment,
    cancel_auto_renewal,
    create_invoice,
    callback_event_reference,
    record_webhook_event,
    utc_now,
)
from taikry.api.saas_routes import get_current_admin, get_current_user
from taikry.database.models import (
    PaymentInvoice,
    PaymentTransaction,
    PaymentWebhookEvent,
    SubscriptionPlan,
    User,
    UserSubscription,
)
from taikry.database.session import get_db
from taikry.saas.trial_service import get_user_trial_status

logger = logging.getLogger("zyrox.payments.routes")
payments_router = APIRouter()
MAX_CALLBACK_BODY_BYTES = 16_384


class CheckoutRequest(BaseModel):
    plan_id: str = Field(min_length=1, max_length=30)


def _adapter() -> ABAPayWayAdapter:
    try:
        return ABAPayWayAdapter()
    except PayWayConfigurationError as exc:
        raise HTTPException(status_code=503, detail="ABA PayWay is not configured for this environment") from exc


def _invoice_payload(invoice: PaymentInvoice) -> dict[str, Any]:
    return {
        "id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "plan_id": invoice.plan_id,
        "amount": f"{Decimal(invoice.amount):.2f}",
        "currency": invoice.currency,
        "provider": invoice.provider,
        "provider_transaction_id": invoice.provider_transaction_id,
        "status": invoice.status,
        "checkout_reference": invoice.checkout_reference,
        "expires_at": invoice.expires_at.isoformat() if invoice.expires_at else None,
        "paid_at": invoice.paid_at.isoformat() if invoice.paid_at else None,
        "created_at": invoice.created_at.isoformat() if invoice.created_at else None,
    }


def _payment_result_payload(result: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in result.items() if key != "reason"} | {
        "reason": result.get("reason")
    }


def _apply_provider_verification(
    db: Session,
    invoice: PaymentInvoice,
    adapter: ABAPayWayAdapter,
) -> dict[str, Any]:
    verified: VerifiedPayment = adapter.verify_transaction_status(invoice)
    result = apply_verified_payment(
        db,
        invoice.id,
        verified,
        expected_merchant_id=adapter.settings.merchant_id,
    )
    return result


@payments_router.get("/api/v1/payments/status")
def payment_integration_status():
    """Return public readiness only; do not expose merchant configuration."""
    try:
        adapter = ABAPayWayAdapter()
        return {
            "provider": "aba_payway",
            "environment": adapter.settings.environment,
            "checkout_available": adapter.is_ready,
        }
    except PayWayConfigurationError:
        return {"provider": "aba_payway", "environment": "sandbox", "checkout_available": False}


@payments_router.get("/api/v1/payments/plans")
def list_payment_plans(db: Session = Depends(get_db)):
    plans = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.is_active.is_(True),
        SubscriptionPlan.amount > 0,
        SubscriptionPlan.billing_interval.in_(("monthly", "yearly")),
    ).order_by(SubscriptionPlan.amount.asc()).all()
    return {
        "plans": [
            {
                "id": plan.id,
                "slug": plan.slug,
                "name": plan.name,
                "name_en": plan.name_en,
                "name_kh": plan.name_kh,
                "description": plan.description or plan.name_en,
                "amount": f"{Decimal(plan.amount):.2f}",
                "currency": plan.currency,
                "billing_interval": plan.billing_interval,
                "interval_count": plan.interval_count,
                "trial_days": plan.trial_days,
                "features": {
                    "max_ai_scans_per_day": plan.max_ai_scans_per_day,
                    "max_deep_analysis_per_day": plan.max_deep_analysis_per_day,
                    "max_watchlists": plan.max_watchlists,
                    "backtesting_enabled": plan.backtesting_enabled,
                    "telegram_alerts_enabled": plan.telegram_alerts_enabled,
                    "agent_debate_enabled": plan.agent_debate_enabled,
                },
            }
            for plan in plans
        ]
    }


@payments_router.post("/api/v1/payments/checkout")
def create_checkout(
    payload: CheckoutRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    adapter = _adapter()
    try:
        # This check happens before invoice creation, so missing merchant signing
        # rules never leave customers with unusable pending invoices.
        adapter.ensure_ready()
        invoice, created = create_invoice(db, user, payload.plan_id)
        fields = adapter.build_purchase_request(invoice=invoice, user=user)
        db.commit()
        return {
            "success": True,
            "created": created,
            "invoice": _invoice_payload(invoice),
            "checkout": {
                "url": adapter.settings.checkout_url,
                "method": "POST",
                "encoding": "multipart/form-data",
                "fields": fields,
            },
        }
    except PaymentDomainError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (PayWayConfigurationError, PayWayIntegrationIncomplete) as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        logger.exception("ABA PayWay checkout could not be prepared")
        raise HTTPException(status_code=502, detail="Checkout could not be prepared")


@payments_router.get("/api/v1/payments/invoices")
def list_my_invoices(
    limit: int = Query(default=50, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    invoices = db.query(PaymentInvoice).filter(
        PaymentInvoice.user_id == user.id
    ).order_by(PaymentInvoice.created_at.desc()).limit(limit).all()
    return {"invoices": [_invoice_payload(invoice) for invoice in invoices]}


@payments_router.get("/api/v1/payments/invoices/{invoice_id}")
def get_my_invoice(
    invoice_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    invoice = db.query(PaymentInvoice).filter(
        PaymentInvoice.id == invoice_id,
        PaymentInvoice.user_id == user.id,
    ).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return _invoice_payload(invoice)


@payments_router.post("/api/v1/payments/callback")
async def payment_callback(request: Request, db: Session = Depends(get_db)):
    if "application/json" not in request.headers.get("content-type", "").lower():
        raise HTTPException(status_code=415, detail="PayWay callback must use application/json")
    raw_body = await request.body()
    if len(raw_body) > MAX_CALLBACK_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Callback body is too large")
    try:
        payload = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid callback JSON") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Callback must be a JSON object")
    return _process_payment_callback(
        db,
        payload,
        raw_body,
        request.headers.get("X-PayWay-Hmac-Sha512", ""),
    )


def _process_payment_callback(
    db: Session,
    payload: dict[str, Any],
    raw_body: bytes,
    signature: str,
):
    adapter = _adapter()
    valid_signature = adapter.verify_callback_signature(
        payload,
        signature,
        adapter.settings.api_key,
    )
    try:
        event, created = record_webhook_event(
            db,
            raw_body=raw_body,
            event_type="PAYMENT_CALLBACK",
            valid_signature=valid_signature,
            error_message=None if valid_signature else "Callback signature validation failed",
        )
        if not valid_signature:
            db.commit()
            raise HTTPException(status_code=401, detail="Invalid PayWay callback signature")
        terminal_event_states = {"PAID", "FAILED", "REVIEW", "UNMATCHED_REFERENCE"}
        if not created and event.processing_status in terminal_event_states:
            db.commit()
            return {"received": True, "duplicate": True, "status": event.processing_status}
        if not created and event.processing_status == "INVALID_SIGNATURE":
            event.processing_status = "RECEIVED"
            event.error_message = None
            event.processed_at = None

        invoice = db.query(PaymentInvoice).filter(
            PaymentInvoice.checkout_reference == str(payload.get("tran_id", ""))
        ).with_for_update().first()
        if not invoice:
            event.processing_status = "UNMATCHED_REFERENCE"
            event.error_message = "No invoice matched the callback reference"
            event.processed_at = utc_now()
            db.commit()
            return JSONResponse(
                {"received": True, "status": "unmatched_reference"},
                status_code=status.HTTP_202_ACCEPTED,
            )

        adapter.ensure_ready()
        result = _apply_provider_verification(db, invoice, adapter)
        event.processing_status = str(result.get("status", "VERIFICATION_PENDING"))
        if result.get("status") in {"PAID", "FAILED", "REVIEW"}:
            event.processed_at = utc_now()
        db.commit()
        return {"received": True, "duplicate": False, **_payment_result_payload(result)}
    except HTTPException:
        raise
    except (PayWayConfigurationError, PayWayIntegrationIncomplete):
        event.processing_status = "PENDING_SERVER_VERIFICATION"
        event.error_message = "Server-side status verification is not configured"
        db.commit()
        return JSONResponse(
            {"received": True, "status": "pending_server_verification"},
            status_code=status.HTTP_202_ACCEPTED,
        )
    except Exception:
        db.rollback()
        # Persist the successful signature check even when the downstream status
        # query is temporarily unavailable. In particular, do not leave a valid
        # retry marked as INVALID_SIGNATURE after rolling back its state change.
        if valid_signature:
            pending_event = db.query(PaymentWebhookEvent).filter(
                PaymentWebhookEvent.provider == "aba_payway",
                PaymentWebhookEvent.event_reference == callback_event_reference(raw_body),
            ).first()
            if pending_event:
                pending_event.processing_status = "PENDING_SERVER_VERIFICATION"
                pending_event.error_message = "Provider status verification is temporarily unavailable"
                pending_event.processed_at = None
                db.commit()
        logger.exception("PayWay callback was stored but could not be verified")
        return JSONResponse(
            {"received": True, "status": "pending_server_verification"},
            status_code=status.HTTP_202_ACCEPTED,
        )


@payments_router.post("/api/v1/payments/verify/{invoice_id}")
def verify_my_invoice(
    invoice_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    invoice = db.query(PaymentInvoice).filter(
        PaymentInvoice.id == invoice_id,
        PaymentInvoice.user_id == user.id,
    ).with_for_update().first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if invoice.status == "PAID":
        return {"invoice": _invoice_payload(invoice), "activated": True, "idempotent": True}
    adapter = _adapter()
    try:
        adapter.ensure_ready()
        result = _apply_provider_verification(db, invoice, adapter)
        db.commit()
        return {"invoice": _invoice_payload(invoice), **_payment_result_payload(result)}
    except (PayWayConfigurationError, PayWayIntegrationIncomplete) as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except PaymentDomainError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        logger.exception("PayWay invoice verification failed")
        raise HTTPException(status_code=502, detail="Payment status could not be verified") from exc


@payments_router.get("/api/v1/subscriptions/me")
def get_my_subscription(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entitlement = get_user_trial_status(db, user.id)
    subscription = db.query(UserSubscription).filter(
        UserSubscription.user_id == user.id
    ).first()
    invoices = db.query(PaymentInvoice).filter(
        PaymentInvoice.user_id == user.id
    ).order_by(PaymentInvoice.created_at.desc()).limit(20).all()
    plan = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.id == (subscription.plan_id if subscription else "free_trial")
    ).first()
    return {
        "subscription": {
            "status": entitlement.get("status", "unsubscribed"),
            "is_active": entitlement.get("is_active", False),
            "plan_id": subscription.plan_id if subscription else None,
            "plan_name_en": plan.name_en if plan else None,
            "plan_name_kh": plan.name_kh if plan else None,
            "starts_at": entitlement.get("current_period_starts_at_utc") or entitlement.get("trial_starts_at_utc"),
            "expires_at": entitlement.get("current_period_expires_at_utc") or entitlement.get("trial_expires_at_utc"),
            "days_remaining": entitlement.get("days_remaining", 0),
            "auto_renew": subscription.auto_renew if subscription else False,
            "cancel_at_period_end": subscription.cancel_at_period_end if subscription else False,
        },
        "invoices": [_invoice_payload(invoice) for invoice in invoices],
    }


@payments_router.post("/api/v1/subscriptions/cancel")
def cancel_my_subscription(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        result = cancel_auto_renewal(db, user.id)
        db.commit()
        return result
    except PaymentDomainError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@payments_router.get("/api/v1/admin/payments/summary")
def admin_payment_summary(
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    now = utc_now()
    soon = now + datetime.timedelta(days=7)
    verified_revenue = db.query(func.coalesce(func.sum(PaymentTransaction.amount), 0)).filter(
        PaymentTransaction.provider == "aba_payway",
        PaymentTransaction.status == "APPROVED",
        PaymentTransaction.verification_status == "VERIFIED",
    ).scalar()
    active_subscriptions = db.query(func.count(UserSubscription.id)).filter(
        UserSubscription.status == "active_paid",
        (UserSubscription.current_period_expires_at.is_(None))
        | (UserSubscription.current_period_expires_at > now.replace(tzinfo=None)),
    ).scalar() or 0
    expiring = db.query(func.count(UserSubscription.id)).filter(
        UserSubscription.status == "active_paid",
        UserSubscription.current_period_expires_at > now.replace(tzinfo=None),
        UserSubscription.current_period_expires_at <= soon.replace(tzinfo=None),
    ).scalar() or 0
    return {
        "verified_revenue": f"{Decimal(verified_revenue or 0):.2f}",
        "currency": "USD",
        "pending_invoices": db.query(func.count(PaymentInvoice.id)).filter(PaymentInvoice.status == "PENDING").scalar() or 0,
        "successful_payments": db.query(func.count(PaymentInvoice.id)).filter(PaymentInvoice.status == "PAID").scalar() or 0,
        "failed_payments": db.query(func.count(PaymentInvoice.id)).filter(PaymentInvoice.status == "FAILED").scalar() or 0,
        "active_subscriptions": active_subscriptions,
        "expiring_within_7_days": expiring,
        "refund_status_supported": False,
        "refunds": [],
    }


@payments_router.get("/api/v1/admin/payments/transactions")
def admin_payment_transactions(
    limit: int = Query(default=100, ge=1, le=500),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    rows = db.query(PaymentTransaction).order_by(
        PaymentTransaction.created_at.desc()
    ).limit(limit).all()
    return {
        "transactions": [
            {
                "id": row.id,
                "invoice_id": row.invoice_id,
                "provider": row.provider,
                "provider_transaction_id": row.provider_transaction_id,
                "provider_reference": row.provider_reference,
                "amount": f"{Decimal(row.amount):.2f}",
                "currency": row.currency,
                "status": row.status,
                "verification_status": row.verification_status,
                "response": row.raw_response_redacted,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]
    }
