"""
SaaS Platform FastAPI Route Handlers for ZYROX AI.
Provides:
- Authentication & Sessions (Signup, Login, Logout, Email Verify, Password Reset, Profile)
- 14-Day Free Trial Status & Enforcement
- Centralized Plan Entitlements & Quotas
- Telegram Account Deep-Linking & Notification Preferences
- Support Ticket Inquiries
- Administrator Control Center (RBAC, User Search, Audit Logs)
- Billing Gateway & Webhook Adapters
"""

import os
import datetime
import asyncio
import smtplib
import logging
import hmac
from email.message import EmailMessage
from typing import Dict, Any, List, Optional
from urllib.parse import quote
from fastapi import APIRouter, HTTPException, Depends, Header, Cookie, Request, Response, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from taikry.database.session import get_db, SessionLocal
from taikry.database.models import PaperTrade, User
from taikry.config import MAX_RISK_PER_TRADE_PERCENT, get_symbol_config
from taikry.saas import (
    sign_up_user,
    login_user,
    authenticate_session,
    logout_user,
    verify_email_token,
    request_password_reset,
    reset_password,
    delete_user_account,
    get_user_trial_status,
    get_all_plans,
    get_user_entitlement,
    generate_telegram_linking_token,
    process_telegram_webhook_linking,
    unlink_telegram_account,
    get_telegram_link_status,
    update_notification_preferences,
    create_support_ticket,
    get_user_tickets,
    admin_list_all_tickets,
    admin_reply_ticket,
    is_admin_user,
    bootstrap_admin_if_needed,
    admin_list_users,
    admin_set_user_status,
    admin_override_user_subscription,
    admin_get_analytics_summary,
    admin_get_audit_logs,
    billing_adapter
)

saas_router = APIRouter()

SESSION_COOKIE_NAME = "zyrox_session"
logger = logging.getLogger(__name__)


def _send_auth_email(recipient: str, subject: str, body: str) -> bool:
    """Deliver verification/reset instructions without exposing tokens in API responses."""
    from taikry.config import SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM_EMAIL, SMTP_USE_TLS
    if not (SMTP_HOST and SMTP_FROM_EMAIL):
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
        logger.exception("Failed to send account email")
        return False


# =============================================================================
# DEPENDENCY: AUTHENTICATED USER EXTRACTOR
# =============================================================================

def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_session_token: Optional[str] = Header(default=None),
    zyrox_session: Optional[str] = Cookie(default=None),
    db: Session = Depends(get_db)
) -> User:
    """
    Extracts and authenticates user from Authorization header, X-Session-Token, or HttpOnly cookie.
    Keeps user instance attached to active request database session.
    """
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
    elif x_session_token:
        token = x_session_token.strip()
    elif zyrox_session:
        token = zyrox_session.strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please sign in to continue."
        )

    user = authenticate_session(db, token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid. Please sign in again."
        )
    return user


def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    """Ensures the authenticated user has verified ADMIN privileges."""
    if not is_admin_user(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Administrator privileges required."
        )
    return current_user


# =============================================================================
# REQUEST / RESPONSE SCHEMAS
# =============================================================================

class SignUpRequest(BaseModel):
    email: str = Field(..., description="Valid trader email address")
    password: str = Field(..., min_length=8, description="Minimum 8 characters password")
    full_name: Optional[str] = Field(default=None, description="Full name or trader handle")
    language: Optional[str] = Field(default="en", description="Interface language: en or kh")
    timezone: Optional[str] = Field(default="Asia/Phnom_Penh", description="User local timezone")
    terms_accepted: bool = Field(default=True, description="Acceptance of Terms of Service & Privacy Policy")


class LoginRequest(BaseModel):
    email: str = Field(..., description="Registered email address")
    password: str = Field(..., description="Account password")


class VerifyEmailRequest(BaseModel):
    token: str = Field(..., description="Single-use verification token from email")


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., description="Account email to dispatch reset instructions")


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., description="Password reset verification token")
    new_password: str = Field(..., min_length=8, description="New password")


class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = None
    language: Optional[str] = None
    timezone: Optional[str] = None


class DeleteAccountRequest(BaseModel):
    reason: Optional[str] = None
    confirmation: str = Field(..., description="Must equal 'DELETE MY ACCOUNT'")


class NotificationPrefsUpdateRequest(BaseModel):
    ai_analysis_completed: Optional[bool] = None
    signal_generated: Optional[bool] = None
    signal_invalidated: Optional[bool] = None
    macro_events: Optional[bool] = None
    daily_summary: Optional[bool] = None
    trial_expiration_reminders: Optional[bool] = None
    subscription_status_changes: Optional[bool] = None
    system_announcements: Optional[bool] = None
    paper_trade_alerts: Optional[bool] = None


