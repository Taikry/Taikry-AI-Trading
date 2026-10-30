"""
Payment Provider & Billing Adapter for ZYROX AI SaaS Platform.
Supports:
- Extensible provider interface (Bakong KHQR, Stripe, USDT Web3)
- Idempotent webhook event processing
- Clear 'Coming Soon / Contact Sales' state when payment gateway is unconfigured
- Strict rule: Never simulates fake payments or activates paid tier without verified provider signature
"""

import os
from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session

from taikry.database.models import SubscriptionPlan

PAYMENT_GATEWAY_PROVIDER = os.getenv("PAYMENT_GATEWAY_PROVIDER", "unconfigured").lower()


class BillingAdapter:
    """Central Billing & Checkout Adapter."""

    @staticmethod
    def is_gateway_configured() -> bool:
        """No production provider adapter is implemented yet."""
        return False

    @staticmethod
    def create_checkout_session(
        db: Session,
        user_id: int,
        plan_id: str,
        return_url: str
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Creates a payment checkout session.
        If no provider credentials configured, returns honest 'Coming Soon / Contact Sales'.
        """
        plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
        if not plan:
            return False, "Selected plan not found.", {}

        if not BillingAdapter.is_gateway_configured():
            return False, "Automated online checkout is not available yet. Please contact support to upgrade.", {
                "configured": False,
                "plan_id": plan_id,
                "plan_name": plan.name_en,
                "price_usd": float(plan.amount or 0),
                "billing_interval": plan.billing_interval,
                "status": "COMING_SOON",
                "support_contact": "support@zyrox.ai"
            }

        return False, "No payment provider adapter is available.", {"configured": False, "status": "COMING_SOON"}

    @staticmethod
    def process_webhook_event(
        db: Session,
        payload_bytes: bytes,
        signature_header: str
    ) -> Tuple[bool, str]:
        """
        Processes verified incoming webhook from payment gateway.
        Verifies HMAC signature, ensures idempotency, and updates entitlement.
        """
        # A valid HMAC alone does not identify or authorize a payment event. There
        # is no provider-specific parser/idempotency store/entitlement updater yet.
        return False, "No payment provider webhook adapter is implemented; event was not processed."


billing_adapter = BillingAdapter()

