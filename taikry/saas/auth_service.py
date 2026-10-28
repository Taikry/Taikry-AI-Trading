"""
Authentication, Session Management, and User Profile Service for ZYROX AI SaaS Platform.
Implements:
- Email/Password Sign Up with PBKDF2-HMAC-SHA256
- Automated 14-Day Free Trial activation on signup
- Rate-limited Sign In with secure HttpOnly-compatible session token issuance
- Email verification & password reset workflows
- Profile updates, language/timezone preferences, and GDPR/CCPA-compliant account deletion
"""

import re
import secrets
import datetime
from typing import Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session

from taikry.database.session import SessionLocal
from taikry.database.models import (
    User,
    UserSession,
    VerificationToken,
    AuditLog,
    TelegramLink,
    NotificationPreferences
)
from taikry.saas.security import (
    hash_password,
    verify_password,
    generate_session_token,
    hash_token,
    auth_rate_limiter
)
from taikry.saas.trial_service import grant_14_day_trial

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
SESSION_DURATION_DAYS = 30
TOKEN_EXPIRE_HOURS = 24


def sign_up_user(
    db: Session,
    email: str,
    password: str,
    full_name: Optional[str] = None,
    language: str = "en",
    timezone: str = "Asia/Phnom_Penh",
    terms_accepted: bool = True,
    ip_address: Optional[str] = None
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Registers a new user, hashes password, grants 14-day trial, and initializes preferences.
    """
    norm_email = email.strip().lower()
    if not EMAIL_REGEX.match(norm_email):
        return False, "Invalid email address format.", None

    if not password or len(password) < 8:
        return False, "Password must be at least 8 characters long.", None

    if not terms_accepted:
        return False, "You must accept the Terms of Service and Privacy Policy to create an account.", None

    # Check for existing user
    existing = db.query(User).filter(User.email == norm_email, User.deleted_at == None).first()
    if existing:
        return False, "An account with this email address already exists.", None

    # Hash password with secure PBKDF2
    hashed_pwd, salt = hash_password(password)
    now_utc = datetime.datetime.now(datetime.timezone.utc)

    user = User(
        email=norm_email,
        hashed_password=hashed_pwd,
        salt=salt,
        full_name=full_name.strip() if full_name else None,
        role="USER",
        is_verified=False,
        is_active=True,
        language=language if language in ("en", "kh") else "en",
        timezone=timezone or "Asia/Phnom_Penh",
        terms_accepted_at=now_utc if terms_accepted else None,
        terms_version="v1.0",
        privacy_accepted_at=now_utc if terms_accepted else None,
        created_at=now_utc,
        updated_at=now_utc
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # 1. Grant 14-Day Free Trial
    grant_ok, grant_msg, grant_rec = grant_14_day_trial(db, user)

    # 2. Create Email Verification Token
    raw_verify_token = secrets.token_urlsafe(32)
    verify_token = VerificationToken(
        user_id=user.id,
        token_hash=hash_token(raw_verify_token),
        token_type="EMAIL_VERIFICATION",
        expires_at=now_utc + datetime.timedelta(hours=TOKEN_EXPIRE_HOURS),
        created_at=now_utc
    )
    db.add(verify_token)

    # 3. Create Default Notification Preferences
    notif_prefs = NotificationPreferences(
        user_id=user.id,
        ai_analysis_completed=True,
        signal_generated=True,
        signal_invalidated=True,
        daily_summary=True,
        trial_expiration_reminders=True,
        subscription_status_changes=True,
        system_announcements=True
    )
    db.add(notif_prefs)

    # 4. Audit Log
    audit = AuditLog(
        actor_user_id=user.id,
        action="USER_SIGNUP",
        target_type="user",
        target_id=str(user.id),
        details={"email": norm_email, "trial_granted": grant_ok},
        ip_address=ip_address
    )
    db.add(audit)
    db.commit()

    return True, "Account created successfully. 14-day free trial activated.", {
        "user_id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "verification_token": raw_verify_token,  # Can be sent via email or verified directly
        "trial_granted": grant_ok,
        "trial_message": grant_msg
    }


def login_user(
    db: Session,
    email: str,
    password: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Authenticates user with rate-limiting protection.
    Returns session token on success.
    """
    norm_email = email.strip().lower()
    rate_key = f"{ip_address or 'unknown'}:{norm_email}"

    # Check Rate Limit
    is_limited, sec_rem = auth_rate_limiter.is_rate_limited(rate_key)
    if is_limited:
        return False, f"Too many failed login attempts. Account temporarily locked for {sec_rem} seconds.", None

    user = db.query(User).filter(User.email == norm_email, User.deleted_at == None).first()
    if not user:
        auth_rate_limiter.record_failure(rate_key)
        return False, "Invalid email or password.", None

    if not user.is_active:
        return False, "This account has been deactivated or suspended. Please contact support.", None

    if not verify_password(password, user.hashed_password, user.salt):
        auth_rate_limiter.record_failure(rate_key)
        return False, "Invalid email or password.", None

    # Reset Rate Limiter on Success
    auth_rate_limiter.reset(rate_key)

    # Create 30-Day Session
    raw_token, token_hash = generate_session_token()
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    expires_utc = now_utc + datetime.timedelta(days=SESSION_DURATION_DAYS)

    session = UserSession(
        user_id=user.id,
        token_hash=token_hash,
        ip_address=ip_address,
        user_agent=user_agent[:250] if user_agent else None,
        expires_at=expires_utc,
        created_at=now_utc,
        last_seen_at=now_utc
    )
    db.add(session)

    audit = AuditLog(
        actor_user_id=user.id,
        action="USER_LOGIN_SUCCESS",
        target_type="user",
        target_id=str(user.id),
        details={"ip": ip_address},
        ip_address=ip_address
    )
    db.add(audit)
    db.commit()

    return True, "Login successful.", {
        "session_token": raw_token,
        "expires_at_utc": expires_utc.isoformat(),
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "is_verified": user.is_verified,
            "language": user.language,
            "timezone": user.timezone
        }
    }