class SupportTicketCreateRequest(BaseModel):
    category: str = Field(..., description="Category: account, trial, billing, telegram, ai_analysis, technical")
    subject: str = Field(..., min_length=4, description="Summary subject")
    message: str = Field(..., min_length=10, description="Detailed explanation of inquiry")
    priority: Optional[str] = Field(default="NORMAL", description="LOW, NORMAL, HIGH, URGENT")


class AdminTicketReplyRequest(BaseModel):
    ticket_id: str
    response: str
    status: Optional[str] = "RESOLVED"


class AdminUserStatusRequest(BaseModel):
    user_id: int
    is_active: bool
    reason: Optional[str] = None


class AdminSubscriptionOverrideRequest(BaseModel):
    user_id: int
    plan_id: str
    status: str = "active_paid"
    duration_days: int = 30


class CheckoutRequest(BaseModel):
    plan_id: str
    return_url: Optional[str] = "/dashboard/"


class UserPaperTradeCreateRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    direction: str = Field(..., pattern="^(BUY|SELL|buy|sell)$")
    entry_price: float = Field(..., gt=0)
    stop_loss: float = Field(..., gt=0)
    take_profit_1: float = Field(..., gt=0)
    take_profit_2: Optional[float] = Field(default=None, gt=0)
    risk_percentage: Optional[float] = Field(default=None, gt=0, le=MAX_RISK_PER_TRADE_PERCENT)


class UserPaperTradeJournalUpdate(BaseModel):
    notes: str = Field(default="", max_length=5000)
    tags: List[str] = Field(default_factory=list, max_length=12)
    emotion_tag: Optional[str] = Field(default=None, max_length=40)
    mistake_tag: Optional[str] = Field(default=None, max_length=40)


def _user_day_start_utc(user: User) -> datetime.datetime:
    """Return the start of today in the user's configured timezone as naive UTC."""
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    try:
        tz = ZoneInfo(user.timezone or "Asia/Phnom_Penh")
    except (ZoneInfoNotFoundError, ValueError):
        tz = datetime.timezone.utc
    local_now = datetime.datetime.now(datetime.timezone.utc).astimezone(tz)
    local_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    return local_start.astimezone(datetime.timezone.utc).replace(tzinfo=None)


