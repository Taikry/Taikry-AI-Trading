"""
Server-Enforced 14-Day Free Trial Engine for ZYROX AI SaaS Platform.
Guarantees:
- Strict UTC timestamps on backend.
- One 14-day trial per eligible account/email (deduplicated against trial_grants).
- States: pending_verification, trial_active, trial_expired, active_paid, past_due, canceled, suspended.
- Zero fake credit card requirement.
- Server-side expiration evaluation on every protected request.
"""

import datetime
from typing import Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session

from taikry.database.session import SessionLocal
from taikry.database.models import User, UserSubscription, TrialGrantRecord, SubscriptionPlan

TRIAL_DURATION_DAYS = 14


def grant_14_day_trial(db: Session, user: Any) -> Tuple[bool, str, Optional[TrialGrantRecord]]:
    """
    Grants a server-enforced 14-day free trial to a newly registered or verified user.
    Enforces one-trial-per-account policy by checking prior grants for this email.
    """
    if isinstance(user, int):
        user = db.query(User).filter(User.id == user).first()
    if not user:
        return False, "User not found.", None
    # 1. Check existing grants by email (case-insensitive)
    normalized_email = user.email.strip().lower()
    existing_grant = db.query(TrialGrantRecord).filter(
        TrialGrantRecord.email == normalized_email
    ).first()

    if existing_grant:
        return False, "This email address has already redeemed a 14-day free trial.", existing_grant

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    expires_utc = now_utc + datetime.timedelta(days=TRIAL_DURATION_DAYS)

    # 2. Record immutable trial grant
    grant = TrialGrantRecord(
        user_id=user.id,
        email=normalized_email,
        duration_days=TRIAL_DURATION_DAYS,
        starts_at=now_utc,
        expires_at=expires_utc,
        status="ACTIVE"
    )
    db.add(grant)

    # 3. Create or update UserSubscription
    sub = db.query(UserSubscription).filter(UserSubscription.user_id == user.id).first()
    if not sub:
        sub = UserSubscription(
            user_id=user.id,
            plan_id="free_trial",
            status="trial_active",
            trial_starts_at=now_utc,
            trial_expires_at=expires_utc,
            current_period_starts_at=now_utc,
            current_period_expires_at=expires_utc
        )
        db.add(sub)
    else:
        sub.plan_id = "free_trial"
        sub.status = "trial_active"
        sub.trial_starts_at = now_utc
        sub.trial_expires_at = expires_utc
        sub.current_period_starts_at = now_utc
        sub.current_period_expires_at = expires_utc

    db.commit()
    db.refresh(grant)
    return True, f"14-Day Free Trial activated successfully until {expires_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}.", grant


def get_user_trial_status(db: Session, user_id: int) -> Dict[str, Any]:
    """
    Evaluates real-time trial state, days/hours remaining, and expiration.
    Automatically transitions status to 'trial_expired' on the server when time is up.
    """
    sub = db.query(UserSubscription).filter(UserSubscription.user_id == user_id).first()
    if not sub:
        return {
            "status": "unsubscribed",
            "has_trial": False,
            "is_active": False,
            "days_remaining": 0,
            "hours_remaining": 0,
            "progress_percent": 100.0,
            "message": "No active subscription or trial found."
        }

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    # Ensure timezone awareness
    trial_expires = sub.trial_expires_at
    if trial_expires and trial_expires.tzinfo is None:
        trial_expires = trial_expires.replace(tzinfo=datetime.timezone.utc)

    trial_starts = sub.trial_starts_at
    if trial_starts and trial_starts.tzinfo is None:
        trial_starts = trial_starts.replace(tzinfo=datetime.timezone.utc)

    # Check expiration
    if sub.status == "trial_active" and trial_expires:
        if now_utc >= trial_expires:
            sub.status = "trial_expired"
            db.commit()

    is_active = sub.status in ("trial_active", "active_paid")
    days_rem = 0
    hours_rem = 0
    progress_pct = 100.0

    if trial_expires and trial_starts:
        total_seconds = max(1, (trial_expires - trial_starts).total_seconds())
        remaining_seconds = (trial_expires - now_utc).total_seconds()
        if remaining_seconds > 0:
            days_rem = int(remaining_seconds // 86400)
            hours_rem = int((remaining_seconds % 86400) // 3600)
            elapsed_seconds = total_seconds - remaining_seconds
            progress_pct = round(min(100.0, max(0.0, (elapsed_seconds / total_seconds) * 100.0)), 1)
        else:
            days_rem = 0
            hours_rem = 0
            progress_pct = 100.0

    return {
        "status": sub.status,
        "plan_id": sub.plan_id,
        "has_trial": sub.trial_starts_at is not None,
        "is_active": is_active,
        "trial_starts_at_utc": trial_starts.isoformat() if trial_starts else None,
        "trial_expires_at_utc": trial_expires.isoformat() if trial_expires else None,
        "days_remaining": days_rem,
        "hours_remaining": hours_rem,
        "progress_percent": progress_pct,
        "cancel_at_period_end": sub.cancel_at_period_end
    }
