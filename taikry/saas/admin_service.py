"""
Administrative Service & Role-Based Access Control for ZYROX AI SaaS Platform.
Implements:
- Server-side RBAC verification (role == "ADMIN")
- Secure first-admin bootstrap from environment
- User account search, status management, and plan overrides
- Audit logging for all administrative actions
- System telemetry and AI token spend aggregation
"""

import os
import datetime
import logging
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from taikry.database.session import SessionLocal
from taikry.database.models import (
    User,
    UserSubscription,
    SubscriptionPlan,
    AIUsageRecord,
    AuditLog,
    SupportTicket,
    TelegramLink
)
from taikry.saas.security import hash_password

logger = logging.getLogger(__name__)


def is_admin_user(user: Optional[User]) -> bool:
    """Verifies that the user object has verified ADMIN privileges."""
    return bool(user and user.is_active and user.role == "ADMIN")


def bootstrap_admin_if_needed(db: Session) -> Optional[User]:
    """
    Bootstraps the first administrator using environment variables:
    SAAS_ADMIN_EMAIL and SAAS_ADMIN_PASSWORD.
    Never uses a hardcoded default password.
    """
    admin_email = os.getenv("SAAS_ADMIN_EMAIL", "").strip().lower()
    admin_password = os.getenv("SAAS_ADMIN_PASSWORD", "").strip()

    if not admin_email or not admin_password:
        return None
    if len(admin_password) < 16 or admin_password in {"change_this_admin_password_2026", "generate-a-long-random-admin-password"}:
        logger.warning("Initial admin bootstrap skipped: configure a unique password of at least 16 characters.")
        return None

    user = db.query(User).filter(User.email == admin_email).first()
    if not user:
        hashed_pwd, salt = hash_password(admin_password)
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        user = User(
            email=admin_email,
            hashed_password=hashed_pwd,
            salt=salt,
            full_name="Platform Administrator",
            role="ADMIN",
            is_verified=True,
            is_active=True,
            language="en",
            timezone="Asia/Phnom_Penh",
            created_at=now_utc,
            updated_at=now_utc
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        # Grant admin permanent active_paid subscription
        sub = UserSubscription(
            user_id=user.id,
            plan_id="premium",
            status="active_paid",
            current_period_starts_at=now_utc,
            current_period_expires_at=now_utc + datetime.timedelta(days=3650)
        )
        db.add(sub)
        db.commit()
    elif user.role != "ADMIN":
        # Never elevate an existing account just because its address matches an
        # environment setting; the account holder could already control it.
        logger.warning("Initial admin bootstrap skipped: configured admin email already belongs to a non-admin account.")
        return None

    return user


def admin_list_users(
    db: Session,
    query_str: Optional[str] = None,
    role_filter: Optional[str] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """Searches and lists users with subscription statuses."""
    q = db.query(User).filter(User.deleted_at == None)
    if query_str:
        s = f"%{query_str.strip().lower()}%"
        q = q.filter((User.email.like(s)) | (User.full_name.like(s)))
    if role_filter:
        q = q.filter(User.role == role_filter.upper())

    users = q.order_by(User.created_at.desc()).limit(limit).all()

    results = []
    for u in users:
        sub = db.query(UserSubscription).filter(UserSubscription.user_id == u.id).first()
        tg = db.query(TelegramLink).filter(TelegramLink.user_id == u.id).first()
        results.append({
            "id": u.id,
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role,
            "is_verified": u.is_verified,
            "is_active": u.is_active,
            "language": u.language,
            "subscription_status": sub.status if sub else "unsubscribed",
            "plan_id": sub.plan_id if sub else "none",
            "trial_expires_at": sub.trial_expires_at.isoformat() if (sub and sub.trial_expires_at) else None,
            "telegram_linked": bool(tg and tg.is_linked),
            "created_at": u.created_at.isoformat()
        })
    return results


def admin_set_user_status(
    db: Session,
    target_user_id: int,
    is_active: bool,
    admin_user_id: int,
    reason: Optional[str] = None
) -> Tuple[bool, str]:
    """Suspends or reactivates a user account."""
    user = db.query(User).filter(User.id == target_user_id).first()
    if not user:
        return False, "Target user not found."

    user.is_active = is_active
    action_name = "USER_ACTIVATED" if is_active else "USER_SUSPENDED"

    audit = AuditLog(
        actor_user_id=admin_user_id,
        action=action_name,
        target_type="user",
        target_id=str(target_user_id),
        details={"reason": reason or "Administrative action"}
    )
    db.add(audit)
    db.commit()
    return True, f"User {user.email} status updated to {'Active' if is_active else 'Suspended'}."


def admin_override_user_subscription(
    db: Session,
    target_user_id: int,
    plan_id: str,
    status: str,
    duration_days: int,
    admin_user_id: int
) -> Tuple[bool, str]:
    """Grants or updates plan entitlements for a user."""
    sub = db.query(UserSubscription).filter(UserSubscription.user_id == target_user_id).first()
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    expires_utc = now_utc + datetime.timedelta(days=duration_days)

    if not sub:
        sub = UserSubscription(
            user_id=target_user_id,
            plan_id=plan_id,
            status=status,
            current_period_starts_at=now_utc,
            current_period_expires_at=expires_utc
        )
        db.add(sub)
    else:
        sub.plan_id = plan_id
        sub.status = status
        sub.current_period_starts_at = now_utc
        sub.current_period_expires_at = expires_utc

    audit = AuditLog(
        actor_user_id=admin_user_id,
        action="SUBSCRIPTION_OVERRIDDEN",
        target_type="user_subscription",
        target_id=str(target_user_id),
        details={"plan_id": plan_id, "status": status, "duration_days": duration_days}
    )
    db.add(audit)
    db.commit()
    return True, f"Subscription updated to {plan_id} ({status}) for {duration_days} days."


def admin_get_analytics_summary(db: Session) -> Dict[str, Any]:
    """Computes aggregate SaaS metrics and token usage."""
    total_users = db.query(func.count(User.id)).filter(User.deleted_at == None).scalar() or 0
    active_trials = db.query(func.count(UserSubscription.id)).filter(UserSubscription.status == "trial_active").scalar() or 0
    paid_subs = db.query(func.count(UserSubscription.id)).filter(UserSubscription.status == "active_paid").scalar() or 0
    open_tickets = db.query(func.count(SupportTicket.id)).filter(SupportTicket.status == "OPEN").scalar() or 0

    # Total AI Scans
    total_scans = db.query(func.count(AIUsageRecord.id)).scalar() or 0
    total_tokens = db.query(func.sum(AIUsageRecord.tokens_used)).scalar() or 0
    total_cost = db.query(func.sum(AIUsageRecord.cost_usd)).scalar() or 0.0

    return {
        "total_users": total_users,
        "active_trials": active_trials,
        "paid_subscriptions": paid_subs,
        "open_support_tickets": open_tickets,
        "ai_usage": {
            "total_requests": total_scans,
            "total_tokens_consumed": total_tokens,
            "estimated_cost_usd": round(float(total_cost), 4)
        }
    }


def admin_get_audit_logs(db: Session, limit: int = 100) -> List[Dict[str, Any]]:
    """Retrieves immutable security and administrative audit records."""
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()
    return [
        {
            "id": l.id,
            "actor_user_id": l.actor_user_id,
            "action": l.action,
            "target_type": l.target_type,
            "target_id": l.target_id,
            "details": l.details,
            "ip_address": l.ip_address,
            "created_at_utc": l.created_at.isoformat()
        }
        for l in logs
    ]