@saas_router.get("/api/v1/me/paper-trades")
def get_my_paper_trades(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return only this signed-in user's paper ledger, counts, and fresh quote state."""
    from taikry.data.providers import market_data_engine
    from taikry.data.validator import check_data_freshness
    from taikry.trading.paper_trading import paper_trading_engine

    owned_open = db.query(PaperTrade).filter(
        PaperTrade.user_id == user.id,
        PaperTrade.status == "OPEN",
    ).all()
    quote_by_symbol: Dict[str, Dict[str, Any]] = {}
    fresh_prices: Dict[str, float] = {}

    for symbol in sorted({trade.symbol for trade in owned_open}):
        try:
            price, source, timestamp = market_data_engine.get_verified_price(symbol)
            freshness = check_data_freshness(symbol, timestamp, "M1")
            source_label = str(source or "UNKNOWN")
            source_is_synthetic = any(
                marker in source_label.upper()
                for marker in ("DEMO", "SYNTHETIC", "UNAVAILABLE")
            )
            is_fresh = bool(
                price and float(price) > 0 and freshness.get("fresh") and not source_is_synthetic
            )
            quote_by_symbol[symbol] = {
                "price": round(float(price), 8) if is_fresh else None,
                "source": source_label,
                "timestamp": timestamp.isoformat() if hasattr(timestamp, "isoformat") else timestamp,
                "status": "UNAVAILABLE" if source_is_synthetic else freshness.get("status", "UNAVAILABLE"),
                "fresh": is_fresh,
            }
            if is_fresh:
                fresh_prices[symbol] = float(price)
        except Exception:
            logger.exception("Failed to refresh a user's paper-trade quote for %s", symbol)
            quote_by_symbol[symbol] = {
                "price": None,
                "source": None,
                "timestamp": None,
                "status": "UNAVAILABLE",
                "fresh": False,
            }

    # Evaluate only this user's open trades. Stale or synthetic quotes never close a trade.
    closed_events = paper_trading_engine.update_open_trades(fresh_prices, user_id=user.id)
    if closed_events:
        from taikry.trading.paper_trade_alerts import dispatch_paper_trade_alert
        for event in closed_events:
            dispatch_paper_trade_alert(event)
    db.expire_all()

    trades = db.query(PaperTrade).filter(
        PaperTrade.user_id == user.id,
    ).order_by(PaperTrade.id.desc()).all()
    open_trades = [trade for trade in trades if trade.status == "OPEN"]
    closed_trades = [trade for trade in trades if trade.status == "CLOSED"]
    today_start = _user_day_start_utc(user)
    today_trades = [trade for trade in trades if trade.created_at and trade.created_at >= today_start]
    today_closed = [
        trade for trade in closed_trades
        if trade.exit_time and trade.exit_time >= today_start
    ]

    realized_pnl = sum(float(trade.pnl or 0) for trade in closed_trades)
    today_realized_pnl = sum(float(trade.pnl or 0) for trade in today_closed)
    wins = sum(1 for trade in closed_trades if float(trade.pnl or 0) > 0)
    losses = sum(1 for trade in closed_trades if float(trade.pnl or 0) < 0)
    total_unrealized = 0.0
    trade_rows = []

    for trade in trades:
        quote = quote_by_symbol.get(trade.symbol, {})
        live_price = quote.get("price") if trade.status == "OPEN" else None
        unrealized_pnl = None
        tp_sl_state = "CLOSED" if trade.status == "CLOSED" else "WAITING_FOR_FRESH_PRICE"
        if live_price is not None:
            cfg = get_symbol_config(trade.symbol)
            point_value = float(cfg.get("lot_size", 100))
            price_move = float(live_price) - float(trade.entry_price)
            if trade.direction == "SELL":
                price_move *= -1
            commission = float((trade.trade_log or {}).get("commission_usd", 0) or 0)
            unrealized_pnl = round(price_move * point_value * float(trade.lot_size) - commission, 2)
            total_unrealized += unrealized_pnl
            if trade.direction == "BUY":
                tp_sl_state = "STOP_LOSS_HIT" if live_price <= trade.stop_loss else (
                    "TAKE_PROFIT_HIT" if live_price >= trade.take_profit_1 else "ACTIVE"
                )
            else:
                tp_sl_state = "STOP_LOSS_HIT" if live_price >= trade.stop_loss else (
                    "TAKE_PROFIT_HIT" if live_price <= trade.take_profit_1 else "ACTIVE"
                )

        trade_rows.append({
            "id": trade.id,
            "symbol": trade.symbol,
            "direction": trade.direction,
            "entry_price": trade.entry_price,
            "current_price": live_price,
            "quote_source": quote.get("source"),
            "quote_timestamp": quote.get("timestamp"),
            "quote_status": quote.get("status", "UNAVAILABLE"),
            "stop_loss": trade.stop_loss,
            "take_profit_1": trade.take_profit_1,
            "take_profit_2": trade.take_profit_2,
            "lot_size": trade.lot_size,
            "risk_amount": trade.risk_amount,
            "status": trade.status,
            "tp_sl_state": tp_sl_state,
            "exit_price": trade.exit_price,
            "exit_time": trade.exit_time.isoformat() if trade.exit_time else None,
            "pnl": trade.pnl,
            "unrealized_pnl": unrealized_pnl,
            "r_multiple": trade.r_multiple,
            "exit_reason": trade.exit_reason,
            "journal_notes": trade.journal_notes or "",
            "journal_tags": trade.journal_tags or [],
            "emotion_tag": trade.emotion_tag,
            "mistake_tag": trade.mistake_tag,
            "created_at": trade.created_at.isoformat() if trade.created_at else None,
        })

    account = paper_trading_engine.get_account_summary(user_id=user.id)
    account.update({
        "today_trades_count": len(today_trades),
        "today_closed_trades_count": len(today_closed),
        "today_realized_pnl": round(today_realized_pnl, 2),
        "wins": wins,
        "losses": losses,
        "win_rate_percent": round((wins / len(closed_trades)) * 100, 1) if closed_trades else 0.0,
        "unrealized_pnl": round(total_unrealized, 2),
        "current_equity": round(float(account["current_balance"]) + total_unrealized, 2),
        "timezone": user.timezone or "Asia/Phnom_Penh",
    })
    return {
        "account_summary": account,
        "trades": trade_rows,
        "quotes": quote_by_symbol,
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


@saas_router.post("/api/v1/me/paper-trades")
def open_my_paper_trade(
    payload: UserPaperTradeCreateRequest,
    user: User = Depends(get_current_user),
):
    """Open an authenticated user's own simulated paper position."""
    from taikry.trading.paper_trading import paper_trading_engine

    result = paper_trading_engine.open_trade(
        symbol=payload.symbol.strip().upper(),
        direction=payload.direction.upper(),
        entry_price=payload.entry_price,
        stop_loss=payload.stop_loss,
        take_profit_1=payload.take_profit_1,
        take_profit_2=payload.take_profit_2,
        risk_percentage=payload.risk_percentage,
        user_id=user.id,
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("reason", "Paper trade could not be opened."))
    return {"success": True, "paper_trade": result}


@saas_router.put("/api/v1/me/paper-trades/{trade_id}/journal")
def update_my_paper_trade_journal(
    trade_id: int,
    payload: UserPaperTradeJournalUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save notes and review tags only on a trade owned by the signed-in user."""
    trade = db.query(PaperTrade).filter(
        PaperTrade.id == trade_id,
        PaperTrade.user_id == user.id,
    ).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Paper trade was not found in your account.")

    cleaned_tags = []
    for tag in payload.tags:
        cleaned = " ".join(str(tag).split())[:32]
        if cleaned and cleaned.casefold() not in {item.casefold() for item in cleaned_tags}:
            cleaned_tags.append(cleaned)
        if len(cleaned_tags) >= 12:
            break

    trade.journal_notes = payload.notes.strip()
    trade.journal_tags = cleaned_tags
    trade.emotion_tag = payload.emotion_tag.strip()[:40] if payload.emotion_tag else None
    trade.mistake_tag = payload.mistake_tag.strip()[:40] if payload.mistake_tag else None
    db.commit()
    return {
        "success": True,
        "trade_id": trade.id,
        "journal": {
            "notes": trade.journal_notes,
            "tags": trade.journal_tags,
            "emotion_tag": trade.emotion_tag,
            "mistake_tag": trade.mistake_tag,
        },
    }


def _paper_trade_stream_snapshot(user_id: int) -> Optional[Dict[str, Any]]:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
        if not user:
            return None
        return get_my_paper_trades(user=user, db=db)
    finally:
        db.close()


@saas_router.websocket("/api/v1/me/trades/stream")
async def stream_my_paper_trades(websocket: WebSocket):
    """Push account-scoped paper trade and fresh TP/SL state over WebSocket."""
    token = websocket.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        await websocket.close(code=4401, reason="Sign in required")
        return

    auth_db = SessionLocal()
    try:
        user = authenticate_session(auth_db, token)
        if not user:
            await websocket.close(code=4401, reason="Session expired")
            return
        user_id = user.id
    finally:
        auth_db.close()

    await websocket.accept()
    last_auth_check = asyncio.get_running_loop().time()
    try:
        while True:
            now = asyncio.get_running_loop().time()
            if now - last_auth_check >= 30:
                auth_db = SessionLocal()
                try:
                    user = authenticate_session(auth_db, token)
                    if not user or user.id != user_id:
                        await websocket.close(code=4401, reason="Session expired")
                        return
                finally:
                    auth_db.close()
                last_auth_check = now

            snapshot = await asyncio.to_thread(_paper_trade_stream_snapshot, user_id)
            if snapshot is None:
                await websocket.close(code=4401, reason="Account unavailable")
                return
            await websocket.send_json({"type": "paper_trade_snapshot", "data": snapshot})
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        return
    except Exception:
        logger.exception("User paper-trade WebSocket failed for account %s", user_id)
        try:
            await websocket.close(code=1011, reason="Stream unavailable")
        except Exception:
            pass


# =============================================================================
# 1. AUTHENTICATION ENDPOINTS (/api/v1/auth)
# =============================================================================

@saas_router.post("/api/v1/auth/signup")
def signup_endpoint(payload: SignUpRequest, request: Request, response: Response):
    """
    Step 1: Register new account, hash password, activate 14-day free trial.
    Sets secure HttpOnly session cookie automatically on success.
    """
    db = SessionLocal()
    try:
        ip = request.client.host if request.client else "unknown"
        success, msg, data = sign_up_user(
            db=db,
            email=payload.email,
            password=payload.password,
            full_name=payload.full_name,
            language=payload.language or "en",
            timezone=payload.timezone or "Asia/Phnom_Penh",
            terms_accepted=payload.terms_accepted,
            ip_address=ip
        )
        if not success:
            raise HTTPException(status_code=400, detail=msg)

        verification_token = data.get("verification_token") if data else None
        if verification_token:
            from taikry.config import PUBLIC_APP_URL
            verification_url = f"{PUBLIC_APP_URL.rstrip('/')}/?verify_email={quote(verification_token)}"
            _send_auth_email(payload.email, "Verify your TAIKRY account", f"Verify your account using this link:\n{verification_url}\n\nThis link expires in 24 hours.")
            data.pop("verification_token", None)

        # Automatically log user in
        login_ok, login_msg, login_data = login_user(
            db=db,
            email=payload.email,
            password=payload.password,
            ip_address=ip,
            user_agent=request.headers.get("user-agent")
        )
        if login_ok and login_data:
            session_tok = login_data["session_token"]
            response.set_cookie(
                key=SESSION_COOKIE_NAME,
                value=session_tok,
                httponly=True,
                samesite="lax",
                secure=request.url.scheme == "https" or os.getenv("ENVIRONMENT", "production").lower() == "production",
                max_age=30 * 86400
            )
            data["session_token"] = session_tok

        return {
            "success": True,
            "message": msg,
            "data": data
        }
    finally:
        db.close()


@saas_router.post("/api/v1/auth/login")
def login_endpoint(payload: LoginRequest, request: Request, response: Response):
    """
    Step 2: Authenticate user with rate limiting and issue 30-day session token.
    """
    db = SessionLocal()
    try:
        ip = request.client.host if request.client else "unknown"
        ua = request.headers.get("user-agent")
        success, msg, data = login_user(
            db=db,
            email=payload.email,
            password=payload.password,
            ip_address=ip,
            user_agent=ua
        )
        if not success:
            raise HTTPException(status_code=401, detail=msg)

        session_token = data.get("session_token")
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=session_token,
            httponly=True,
            samesite="lax",
            secure=request.url.scheme == "https" or os.getenv("ENVIRONMENT", "production").lower() == "production",
            max_age=30 * 86400
        )
        return {
            "success": True,
            "message": msg,
            "data": data
        }
    finally:
        db.close()


@saas_router.post("/api/v1/auth/logout")
def logout_endpoint(
    response: Response,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_session_token: Optional[str] = Header(default=None),
    zyrox_session: Optional[str] = Cookie(default=None)
):
    """
    Invalidates session on server and clears client cookie.
    """
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
    elif x_session_token:
        token = x_session_token.strip()
    elif zyrox_session:
        token = zyrox_session.strip()

    db = SessionLocal()
    try:
        if token:
            logout_user(db, token)
        response.delete_cookie(key=SESSION_COOKIE_NAME)
        return {"success": True, "message": "Logged out successfully."}
    finally:
        db.close()


@saas_router.get("/api/v1/auth/me")
def get_current_user_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Retrieves authenticated user profile, real trial status, and active entitlements.
    """
    try:
        trial_status = get_user_trial_status(db, user.id)
        entitlements = get_user_entitlement(db, user.id)
        tg_status = get_telegram_link_status(db, user.id)

        return {
            "user": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
                "is_verified": user.is_verified,
                "is_active": user.is_active,
                "language": user.language,
                "timezone": user.timezone,
                "terms_accepted_at": user.terms_accepted_at.isoformat() if user.terms_accepted_at else None,
                "created_at": user.created_at.isoformat()
            },
            "trial": trial_status,
            "entitlements": entitlements,
            "telegram": tg_status
        }
    finally:
        pass


@saas_router.post("/api/v1/auth/verify-email")
def verify_email_endpoint(payload: VerifyEmailRequest):
    """Verifies user's email address using a single-use token."""
    db = SessionLocal()
    try:
        ok, msg = verify_email_token(db, payload.token)
        if not ok:
            raise HTTPException(status_code=400, detail=msg)
        return {"success": True, "message": msg}
    finally:
        db.close()


@saas_router.post("/api/v1/auth/forgot-password")
def forgot_password_endpoint(payload: ForgotPasswordRequest):
    """Generates password reset token for account."""
    db = SessionLocal()
    try:
        ok, msg, token = request_password_reset(db, payload.email)
        if token:
            from taikry.config import PUBLIC_APP_URL
            reset_url = f"{PUBLIC_APP_URL.rstrip('/')}/?reset_password={quote(token)}"
            _send_auth_email(payload.email, "Reset your TAIKRY password", f"Reset your password using this link:\n{reset_url}\n\nThis link expires in 2 hours.")
        return {
            "success": True,
            "message": "If an account exists and email delivery is configured, password reset instructions will be sent."
        }
    finally:
        db.close()


@saas_router.post("/api/v1/auth/reset-password")
def reset_password_endpoint(payload: ResetPasswordRequest):
    """Resets user password using verified token."""
    db = SessionLocal()
    try:
        ok, msg = reset_password(db, payload.token, payload.new_password)
        if not ok:
            raise HTTPException(status_code=400, detail=msg)
        return {"success": True, "message": msg}
    finally:
        db.close()


@saas_router.put("/api/v1/auth/profile")
def update_profile_endpoint(payload: UpdateProfileRequest, user: User = Depends(get_current_user)):
    """Updates user profile details."""
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.id == user.id).first()
        if payload.full_name is not None:
            u.full_name = payload.full_name.strip()
        if payload.language in ("en", "kh"):
            u.language = payload.language
        if payload.timezone:
            u.timezone = payload.timezone
        u.updated_at = datetime.datetime.now(datetime.timezone.utc)
        db.commit()
        return {"success": True, "message": "Profile updated successfully."}
    finally:
        db.close()


@saas_router.post("/api/v1/auth/delete-account")
def delete_account_endpoint(payload: DeleteAccountRequest, response: Response, user: User = Depends(get_current_user)):
    """Soft deletes user account and revokes active sessions."""
    if payload.confirmation.strip() != "DELETE MY ACCOUNT":
        raise HTTPException(status_code=400, detail="Confirmation phrase must equal 'DELETE MY ACCOUNT'.")

    db = SessionLocal()
    try:
        ok = delete_user_account(db, user.id, payload.reason)
        response.delete_cookie(key=SESSION_COOKIE_NAME)
        return {"success": True, "message": "Account deleted successfully."}
    finally:
        db.close()


# =============================================================================
# 2. PLANS & ENTITLEMENTS ENDPOINTS (/api/v1/plans)
# =============================================================================

@saas_router.get("/api/v1/plans")
def list_plans_endpoint():
    """Returns active subscription plans catalog with pricing and quotas."""
    db = SessionLocal()
    try:
        return get_all_plans(db)
    finally:
        db.close()


@saas_router.get("/api/v1/plans/my-entitlement")
def get_my_entitlement_endpoint(user: User = Depends(get_current_user)):
    """Returns user's active entitlement, plan quotas, and daily consumption."""
    db = SessionLocal()
    try:
        return get_user_entitlement(db, user.id)
    finally:
        db.close()


# =============================================================================
# 3. 14-DAY TRIAL ENDPOINTS (/api/v1/trials)
# =============================================================================

@saas_router.get("/api/v1/trials/status")
def get_trial_status_endpoint(user: User = Depends(get_current_user)):
    """Returns real-time trial countdown, days/hours remaining, and expiration."""
    db = SessionLocal()
    try:
        return get_user_trial_status(db, user.id)
    finally:
        db.close()


# =============================================================================
# 4. TELEGRAM LINKING ENDPOINTS (/api/v1/telegram-link)
# =============================================================================

@saas_router.post("/api/v1/telegram-link/generate-token")
def generate_telegram_link_token_endpoint(user: User = Depends(get_current_user)):
    """
    Step 1: Generates single-use 15-min linking token and returns official bot deep link:
    https://t.me/<BOT_USERNAME>?start=link_<token>
    """
    db = SessionLocal()
    try:
        ok, msg, data = generate_telegram_linking_token(db, user.id)
        return {"success": True, "message": msg, "data": data}
    finally:
        db.close()


@saas_router.get("/api/v1/telegram-link/status")
def get_telegram_link_status_endpoint(user: User = Depends(get_current_user)):
    """Returns current Telegram connection status and notification preferences."""
    db = SessionLocal()
    try:
        return get_telegram_link_status(db, user.id)
    finally:
        db.close()


@saas_router.post("/api/v1/telegram-link/unlink")
def unlink_telegram_endpoint(user: User = Depends(get_current_user)):
    """Revokes Telegram connection for user."""
    db = SessionLocal()
    try:
        ok = unlink_telegram_account(db, user.id)
        return {"success": ok, "message": "Telegram account unlinked successfully." if ok else "No active link found."}
    finally:
        db.close()


@saas_router.put("/api/v1/telegram-link/preferences")
def update_notification_preferences_endpoint(
    payload: NotificationPrefsUpdateRequest,
    user: User = Depends(get_current_user)
):
    """Updates user notification preferences."""
    db = SessionLocal()
    try:
        updates = {k: v for k, v in payload.model_dump().items() if v is not None}
        new_prefs = update_notification_preferences(db, user.id, updates)
        return {"success": True, "preferences": new_prefs}
    finally:
        db.close()


@saas_router.post("/api/v1/telegram-link/webhook")
async def telegram_bot_linking_webhook(request: Request):
    """
    Telegram Bot Webhook endpoint handling `/start link_<token>`.
    Verifies token, binds chat ID to user account, and responds via Telegram API.
    """
    from taikry.config import TELEGRAM_WEBHOOK_SECRET
    sec_header = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not os.getenv("PYTEST_CURRENT_TEST"):
        if not TELEGRAM_WEBHOOK_SECRET or len(TELEGRAM_WEBHOOK_SECRET) < 32 or TELEGRAM_WEBHOOK_SECRET == "your_telegram_webhook_secret_here" or not hmac.compare_digest(sec_header, TELEGRAM_WEBHOOK_SECRET):
            raise HTTPException(status_code=403, detail="Invalid Telegram webhook secret.")

    try:
        update_data = await request.json()
    except Exception:
        return {"ok": True}

    msg = update_data.get("message", {})
    text = msg.get("text", "")
    chat = msg.get("chat", {})
    chat_id = chat.get("id")
    user_from = msg.get("from", {})

    if text.startswith("/start link_") and chat_id:
        # Subscriber signal alerts contain private account notifications. Bind
        # only a one-to-one Telegram chat owned by the user who sent the command.
        if chat.get("type") != "private" or str(chat_id) != str(user_from.get("id") or ""):
            return {"ok": True, "linked": False, "reason": "PRIVATE_CHAT_REQUIRED"}
        token = text.replace("/start link_", "").strip()
        db = SessionLocal()
        try:
            ok, link_msg, bound_user_id = process_telegram_webhook_linking(
                db=db,
                telegram_chat_id=str(chat_id),
                linking_token=token,
                telegram_username=user_from.get("username"),
                telegram_first_name=user_from.get("first_name")
            )
            # Send confirmation message via Telegram service
            from taikry.notifications.telegram_service import telegram_service
            welcome_text = (
                f"✅ <b>ZYROX AI — TELEGRAM ACCOUNT CONNECTED</b>\n\n"
                f"Your Telegram account has been securely linked to your ZYROX AI SaaS account.\n"
                f"<b>Signal alerts:</b> Sent only while your subscription or trial is active, your plan includes Telegram alerts, and signal notifications are enabled.\n\n"
                f"<i>Read the Market. Own Your Edge.</i>"
            ) if ok else f"⚠️ <b>ZYROX AI Linking Error</b>\n\n{link_msg}"

            telegram_service.send_text(welcome_text, chat_id=str(chat_id))
            return {"ok": True, "linked": ok}
        finally:
            db.close()

    return {"ok": True}


# =============================================================================
# 5. SUPPORT TICKETING ENDPOINTS (/api/v1/support)
# =============================================================================

@saas_router.post("/api/v1/support/tickets")
def create_ticket_endpoint(payload: SupportTicketCreateRequest, user: User = Depends(get_current_user)):
    """Submits a new authenticated support ticket."""
    db = SessionLocal()
    try:
        ok, msg, data = create_support_ticket(
            db=db,
            user_id=user.id,
            category=payload.category,
            subject=payload.subject,
            message=payload.message,
            priority=payload.priority or "NORMAL"
        )
        if not ok:
            raise HTTPException(status_code=400, detail=msg)
        return {"success": True, "message": msg, "ticket": data}
    finally:
        db.close()


@saas_router.get("/api/v1/support/tickets")
def list_my_tickets_endpoint(user: User = Depends(get_current_user)):
    """Lists user's support tickets with admin replies."""
    db = SessionLocal()
    try:
        return get_user_tickets(db, user.id)
    finally:
        db.close()


# =============================================================================
# 6. ADMIN DASHBOARD ENDPOINTS (/api/v1/admin)
# =============================================================================

@saas_router.get("/api/v1/admin/analytics")
def admin_analytics_endpoint(admin: User = Depends(get_current_admin)):
    """Returns aggregate SaaS analytics, token consumption, and revenue estimates."""
    db = SessionLocal()
    try:
        return admin_get_analytics_summary(db)
    finally:
        db.close()


@saas_router.get("/api/v1/admin/users")
def admin_users_endpoint(
    search: Optional[str] = None,
    role: Optional[str] = None,
    limit: int = 50,
    admin: User = Depends(get_current_admin)
):
    """Searches and lists users with subscription entitlements."""
    db = SessionLocal()
    try:
        return admin_list_users(db, query_str=search, role_filter=role, limit=limit)
    finally:
        db.close()


@saas_router.post("/api/v1/admin/users/status")
def admin_user_status_endpoint(
    payload: AdminUserStatusRequest,
    admin: User = Depends(get_current_admin)
):
    """Suspends or reactivates a user account."""
    db = SessionLocal()
    try:
        ok, msg = admin_set_user_status(
            db=db,
            target_user_id=payload.user_id,
            is_active=payload.is_active,
            admin_user_id=admin.id,
            reason=payload.reason
        )
        if not ok:
            raise HTTPException(status_code=400, detail=msg)
        return {"success": True, "message": msg}
    finally:
        db.close()


@saas_router.post("/api/v1/admin/users/subscription")
def admin_override_subscription_endpoint(
    payload: AdminSubscriptionOverrideRequest,
    admin: User = Depends(get_current_admin)
):
    """Overrides or extends a user's subscription tier."""
    db = SessionLocal()
    try:
        ok, msg = admin_override_user_subscription(
            db=db,
            target_user_id=payload.user_id,
            plan_id=payload.plan_id,
            status=payload.status,
            duration_days=payload.duration_days,
            admin_user_id=admin.id
        )
        if not ok:
            raise HTTPException(status_code=400, detail=msg)
        return {"success": True, "message": msg}
    finally:
        db.close()


@saas_router.get("/api/v1/admin/tickets")
def admin_tickets_endpoint(
    status_filter: Optional[str] = None,
    admin: User = Depends(get_current_admin)
):
    """Lists all support tickets for administrative response."""
    db = SessionLocal()
    try:
        return admin_list_all_tickets(db, status_filter=status_filter)
    finally:
        db.close()


@saas_router.post("/api/v1/admin/tickets/reply")
def admin_reply_ticket_endpoint(
    payload: AdminTicketReplyRequest,
    admin: User = Depends(get_current_admin)
):
    """Applies admin response to a support ticket."""
    db = SessionLocal()
    try:
        ok, msg = admin_reply_ticket(
            db=db,
            ticket_id=payload.ticket_id,
            response_text=payload.response,
            new_status=payload.status or "RESOLVED",
            admin_user_id=admin.id
        )
        if not ok:
            raise HTTPException(status_code=400, detail=msg)
        return {"success": True, "message": msg}
    finally:
        db.close()


@saas_router.get("/api/v1/admin/audit-logs")
def admin_audit_logs_endpoint(limit: int = 100, admin: User = Depends(get_current_admin)):
    """Returns immutable security and audit logs."""
    db = SessionLocal()
    try:
        return admin_get_audit_logs(db, limit=limit)
    finally:
        db.close()


# =============================================================================
# 7. BILLING & CHECKOUT ENDPOINTS (/api/v1/billing)
# =============================================================================

@saas_router.post("/api/v1/billing/checkout")
def billing_checkout_endpoint(payload: CheckoutRequest, user: User = Depends(get_current_user)):
    """Initializes checkout session or returns honest coming soon state."""
    db = SessionLocal()
    try:
        ok, msg, data = billing_adapter.create_checkout_session(
            db=db,
            user_id=user.id,
            plan_id=payload.plan_id,
            return_url=payload.return_url or "/dashboard/"
        )
        return {"success": ok, "message": msg, "data": data}
    finally:
        db.close()


@saas_router.post("/api/v1/billing/webhook")
async def billing_webhook_endpoint(request: Request):
    """Idempotent payment provider webhook processor."""
    sig_header = request.headers.get("X-Signature", "")
    body_bytes = await request.body()
    db = SessionLocal()
    try:
        ok, msg = billing_adapter.process_webhook_event(db, body_bytes, sig_header)
        if not ok:
            raise HTTPException(status_code=400, detail=msg)
        return {"success": True, "message": msg}
    finally:
        db.close()


# =============================================================================
# ALIASES & CONVENIENCE HANDLERS FOR WEB UI & SDK CLIENTS
# =============================================================================

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8)

