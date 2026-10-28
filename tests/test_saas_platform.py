"""
Integration and Unit Test Suite for ZYROX AI SaaS Platform
Tests Phases 1 through 12:
- Secure Sign Up, Password Hashing, Session Management
- 14-Day Free Trial Automatic Grant & UTC Expiration Gating
- Daily Quota Tracking and Server-Side Gating
- Telegram Link Token Generation, Webhook Verification, Preferences, and Unlinking
- Support Ticket Creation, History, and Admin Resolution
- Admin RBAC, Analytics, Plan Overrides, and User Status Gating
"""
import pytest
import datetime
import uuid
from fastapi.testclient import TestClient
from taikry.api.app import app
from taikry.database.session import SessionLocal, init_db
from taikry.database.models import User, UserSession, SubscriptionPlan, SupportTicket, UserSubscription
from taikry.saas.security import hash_password, verify_password
from taikry.saas.entitlement_service import check_and_consume_quota, init_default_plans
from taikry.saas.trial_service import grant_14_day_trial, get_user_trial_status

@pytest.fixture(scope="module")
def client():
    init_db()
    with SessionLocal() as db:
        init_default_plans(db)
    with TestClient(app) as c:
        yield c

def test_password_hashing_security():
    """Verifies PBKDF2-HMAC-SHA256 salt & password hashing correctness."""
    pwd = "InstitutionalSecret#2026"
    h, salt = hash_password(pwd)
    assert len(h) == 64
    assert len(salt) == 32
    assert verify_password(pwd, h, salt) is True
    assert verify_password("WrongPassword123", h, salt) is False

def test_user_sign_up_and_trial_auto_grant(client):
    """Verifies Phase 3 & 4: Sign up instantly provisions user with 14-day trial."""
    email = f"trader_{uuid.uuid4().hex[:8]}@zyrox.ai"
    payload = {
        "email": email,
        "password": "SecurePassword#999",
        "full_name": "Gold Scalper Pro",
        "language": "en"
    }
    r = client.post("/api/v1/auth/signup", json=payload)
    assert r.status_code == 200
    res = r.json()
    assert res["success"] is True
    data = res["data"]
    assert data["email"] == email
    assert data["trial_granted"] is True
    assert "session_token" in data
    assert "zyrox_session" in r.cookies

def test_duplicate_signup_prevention(client):
    """Verifies that an email cannot be registered more than once."""
    email = f"dup_{uuid.uuid4().hex[:8]}@zyrox.ai"
    payload = {"email": email, "password": "Password123#", "full_name": "Trader One"}
    r1 = client.post("/api/v1/auth/signup", json=payload)
    assert r1.status_code == 200

    r2 = client.post("/api/v1/auth/signup", json=payload)
    assert r2.status_code == 400
    assert "already exists" in r2.json()["detail"].lower()

def test_login_and_authenticated_me(client):
    """Verifies session authentication and /me profile endpoint."""
    email = f"login_{uuid.uuid4().hex[:8]}@zyrox.ai"
    password = "CorrectPassword#123"
    client.post("/api/v1/auth/signup", json={"email": email, "password": password, "full_name": "Apex Trader"})

    # Login
    r_login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r_login.status_code == 200
    token = r_login.json()["data"]["session_token"]

    # Access /me with Bearer token
    r_me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r_me.status_code == 200
    me_data = r_me.json()
    assert me_data["user"]["email"] == email
    assert me_data["user"]["full_name"] == "Apex Trader"
    assert me_data["trial"]["status"] == "trial_active"

def test_trial_expiration_server_enforcement(client):
    """Verifies that past UTC dates automatically transition to trial_expired."""
    email = f"expired_{uuid.uuid4().hex[:8]}@zyrox.ai"
    r = client.post("/api/v1/auth/signup", json={"email": email, "password": "Password123#"})
    token = r.json()["data"]["session_token"]
    user_id = r.json()["data"]["user_id"]

    # Artificially set trial_expires_at into the past in the database
    with SessionLocal() as db:
        sub = db.query(UserSubscription).filter(UserSubscription.user_id == user_id).first()
        assert sub is not None
        sub.trial_expires_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=2)
        db.commit()

    # Query trial status via API
    r_status = client.get("/api/v1/auth/trial-status", headers={"Authorization": f"Bearer {token}"})
    assert r_status.status_code == 200
    status_data = r_status.json()
    assert status_data["status"] == "trial_expired"
    assert status_data["is_active"] is False

