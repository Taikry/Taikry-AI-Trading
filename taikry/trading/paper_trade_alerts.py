"""Per-user, idempotent delivery for paper-trade TP/SL exits."""

import datetime
import logging
import smtplib
from email.message import EmailMessage
from html import escape
from typing import Any, Dict

from sqlalchemy.exc import IntegrityError

from taikry.config import SMTP_FROM_EMAIL, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USERNAME, SMTP_USE_TLS
from taikry.database.models import NotificationPreferences, PaperTradeAlert, TelegramLink, User
from taikry.database.session import SessionLocal

logger = logging.getLogger("taikry.trading.paper_trade_alerts")


def _send_email(recipient: str, subject: str, body: str) -> bool:
    if not (SMTP_HOST and SMTP_FROM_EMAIL and recipient):
        return False
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = SMTP_FROM_EMAIL
    message["To"] = recipient
    message.set_content(body)
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as smtp:
            if SMTP_USE_TLS:
                smtp.starttls()
            if SMTP_USERNAME:
                smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
            smtp.send_message(message)
        return True
    except Exception:
        logger.exception("Paper-trade alert email delivery failed")
        return False


def _messages(event: Dict[str, Any], language: str) -> tuple[str, str]:
    reason = str(event.get("exit_reason") or "CLOSED")
    symbol = escape(str(event.get("symbol") or "MARKET"))
    direction = escape(str(event.get("direction") or "TRADE"))
    price = float(event.get("exit_price") or 0)
    pnl = float(event.get("net_pnl") or 0)
    won = reason != "HIT_SL"
    if language == "kh":
        title = "ជួញដូរសាកល្បងបានដល់គោលដៅចំណេញ" if won else "ជួញដូរសាកល្បងបានដល់កម្រិតកាត់ខាត"
        subject = f"TAIKRY AI — {title}: {symbol}"
        body = (
            f"{title}\n"
            f"គូ/ទ្រព្យ៖ {symbol} · ទិស៖ {direction}\n"
            f"មូលហេតុ៖ {reason}\n"
            f"តម្លៃបិទ៖ {price:,.5f}\n"
            f"P&L សុទ្ធ៖ ${pnl:+,.2f}\n"
            "នេះជាកំណត់ត្រា Paper Trading ប៉ុណ្ណោះ។ មិនមានការបញ្ជាទិញទៅ broker ទេ។"
        )
        telegram = (
            f"🔔 <b>{title}</b>\n\n"
            f"ទ្រព្យ៖ <b>{symbol}</b> · ទិស៖ <b>{direction}</b>\n"
            f"មូលហេតុ៖ <b>{reason}</b>\n"
            f"តម្លៃបិទ៖ <code>{price:,.5f}</code>\n"
            f"P&amp;L សុទ្ធ៖ <b>${pnl:+,.2f}</b>\n"
            "<i>Paper Trading ប៉ុណ្ណោះ · មិនបានផ្ញើការបញ្ជាទិញទៅ broker ទេ។</i>"
        )
        return subject, body + "\n" + telegram

    title = "Paper trade take-profit reached" if won else "Paper trade stop-loss reached"
    subject = f"TAIKRY AI — {title}: {symbol}"
    body = (
        f"{title}\n"
        f"Symbol: {symbol} · Direction: {direction}\n"
        f"Reason: {reason}\n"
        f"Exit price: {price:,.5f}\n"
        f"Net P&L: ${pnl:+,.2f}\n"
        "This is a paper-trading record only. No broker order was placed."
    )
    telegram = (
        f"🔔 <b>{title}</b>\n\n"
        f"Symbol: <b>{symbol}</b> · Direction: <b>{direction}</b>\n"
        f"Reason: <b>{reason}</b>\n"
        f"Exit: <code>{price:,.5f}</code>\n"
        f"Net P&amp;L: <b>${pnl:+,.2f}</b>\n"
        "<i>Paper trading only · no broker order was placed.</i>"
    )
    return subject, body + "\n" + telegram