def authenticate_session(db: Session, session_token: str) -> Optional[User]:
    """
    Validates a session token from request header/cookie.
    Updates last_seen_at timestamp. Returns User if valid, else None.
    """
    if not session_token or len(session_token) < 20:
        return None

    token_h = hash_token(session_token)
    now_utc = datetime.datetime.now(datetime.timezone.utc)

    session = db.query(UserSession).filter(
        UserSession.token_hash == token_h,
        UserSession.expires_at > now_utc
    ).first()

    if not session:
        return None

    user = db.query(User).filter(User.id == session.user_id, User.deleted_at == None).first()
    if not user or not user.is_active:
        return None

    # Touch session last_seen
    session.last_seen_at = now_utc
    db.commit()
    return user


def logout_user(db: Session, session_token: str) -> bool:
    """Invalidates the session token immediately."""
    if not session_token:
        return False
    token_h = hash_token(session_token)
    deleted = db.query(UserSession).filter(UserSession.token_hash == token_h).delete()
    db.commit()
    return deleted > 0


def verify_email_token(db: Session, raw_token: str) -> Tuple[bool, str]:
    """Verifies user's email address using a single-use token."""
    token_h = hash_token(raw_token)
    now_utc = datetime.datetime.now(datetime.timezone.utc)

    rec = db.query(VerificationToken).filter(
        VerificationToken.token_hash == token_h,
        VerificationToken.token_type == "EMAIL_VERIFICATION",
        VerificationToken.expires_at > now_utc,
        VerificationToken.used_at == None
    ).first()

    if not rec:
        return False, "Invalid or expired email verification token."

    user = db.query(User).filter(User.id == rec.user_id).first()
    if not user:
        return False, "User not found."

    user.is_verified = True
    rec.used_at = now_utc
    db.commit()
    return True, "Email verified successfully."


def request_password_reset(db: Session, email: str) -> Tuple[bool, str, Optional[str]]:
    """Generates a secure password reset token."""
    norm_email = email.strip().lower()
    user = db.query(User).filter(User.email == norm_email, User.deleted_at == None).first()
    if not user:
        # Safe response to prevent account enumeration
        return True, "If an account exists with this email, a password reset link has been dispatched.", None

    raw_token = secrets.token_urlsafe(32)
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    token = VerificationToken(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        token_type="PASSWORD_RESET",
        expires_at=now_utc + datetime.timedelta(hours=2),
        created_at=now_utc
    )
    db.add(token)
    db.commit()
    return True, "Password reset token generated.", raw_token


def reset_password(db: Session, raw_token: str, new_password: str) -> Tuple[bool, str]:
    """Updates password using a verified single-use password reset token."""
    if not new_password or len(new_password) < 8:
        return False, "New password must be at least 8 characters long."

    token_h = hash_token(raw_token)
    now_utc = datetime.datetime.now(datetime.timezone.utc)

    token_rec = db.query(VerificationToken).filter(
        VerificationToken.token_hash == token_h,
        VerificationToken.token_type == "PASSWORD_RESET",
        VerificationToken.expires_at > now_utc,
        VerificationToken.used_at == None
    ).first()

    if not token_rec:
        return False, "Invalid or expired password reset link."

    user = db.query(User).filter(User.id == token_rec.user_id).first()
    if not user:
        return False, "Associated user account not found."

    hashed_pwd, salt = hash_password(new_password)
    user.hashed_password = hashed_pwd
    user.salt = salt
    token_rec.used_at = now_utc

    # Invalidate all active sessions for security
    db.query(UserSession).filter(UserSession.user_id == user.id).delete()
    db.commit()
    return True, "Password reset successfully. Please sign in with your new credentials."


def delete_user_account(db: Session, user_id: int, reason: Optional[str] = None) -> bool:
    """
    Soft deletes user account and terminates all sessions and Telegram bindings.
    """
    user = db.query(User).filter(User.id == user_id, User.deleted_at == None).first()
    if not user:
        return False

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    user.deleted_at = now_utc
    user.is_active = False

    # Revoke sessions
    db.query(UserSession).filter(UserSession.user_id == user_id).delete()

    # Unlink Telegram
    db.query(TelegramLink).filter(TelegramLink.user_id == user_id).update({
        TelegramLink.is_linked: False,
        TelegramLink.unlinked_at: now_utc
    })

    audit = AuditLog(
        actor_user_id=user_id,
        action="USER_ACCOUNT_DELETED",
        target_type="user",
        target_id=str(user_id),
        details={"reason": reason or "User requested account deletion"}
    )
    db.add(audit)
    db.commit()
    return True