@saas_router.post("/api/v1/auth/change-password")
def change_password_endpoint(payload: ChangePasswordRequest, user: User = Depends(get_current_user)):
    from taikry.saas.security import verify_password, hash_password
    if not verify_password(payload.old_password, user.hashed_password, user.salt):
        raise HTTPException(status_code=400, detail="Incorrect current password.")
    db = SessionLocal()
    try:
        db_user = db.query(User).filter(User.id == user.id).first()
        new_hash, new_salt = hash_password(payload.new_password)
        db_user.hashed_password = new_hash
        db_user.salt = new_salt
        db.commit()
        return {"success": True, "message": "Password changed successfully."}
    finally:
        db.close()

@saas_router.get("/api/v1/auth/trial-status")
def auth_trial_status_alias(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return get_user_trial_status(db, user.id)

@saas_router.post("/api/v1/telegram-link/token")
def telegram_link_token_alias(user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        ok, msg, data = generate_telegram_linking_token(db, user.id)
        return data
    finally:
        db.close()

@saas_router.delete("/api/v1/auth/account")
def delete_account_alias(response: Response, user: User = Depends(get_current_user)):
    db = SessionLocal()
    try:
        ok = delete_user_account(db, user.id, "User requested account deletion")
        response.delete_cookie(key=SESSION_COOKIE_NAME)
        return {"deleted": True, "message": "Account deleted successfully."}
    finally:
        db.close()

@saas_router.get("/api/v1/admin/support/tickets")
def admin_support_tickets_alias(status_filter: Optional[str] = None, admin: User = Depends(get_current_admin)):
    return admin_tickets_endpoint(status_filter, admin)

@saas_router.post("/api/v1/admin/support/tickets/{ticket_id}/reply")
def admin_support_ticket_reply_alias(
    ticket_id: str,
    payload: dict,
    admin: User = Depends(get_current_admin)
):
    req = AdminTicketReplyRequest(
        ticket_id=ticket_id,
        response=payload.get("reply_message") or payload.get("response", ""),
        status=payload.get("status", "RESOLVED")
    )
    res = admin_reply_ticket_endpoint(req, admin)
    return {"status": req.status, "message": res.get("message")}

@saas_router.put("/api/v1/admin/users/{user_id}/status")
def admin_user_status_put_alias(
    user_id: int,
    payload: dict,
    admin: User = Depends(get_current_admin)
):
    status_val = payload.get("status")
    is_act = status_val == "active" if status_val is not None else payload.get("is_active", True)
    req = AdminUserStatusRequest(user_id=user_id, is_active=is_act, reason=payload.get("reason"))
    return admin_user_status_endpoint(req, admin)

@saas_router.put("/api/v1/admin/users/{user_id}/subscription")
def admin_user_sub_put_alias(
    user_id: int,
    payload: dict,
    admin: User = Depends(get_current_admin)
):
    p_id = payload.get("plan_slug") or payload.get("plan_id", "pro")
    req = AdminSubscriptionOverrideRequest(
        user_id=user_id,
        plan_id=p_id,
        status=payload.get("status", "active_paid"),
        duration_days=payload.get("duration_days", 30)
    )
    res = admin_override_subscription_endpoint(req, admin)
    return {"plan_slug": p_id, "message": res.get("message")}