def dispatch_paper_trade_alert(event: Dict[str, Any]) -> Dict[str, Any]:
    """Claim and send one TP/SL alert to the owner's enabled channels."""
    user_id = event.get("user_id")
    trade_id = event.get("trade_id")
    if user_id is None or trade_id is None:
        return {"status": "SKIPPED", "reason": "NO_USER_OWNER"}

    event_type = str(event.get("exit_reason") or "CLOSED")
    event_key = f"paper-trade:{int(trade_id)}:{event_type}"
    db = SessionLocal()
    try:
        alert = db.query(PaperTradeAlert).filter(PaperTradeAlert.event_key == event_key).first()
        now = datetime.datetime.utcnow()
        if alert and alert.status in ("DELIVERED", "SUPPRESSED", "NO_CHANNEL"):
            return {"status": alert.status}
        if alert and alert.status == "PROCESSING" and (now - alert.updated_at).total_seconds() < 300:
            return {"status": "PROCESSING"}
        if not alert:
            alert = PaperTradeAlert(
                event_key=event_key,
                user_id=int(user_id),
                paper_trade_id=int(trade_id),
                event_type=event_type,
                status="PROCESSING",
                updated_at=now,
            )
            db.add(alert)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                return {"status": "ALREADY_CLAIMED"}
        else:
            alert.status = "PROCESSING"
            alert.updated_at = now
            db.commit()

        user = db.query(User).filter(User.id == int(user_id), User.is_active.is_(True)).first()
        if not user:
            alert.status = "SUPPRESSED"
            alert.error_summary = "USER_INACTIVE_OR_MISSING"
            alert.updated_at = datetime.datetime.utcnow()
            db.commit()
            return {"status": "SUPPRESSED"}

        preferences = db.query(NotificationPreferences).filter(
            NotificationPreferences.user_id == user.id
        ).first()
        if preferences and not preferences.paper_trade_alerts:
            alert.status = "SUPPRESSED"
            alert.updated_at = datetime.datetime.utcnow()
            db.commit()
            return {"status": "SUPPRESSED"}

        telegram_link = db.query(TelegramLink).filter(
            TelegramLink.user_id == user.id,
            TelegramLink.is_linked.is_(True),
        ).first()
        chat_id = telegram_link.telegram_chat_id if telegram_link else None
        email_available = bool(SMTP_HOST and SMTP_FROM_EMAIL and user.email)
        if not email_available and not chat_id:
            alert.status = "NO_CHANNEL"
            alert.channels = {"email": False, "telegram": False}
            alert.updated_at = datetime.datetime.utcnow()
            db.commit()
            return {"status": "NO_CHANNEL"}

        subject, message = _messages(event, user.language or "en")
        # Close the DB session before network I/O; the unique event key remains claimed.
        db.commit()
        db.close()

        email_sent = _send_email(user.email, subject, message.split("\n🔔", 1)[0]) if email_available else False
        telegram_sent = False
        if chat_id:
            from taikry.notifications.telegram_service import telegram_service
            telegram_sent = telegram_service.send_message(message.split("\n🔔", 1)[-1], chat_id=str(chat_id))

        update_db = SessionLocal()
        try:
            saved = update_db.query(PaperTradeAlert).filter(PaperTradeAlert.event_key == event_key).first()
            if saved:
                saved.channels = {"email": email_sent, "telegram": telegram_sent}
                saved.status = "DELIVERED" if (email_sent or telegram_sent) else "FAILED"
                saved.error_summary = None if (email_sent or telegram_sent) else "DELIVERY_FAILED"
                saved.updated_at = datetime.datetime.utcnow()
                update_db.commit()
        finally:
            update_db.close()
        return {"status": "DELIVERED" if (email_sent or telegram_sent) else "FAILED", "channels": {"email": email_sent, "telegram": telegram_sent}}
    except Exception:
        logger.exception("Paper-trade alert dispatch failed for trade %s", trade_id)
        db.rollback()
        return {"status": "FAILED"}
    finally:
        db.close()