def test_daily_quota_enforcement():
    """Verifies standard scan and deep analysis limits per plan."""
    with SessionLocal() as db:
        h, salt = hash_password("Pass123!#")
        user = User(
            email=f"quota_{uuid.uuid4().hex[:8]}@zyrox.ai",
            hashed_password=h,
            salt=salt,
            role="USER",
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        # Grant 14-day free trial (allows 3 deep analyses/day)
        grant_14_day_trial(db, user)

        # Call 1, 2, 3 should succeed
        for i in range(3):
            ok, msg, ent = check_and_consume_quota(db, user.id, "deep_analysis", symbol="XAUUSD")
            assert ok is True

        # 4th deep analysis must be blocked by quota gate
        ok_blocked, msg_blocked, ent_blocked = check_and_consume_quota(db, user.id, "deep_analysis", symbol="XAUUSD")
        assert ok_blocked is False
        assert "quota reached" in msg_blocked.lower()

def test_telegram_linking_lifecycle(client):
    """Verifies cryptographic token generation, webhook verification, preferences, and unlinking."""
    email = f"tg_{uuid.uuid4().hex[:8]}@zyrox.ai"
    r_signup = client.post("/api/v1/auth/signup", json={"email": email, "password": "Password123#"})
    token = r_signup.json()["data"]["session_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Generate link token
    r_tok = client.post("/api/v1/telegram-link/token", headers=headers)
    assert r_tok.status_code == 200
    tok_data = r_tok.json()
    assert "token" in tok_data
    assert "deep_link" in tok_data
    linking_token = tok_data["token"]

    # 2. Simulate Telegram webhook /start link_<token>
    fake_tg_id = 987654321
    fake_chat_id = 987654321
    r_hook = client.post("/api/v1/telegram-link/webhook", json={
        "message": {
            "text": f"/start link_{linking_token}",
            "chat": {"id": fake_chat_id},
            "from": {"id": fake_tg_id, "username": "zyrox_trader", "first_name": "Trader"}
        }
    })
    assert r_hook.status_code == 200
    assert r_hook.json()["linked"] is True

    # 3. Check link status
    r_st = client.get("/api/v1/telegram-link/status", headers=headers)
    assert r_st.status_code == 200
    st_data = r_st.json()
    assert st_data["linked"] is True
    assert st_data["telegram_username"] == "zyrox_trader"

    # 4. Update notification preferences
    r_pref = client.put("/api/v1/telegram-link/preferences", headers=headers, json={
        "signal_generated": True,
        "signal_invalidated": True,
        "trial_expiration_reminders": True,
        "daily_summary": False
    })
    assert r_pref.status_code == 200
    assert r_pref.json()["preferences"]["daily_summary"] is False

    # 5. Unlink account
    r_un = client.post("/api/v1/telegram-link/unlink", headers=headers)
    assert r_un.status_code == 200
    assert r_un.json()["success"] is True

    # Verify status is now unlinked
    r_st2 = client.get("/api/v1/telegram-link/status", headers=headers)
    assert r_st2.json()["linked"] is False

def test_support_ticket_submission_and_admin_reply(client):
    """Verifies ticket creation with TICK-YYYYMMDD-XXXX format and admin resolution."""
    # User signs up
    email = f"support_{uuid.uuid4().hex[:8]}@zyrox.ai"
    r_signup = client.post("/api/v1/auth/signup", json={"email": email, "password": "Password123#"})
    user_token = r_signup.json()["data"]["session_token"]

    # User creates support ticket
    r_tick = client.post("/api/v1/support/tickets", headers={"Authorization": f"Bearer {user_token}"}, json={
        "category": "technical",
        "priority": "HIGH",
        "subject": "MT5 Bridge Latency Spike",
        "message": "Encountered a 450ms latency spike during London open."
    })
    assert r_tick.status_code == 200
    tick_data = r_tick.json()["ticket"]
    assert tick_data["ticket_number"].startswith("TICK-")
    assert tick_data["status"] == "OPEN"
    ticket_id = tick_data["id"]

    # User views tickets
    r_list = client.get("/api/v1/support/tickets", headers={"Authorization": f"Bearer {user_token}"})
    assert r_list.status_code == 200
    assert len(r_list.json()) >= 1

    # Create admin user for reply
    admin_email = f"admin_{uuid.uuid4().hex[:8]}@zyrox.ai"
    h, s = hash_password("AdminPass123!")
    with SessionLocal() as db:
        admin_u = User(
            email=admin_email,
            hashed_password=h,
            salt=s,
            role="ADMIN",
            is_active=True
        )
        db.add(admin_u)
        db.commit()

    r_admin_login = client.post("/api/v1/auth/login", json={"email": admin_email, "password": "AdminPass123!"})
    admin_token = r_admin_login.json()["data"]["session_token"]

    # Admin lists tickets
    r_admin_ticks = client.get("/api/v1/admin/support/tickets", headers={"Authorization": f"Bearer {admin_token}"})
    assert r_admin_ticks.status_code == 200
    assert len(r_admin_ticks.json()) >= 1

    # Admin replies to ticket and marks RESOLVED
    r_reply = client.post(
        f"/api/v1/admin/support/tickets/{ticket_id}/reply",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "reply_message": "Our infrastructure team routed traffic to Frankfurt edge node.",
            "status": "RESOLVED"
        }
    )
    assert r_reply.status_code == 200
    assert r_reply.json()["status"] == "RESOLVED"

def test_admin_rbac_and_plan_override(client):
    """Verifies that non-admins cannot access admin endpoints and admin can override subscriptions."""
    # Normal user
    user_email = f"norm_{uuid.uuid4().hex[:8]}@zyrox.ai"
    r1 = client.post("/api/v1/auth/signup", json={"email": user_email, "password": "Password123#"})
    user_token = r1.json()["data"]["session_token"]
    user_id = r1.json()["data"]["user_id"]

    # Normal user blocked from admin
    r_blocked = client.get("/api/v1/admin/analytics", headers={"Authorization": f"Bearer {user_token}"})
    assert r_blocked.status_code == 403

    # Admin user
    admin_email = f"saas_admin_{uuid.uuid4().hex[:8]}@zyrox.ai"
    h, s = hash_password("AdminPass#123")
    with SessionLocal() as db:
        admin_u = User(
            email=admin_email,
            hashed_password=h,
            salt=s,
            role="ADMIN",
            is_active=True
        )
        db.add(admin_u)
        db.commit()

    r_admin_log = client.post("/api/v1/auth/login", json={"email": admin_email, "password": "AdminPass#123"})
    admin_token = r_admin_log.json()["data"]["session_token"]

    # Admin succeeds
    r_ana = client.get("/api/v1/admin/analytics", headers={"Authorization": f"Bearer {admin_token}"})
    assert r_ana.status_code == 200
    assert "total_users" in r_ana.json()

    # Admin overrides normal user to 'pro' plan
    r_over = client.put(
        f"/api/v1/admin/users/{user_id}/subscription",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "plan_slug": "pro",
            "duration_days": 30,
            "reason": "Promotion grant"
        }
    )
    assert r_over.status_code == 200
    assert r_over.json()["plan_slug"] == "pro"

def test_account_deletion_flow(client):
    """Verifies Phase 3: Complete user account deletion and session revocation."""
    email = f"delete_{uuid.uuid4().hex[:8]}@zyrox.ai"
    r = client.post("/api/v1/auth/signup", json={"email": email, "password": "Password123#"})
    token = r.json()["data"]["session_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Delete account
    r_del = client.delete("/api/v1/auth/account", headers=headers)
    assert r_del.status_code == 200
    assert r_del.json()["deleted"] is True

    # Confirm session revoked
    r_me = client.get("/api/v1/auth/me", headers=headers)
    assert r_me.status_code == 401
