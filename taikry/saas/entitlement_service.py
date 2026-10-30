"""
Centralized Plan and Entitlement Engine for ZYROX AI SaaS Platform.
Controls:
- Plan catalog (Free Trial, Pro, Premium)
- Daily usage quotas (standard scans, deep analysis, watchlists, backtests)
- Server-side entitlement validation before expensive inference
- Token & Cost accounting per user
"""

import datetime
from decimal import Decimal
from typing import Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from taikry.database.session import SessionLocal
from taikry.database.models import User, UserSubscription, SubscriptionPlan, AIUsageRecord
from taikry.saas.trial_service import get_user_trial_status

# Default Standard Plans Specification
DEFAULT_PLANS = [
    {
        "id": "free_trial",
        "name_en": "14-Day Free Trial",
        "name_kh": "សាកល្បងឥតគិតថ្លៃ ១៤ ថ្ងៃ",
        "price_usd": 0.0,
        "billing_interval": "trial",
        "max_ai_scans_per_day": 10,
        "max_deep_analysis_per_day": 3,
        "max_watchlists": 5,
        "backtesting_enabled": False,
        "telegram_alerts_enabled": True,
        "agent_debate_enabled": False,
        "is_active": True
    },
    {
        "id": "pro",
        "name_en": "Pro Trader Tier",
        "name_kh": "កញ្ចប់ Pro Trader",
        "price_usd": 29.0,
        "billing_interval": "monthly",
        "max_ai_scans_per_day": 50,
        "max_deep_analysis_per_day": 20,
        "max_watchlists": 25,
        "backtesting_enabled": True,
        "telegram_alerts_enabled": True,
        "agent_debate_enabled": True,
        "is_active": True
    },
    {
        "id": "premium",
        "name_en": "Institutional Premium",
        "name_kh": "កញ្ចប់ Institutional Premium",
        "price_usd": 79.0,
        "billing_interval": "monthly",
        "max_ai_scans_per_day": 200,
        "max_deep_analysis_per_day": 100,
        "max_watchlists": 100,
        "backtesting_enabled": True,
        "telegram_alerts_enabled": True,
        "agent_debate_enabled": True,
        "is_active": True
    }
]


def init_default_plans(db: Session):
    """Initializes default subscription plans in database if not already present."""
    for p_data in DEFAULT_PLANS:
        existing = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == p_data["id"]).first()
        if not existing:
            plan_values = dict(p_data)
            plan_values["amount"] = Decimal(str(p_data.get("price_usd", 0))).quantize(Decimal("0.01"))
            plan = SubscriptionPlan(**plan_values)
            db.add(plan)
    db.commit()


def get_all_plans(db: Session) -> list:
    """Returns active subscription plans catalog."""
    init_default_plans(db)
    plans = db.query(SubscriptionPlan).filter(SubscriptionPlan.is_active == True).all()
    return [
        {
            "id": p.id,
            "name_en": p.name_en,
            "name_kh": p.name_kh,
            "price_usd": float(p.amount or 0),
            "billing_interval": p.billing_interval,
            "max_ai_scans_per_day": p.max_ai_scans_per_day,
            "max_deep_analysis_per_day": p.max_deep_analysis_per_day,
            "max_watchlists": p.max_watchlists,
            "backtesting_enabled": p.backtesting_enabled,
            "telegram_alerts_enabled": p.telegram_alerts_enabled,
            "agent_debate_enabled": p.agent_debate_enabled
        }
        for p in plans
    ]


def get_user_entitlement(db: Session, user_id: int) -> Dict[str, Any]:
    """
    Returns the user's active entitlement, plan quotas, and today's consumption.
    """
    init_default_plans(db)
    trial_status = get_user_trial_status(db, user_id)
    plan_id = trial_status.get("plan_id", "free_trial")

    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if not plan:
        plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == "free_trial").first()

    today_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

    # Count today's standard scans
    standard_scans_today = db.query(func.count(AIUsageRecord.id)).filter(
        AIUsageRecord.user_id == user_id,
        AIUsageRecord.date_str == today_str,
        AIUsageRecord.request_type == "standard_scan"
    ).scalar() or 0

    # Count today's deep analyses
    deep_scans_today = db.query(func.count(AIUsageRecord.id)).filter(
        AIUsageRecord.user_id == user_id,
        AIUsageRecord.date_str == today_str,
        AIUsageRecord.request_type == "deep_analysis"
    ).scalar() or 0

    return {
        "user_id": user_id,
        "subscription_status": trial_status.get("status"),
        "is_active": trial_status.get("is_active", False),
        "days_remaining": trial_status.get("days_remaining", 0),
        "hours_remaining": trial_status.get("hours_remaining", 0),
        "trial_progress_percent": trial_status.get("progress_percent", 100.0),
        "plan": {
            "id": plan.id,
            "name_en": plan.name_en,
            "name_kh": plan.name_kh,
            "price_usd": float(plan.amount or 0),
            "billing_interval": plan.billing_interval
        },
        "quotas": {
            "max_ai_scans_per_day": plan.max_ai_scans_per_day,
            "standard_scans_used_today": standard_scans_today,
            "standard_scans_remaining_today": max(0, plan.max_ai_scans_per_day - standard_scans_today),
            "max_deep_analysis_per_day": plan.max_deep_analysis_per_day,
            "deep_analysis_used_today": deep_scans_today,
            "deep_analysis_remaining_today": max(0, plan.max_deep_analysis_per_day - deep_scans_today),
            "max_watchlists": plan.max_watchlists,
            "backtesting_enabled": plan.backtesting_enabled,
            "telegram_alerts_enabled": plan.telegram_alerts_enabled,
            "agent_debate_enabled": plan.agent_debate_enabled
        }
    }


def check_and_consume_quota(
    db: Session,
    user_id: int,
    request_type: str,  # "standard_scan" or "deep_analysis"
    symbol: str = "XAUUSD",
    tokens_used: int = 0,
    cost_usd: float = 0.0,
    model_used: Optional[str] = None
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Server-side gatekeeper verifying that user has an active entitlement and
    unexhausted quota BEFORE permitting expensive AI or market operations.
    If authorized, records the usage into AIUsageRecord.
    """
    entitlements = get_user_entitlement(db, user_id)
    if not entitlements.get("is_active"):
        status = entitlements.get("subscription_status", "inactive")
        return False, f"Access denied: Subscription or trial is {status}. Please upgrade to continue.", entitlements

    quotas = entitlements.get("quotas", {})
    today_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

    if request_type == "deep_analysis":
        if quotas.get("deep_analysis_remaining_today", 0) <= 0:
            return False, f"Daily deep-analysis quota reached ({quotas.get('max_deep_analysis_per_day')} requests/day). Resets at 00:00 UTC.", entitlements
    elif request_type == "standard_scan":
        if quotas.get("standard_scans_remaining_today", 0) <= 0:
            return False, f"Daily AI market scan quota reached ({quotas.get('max_ai_scans_per_day')} requests/day). Resets at 00:00 UTC.", entitlements

    # Record usage
    record = AIUsageRecord(
        user_id=user_id,
        request_type=request_type,
        symbol=symbol,
        tokens_used=tokens_used,
        cost_usd=cost_usd,
        model_used=model_used,
        date_str=today_str
    )
    db.add(record)
    db.commit()

    return True, "Quota verified and recorded.", entitlements

