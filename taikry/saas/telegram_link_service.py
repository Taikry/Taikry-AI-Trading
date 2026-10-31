"""
Telegram Account Linking & Notification Dispatch Service for ZYROX AI SaaS Platform.
Implements:
- Cryptographic single-use nonce token generation (15-min TTL).
- Safe deep-linking: https://t.me/<BOT_USERNAME>?start=link_<token>
- Webhook update processing to bind verified chat ID to authenticated user.
- Multi-account chat duplication prevention.
- Safe unlinking and granular notification preference controls.
"""

import secrets
import datetime
from typing import Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session

from taikry.config import TELEGRAM_BOT_USERNAME, TELEGRAM_BOT_TOKEN
from taikry.database.session import SessionLocal
from taikry.database.models import User, TelegramLink, NotificationPreferences, AuditLog

LINKING_TOKEN_TTL_MINUTES = 15


def generate_telegram_linking_token(db: Session, user_id: int) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Generates a cryptographically random, single-use linking token with 15-minute expiration.
    Returns the deep link for user navigation.
    """
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    expires_utc = now_utc + datetime.timedelta(minutes=LINKING_TOKEN_TTL_MINUTES)
    raw_token = secrets.token_urlsafe(24)

    link_rec = db.query(TelegramLink).filter(TelegramLink.user_id == user_id).first()
    if not link_rec:
        link_rec = TelegramLink(
            user_id=user_id,
            linking_token=raw_token,
            linking_token_expires_at=expires_utc,
            is_linked=False,
            created_at=now_utc
        )
        db.add(link_rec)
    else:
        link_rec.linking_token = raw_token
        link_rec.linking_token_expires_at = expires_utc

    db.commit()

    bot_username = (TELEGRAM_BOT_USERNAME or "zyrox_trading_bot").lstrip("@")
    deep_link = f"https://t.me/{bot_username}?start=link_{raw_token}"

    return True, "Linking token generated.", {
        "token": raw_token,
        "deep_link": deep_link,
        "expires_at_utc": expires_utc.isoformat(),
        "expires_in_seconds": int(LINKING_TOKEN_TTL_MINUTES * 60)
    }


def process_telegram_webhook_linking(
    db: Session,
    telegram_chat_id: str,
    linking_token: str,
    telegram_username: Optional[str] = None,
    telegram_first_name: Optional[str] = None
) -> Tuple[bool, str, Optional[int]]:
    """
    Called when user presses /start link_<token> in the official Telegram bot.
    Validates token expiration, ensures chat is not bound to another account,
    and binds chat to the user account atomically.
    """
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    raw_token = linking_token.strip().replace("link_", "")

    link_rec = db.query(TelegramLink).filter(
        TelegramLink.linking_token == raw_token,
        TelegramLink.linking_token_expires_at > now_utc
    ).first()

    if not link_rec:
        return False, "Invalid or expired linking token. Please generate a new link in your Account Center.", None

    chat_id_str = str(telegram_chat_id).strip()

    # Prevent chat ID from being bound to multiple accounts simultaneously
    existing_other = db.query(TelegramLink).filter(
        TelegramLink.telegram_chat_id == chat_id_str,
        TelegramLink.user_id != link_rec.user_id,
        TelegramLink.is_linked == True
    ).first()

    if existing_other:
        # Unlink previous binding to prevent account hijacking
        existing_other.is_linked = False
        existing_other.telegram_chat_id = None
        existing_other.unlinked_at = now_utc

    # Bind to user
    link_rec.telegram_chat_id = chat_id_str
    link_rec.telegram_username = telegram_username.lstrip("@") if telegram_username else None
    link_rec.telegram_first_name = telegram_first_name[:120] if telegram_first_name else None
    link_rec.is_linked = True
    link_rec.linked_at = now_utc
    # Consume token
    link_rec.linking_token = None
    link_rec.linking_token_expires_at = None

    audit = AuditLog(
        actor_user_id=link_rec.user_id,
        action="TELEGRAM_ACCOUNT_LINKED",
        target_type="telegram_link",
        target_id=chat_id_str,
        details={"username": telegram_username}
    )
    db.add(audit)
    db.commit()

    return True, "Telegram account linked successfully! You will now receive verified institutional alerts.", link_rec.user_id


def unlink_telegram_account(db: Session, user_id: int) -> bool:
    """Safely revokes the Telegram binding for the user."""
    link_rec = db.query(TelegramLink).filter(TelegramLink.user_id == user_id).first()
    if not link_rec or not link_rec.is_linked:
        return False

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    link_rec.is_linked = False
    link_rec.unlinked_at = now_utc
    chat_id = link_rec.telegram_chat_id
    link_rec.telegram_chat_id = None

    audit = AuditLog(
        actor_user_id=user_id,
        action="TELEGRAM_ACCOUNT_UNLINKED",
        target_type="telegram_link",
        target_id=str(chat_id)
    )
    db.add(audit)
    db.commit()
    return True


def get_telegram_link_status(db: Session, user_id: int) -> Dict[str, Any]:
    """Returns current Telegram connection status and preferences."""
    link_rec = db.query(TelegramLink).filter(TelegramLink.user_id == user_id).first()
    prefs = db.query(NotificationPreferences).filter(NotificationPreferences.user_id == user_id).first()
    from taikry.saas.entitlement_service import get_user_entitlement
    entitlement = get_user_entitlement(db, user_id)

    try:
        is_private_chat_id = int(str(link_rec.telegram_chat_id)) > 0 if link_rec and link_rec.telegram_chat_id else False
    except (TypeError, ValueError):
        is_private_chat_id = False
    is_linked = bool(link_rec and link_rec.is_linked and link_rec.telegram_chat_id and is_private_chat_id)
    signal_alerts_enabled = prefs.signal_generated if prefs else True
    plan_allows_signals = bool(entitlement.get("quotas", {}).get("telegram_alerts_enabled"))
    signal_delivery_ready = bool(
        entitlement.get("is_active") and plan_allows_signals and is_linked and signal_alerts_enabled
    )
    signal_delivery_reason = (
        "READY" if signal_delivery_ready else
        "SUBSCRIPTION_INACTIVE" if not entitlement.get("is_active") else
        "PLAN_DISABLED" if not plan_allows_signals else
        "TELEGRAM_NOT_LINKED" if not is_linked else
        "SIGNAL_NOTIFICATIONS_DISABLED"
    )
    return {
        "linked": is_linked,
        "is_linked": is_linked,
        "telegram_username": link_rec.telegram_username if is_linked else None,
        "telegram_first_name": link_rec.telegram_first_name if is_linked else None,
        "linked_at_utc": link_rec.linked_at.isoformat() if (is_linked and link_rec.linked_at) else None,
        "signal_delivery": {
            "ready": signal_delivery_ready,
            "reason": signal_delivery_reason,
            "plan_id": entitlement.get("plan", {}).get("id"),
            "subscription_active": bool(entitlement.get("is_active")),
            "plan_allows_signals": plan_allows_signals,
            "signal_notifications_enabled": bool(signal_alerts_enabled),
            "target_min_per_day": entitlement.get("quotas", {}).get("signal_alerts_target_min_per_day", 0),
            "max_per_day": entitlement.get("quotas", {}).get("max_signal_alerts_per_day", 0),
            "reserved_today": entitlement.get("quotas", {}).get("signal_alerts_reserved_today", 0),
            "remaining_today": entitlement.get("quotas", {}).get("signal_alerts_remaining_today", 0),
        },
        "preferences": {
            "ai_analysis_completed": prefs.ai_analysis_completed if prefs else True,
            "signal_generated": prefs.signal_generated if prefs else True,
            "signal_invalidated": prefs.signal_invalidated if prefs else True,
            "macro_events": prefs.macro_events if prefs else True,
            "daily_summary": prefs.daily_summary if prefs else True,
            "trial_expiration_reminders": prefs.trial_expiration_reminders if prefs else True,
            "subscription_status_changes": prefs.subscription_status_changes if prefs else True,
            "system_announcements": prefs.system_announcements if prefs else True,
            "paper_trade_alerts": prefs.paper_trade_alerts if prefs else True
        }
    }


def update_notification_preferences(db: Session, user_id: int, updates: Dict[str, bool]) -> Dict[str, bool]:
    """Updates user notification preferences."""
    prefs = db.query(NotificationPreferences).filter(NotificationPreferences.user_id == user_id).first()
    if not prefs:
        prefs = NotificationPreferences(user_id=user_id)
        db.add(prefs)

    for field in [
        "ai_analysis_completed", "signal_generated", "signal_invalidated", "macro_events",
        "daily_summary", "trial_expiration_reminders",
        "subscription_status_changes", "system_announcements", "paper_trade_alerts"
    ]:
        if field in updates:
            setattr(prefs, field, bool(updates[field]))

    prefs.updated_at = datetime.datetime.now(datetime.timezone.utc)
    db.commit()
    return {
        field: getattr(prefs, field) for field in [
            "ai_analysis_completed", "signal_generated", "signal_invalidated", "macro_events",
            "daily_summary", "trial_expiration_reminders",
            "subscription_status_changes", "system_announcements", "paper_trade_alerts"
        ]
    }
