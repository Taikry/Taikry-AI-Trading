"""
Unit & Integration Tests for Tiered VIP Telegram Subscription Bot & Expiring Links
==================================================================================
Covers:
1. VIP Tiers specification & metadata integrity.
2. Granting subscription & single-use auto-expiring Telegram invite link generation.
3. Subscription renewal & validity extension.
4. Subscription revocation, invite link invalidation & member eviction.
5. Background expiration sweep: evicting expired members and sending 24h reminders.
6. KPI calculation & revenue breakdown.
7. Telegram Bot commands (/vip, /myplan, /grantvip, /revokevip, /viplist).
8. Telegram inline button callback queries (sub:plans, sub:tier:PRO, sub:pay:bakong:PRO, etc.).
9. REST API endpoints (/api/v1/vip/*) with FastAPI TestClient.
"""
import datetime
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from taikry.api.app import app
from taikry.database.session import SessionLocal
from taikry.database.models import VIPSubscriptionModel, VIPInviteLinkRecord
from taikry.subscriptions.vip_manager import (
    vip_subscription_manager,
    VIPManager,
    SUBSCRIPTION_TIERS
)
from taikry.notifications.telegram_service import telegram_service


@pytest.fixture(autouse=True)
def clean_vip_db():
    """Cleans test VIP subscription entries before and after each test."""
    db = SessionLocal()
    try:
        db.query(VIPInviteLinkRecord).delete()
        db.query(VIPSubscriptionModel).delete()
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        db.query(VIPInviteLinkRecord).delete()
        db.query(VIPSubscriptionModel).delete()
        db.commit()
    finally:
        db.close()


def test_vip_tiers_configuration():
    """Verifies that all 4 tiers (FREE, PRO, VIP, LIFETIME) are properly configured."""
    tiers = vip_subscription_manager.get_tiers()
    assert "FREE" in tiers
    assert "PRO" in tiers
    assert "VIP" in tiers
    assert "LIFETIME" in tiers

    pro = tiers["PRO"]
    assert pro["price_usd"] == 49.0
    assert pro["duration_days"] == 30
    assert len(pro["features_en"]) >= 4
    assert len(pro["features_kh"]) >= 4

    vip = tiers["VIP"]
    assert vip["price_usd"] == 129.0
    assert vip["duration_days"] == 90

    life = tiers["LIFETIME"]
    assert life["is_lifetime"] is True
    assert life["price_usd"] == 299.0


def test_grant_vip_subscription_generates_expiring_link():
    """Verifies granting VIP generates single-use expiring invite link and saves to DB."""
    test_user_id = "8899771122"
    mock_link = "https://t.me/+TEST_PRO_INVITE_123"

    with patch.object(telegram_service, "create_chat_invite_link", return_value=(True, mock_link, None)) as mock_create, \
         patch.object(telegram_service, "send_message", return_value=True) as mock_send:

        sub = vip_subscription_manager.grant_subscription(
            user_id=test_user_id,
            username="crypto_whaler",
            full_name="Crypto Whale",
            tier="PRO",
            duration_days=30,
            channel_id="-10099887766",
            payment_ref="KHQR_TX_987654321",
            payment_amount=49.0
        )

        assert sub["user_id"] == test_user_id
        assert sub["tier"] == "PRO"
        assert sub["status"] == "ACTIVE"
        assert sub["invite_link"] == mock_link
        assert sub["duration_days"] == 30
        assert sub["expires_at"] is not None

        mock_create.assert_called_once()
        # Verify member_limit=1 (single-use personal invite link)
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["member_limit"] == 1
        assert call_kwargs["chat_id"] == "-10099887766"

        # Verify welcome message sent to user's Telegram
        mock_send.assert_called_once()
        assert str(mock_send.call_args[1]["chat_id"]) == test_user_id


def test_renew_vip_subscription_extends_expiry():
    """Verifies renewing an active subscription extends its expiration date."""
    test_user_id = "7766554433"

    with patch.object(telegram_service, "create_chat_invite_link", return_value=(True, "https://t.me/+LINK1", None)), \
         patch.object(telegram_service, "send_message", return_value=True):

        # Initial 30-day grant
        sub1 = vip_subscription_manager.grant_subscription(
            user_id=test_user_id,
            tier="PRO",
            duration_days=30
        )
        exp1 = datetime.datetime.fromisoformat(sub1["expires_at"])

        # Renew for another 30 days
        sub2 = vip_subscription_manager.renew_subscription(
            user_id=test_user_id,
            duration_days=30,
            payment_ref="RENEW_TX_123"
        )
        exp2 = datetime.datetime.fromisoformat(sub2["expires_at"])

        # Should be extended by approximately 30 days
        diff = (exp2 - exp1).total_seconds()
        assert 29 * 86400 <= diff <= 31 * 86400
        assert sub2["status"] == "ACTIVE"


def test_revoke_vip_subscription_evicts_user_and_revokes_link():
    """Verifies revoking a subscription invalidates invite link and evicts member from channel."""
    test_user_id = "5544332211"
    mock_link = "https://t.me/+LINK_TO_REVOKE"

    with patch.object(telegram_service, "create_chat_invite_link", return_value=(True, mock_link, None)), \
         patch.object(telegram_service, "revoke_chat_invite_link", return_value=(True, None)) as mock_rev_link, \
         patch.object(telegram_service, "kick_chat_member", return_value=(True, None)) as mock_kick, \
         patch.object(telegram_service, "send_message", return_value=True):

        vip_subscription_manager.grant_subscription(
            user_id=test_user_id,
            tier="VIP",
            duration_days=90,
            channel_id="-10099887766"
        )

        res = vip_subscription_manager.revoke_subscription(
            user_id=test_user_id,
            reason="Violation of community terms",
            kick_from_channel=True
        )

        assert res["status"] == "REVOKED"
        assert res["is_revoked"] is True
        assert res["revoked_reason"] == "Violation of community terms"

        mock_rev_link.assert_called_once_with("-10099887766", mock_link)
        mock_kick.assert_called_once_with("-10099887766", test_user_id)


def test_expiration_sweep_evicts_expired_subscribers():
    """Verifies background expiration sentinel evicts expired users and sends notifications."""
    db = SessionLocal()
    past_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=2)

    try:
        # Create an expired subscription in DB
        expired_sub = VIPSubscriptionModel(
            user_id="9998887771",
            username="expired_trader",
            tier="PRO",
            status="ACTIVE",
            channel_id="-10099887766",
            invite_link="https://t.me/+EXPIRED_LINK",
            duration_days=30,
            is_lifetime=False,
            starts_at=past_date - datetime.timedelta(days=30),
            expires_at=past_date,
            created_at=past_date - datetime.timedelta(days=30)
        )
        db.add(expired_sub)
        db.commit()
    finally:
        db.close()

    with patch.object(telegram_service, "revoke_chat_invite_link", return_value=(True, None)) as mock_rev, \
         patch.object(telegram_service, "kick_chat_member", return_value=(True, None)) as mock_kick, \
         patch.object(telegram_service, "send_message", return_value=True) as mock_send:

        sweep_res = vip_subscription_manager.check_and_process_expirations()

        assert sweep_res["checked_count"] >= 1
        assert sweep_res["expired_count"] == 1

        mock_rev.assert_called_once_with("-10099887766", "https://t.me/+EXPIRED_LINK")
        mock_kick.assert_called_once_with("-10099887766", "9998887771")
        mock_send.assert_called_once()
        assert str(mock_send.call_args[1]["chat_id"]) == "9998887771"

        # Verify DB status is now EXPIRED
        db = SessionLocal()
        try:
            rechecked = db.query(VIPSubscriptionModel).filter(VIPSubscriptionModel.user_id == "9998887771").first()
            assert rechecked.status == "EXPIRED"
        finally:
            db.close()


def test_pre_expiry_reminder_sent_within_24h():
    """Verifies that subscriptions expiring within 24h receive friendly renewal reminders."""
    db = SessionLocal()
    soon_date = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=12)

    try:
        soon_sub = VIPSubscriptionModel(
            user_id="1122334455",
            username="soon_expiring",
            tier="PRO",
            status="ACTIVE",
            channel_id="-10099887766",
            invite_link="https://t.me/+SOON_LINK",
            duration_days=30,
            is_lifetime=False,
            starts_at=soon_date - datetime.timedelta(days=30),
            expires_at=soon_date,
            last_reminded_at=None,
            created_at=soon_date - datetime.timedelta(days=30)
        )
        db.add(soon_sub)
        db.commit()
    finally:
        db.close()

    with patch.object(telegram_service, "send_message", return_value=True) as mock_send:
        sweep_res = vip_subscription_manager.check_and_process_expirations()
        assert sweep_res["reminded_count"] == 1
        mock_send.assert_called_once()
        assert str(mock_send.call_args[1]["chat_id"]) == "1122334455"

        # Verify last_reminded_at is now stamped in DB
        db = SessionLocal()
        try:
            rechecked = db.query(VIPSubscriptionModel).filter(VIPSubscriptionModel.user_id == "1122334455").first()
            assert rechecked.last_reminded_at is not None
        finally:
            db.close()


def test_vip_stats_calculation():
    """Verifies aggregation of active subscribers, expiring soon, and revenue."""
    with patch.object(telegram_service, "create_chat_invite_link", return_value=(True, "https://t.me/+LINK", None)), \
         patch.object(telegram_service, "send_message", return_value=True):

        vip_subscription_manager.grant_subscription("U1", tier="PRO", payment_amount=49.0)
        vip_subscription_manager.grant_subscription("U2", tier="VIP", payment_amount=129.0)
        vip_subscription_manager.grant_subscription("U3", tier="LIFETIME", payment_amount=299.0)

        stats = vip_subscription_manager.get_vip_stats()
        assert stats["total_subscribers"] == 3
        assert stats["active_subscribers"] == 3
        assert stats["tier_breakdown"]["PRO"] == 1
        assert stats["tier_breakdown"]["VIP"] == 1
        assert stats["tier_breakdown"]["LIFETIME"] == 1
        assert stats["total_revenue_usd"] == 477.0


def test_telegram_bot_commands_vip():
    """Tests /vip, /myplan, /grantvip, /revokevip, and /viplist bot commands."""
    with patch.object(telegram_service, "create_chat_invite_link", return_value=(True, "https://t.me/+INVITE", None)), \
         patch.object(telegram_service, "revoke_chat_invite_link", return_value=(True, None)), \
         patch.object(telegram_service, "kick_chat_member", return_value=(True, None)), \
         patch.object(telegram_service, "send_message", return_value=True):

        # 1. /vip command
        res_vip = telegram_service.handle_command("/vip", user_id=12345, chat_id="12345")
        assert "TAIKRY VIP SUBSCRIPTION TIERS" in res_vip["text"]
        assert "reply_markup" in res_vip

        # 2. /myplan command (before having VIP)
        res_plan = telegram_service.handle_command("/myplan", user_id=12345, chat_id="12345")
        assert "NO ACTIVE VIP" in res_plan["text"]

        # 3. /grantvip admin command
        res_grant = telegram_service.handle_command("/grantvip 12345 PRO 30", user_id=0, chat_id="0")
        assert "VIP ACCESS GRANTED" in res_grant["text"]
        assert "https://t.me/+INVITE" in res_grant["text"]

        # 4. /myplan command (after having VIP)
        res_plan_after = telegram_service.handle_command("/myplan", user_id=12345, chat_id="12345")
        assert "សកម្ម (ACTIVE)" in res_plan_after["text"]

        # 5. /viplist command
        res_list = telegram_service.handle_command("/viplist", user_id=0, chat_id="0")
        assert "VIP SUBSCRIBER INTELLIGENCE AUDIT" in res_list["text"]
        assert "Active VIPs:" in res_list["text"]

        # 6. /revokevip command
        res_rev = telegram_service.handle_command("/revokevip 12345", user_id=0, chat_id="0")
        assert "VIP access revoked for user" in res_rev["text"]


def test_telegram_callback_queries_vip():
    """Tests interactive callback button dispatchers (sub:plans, sub:tier:PRO, sub:myplan, etc.)."""
    with patch.object(telegram_service, "answer_callback_query", return_value=True), \
         patch.object(telegram_service, "send_message", return_value=True), \
         patch.object(telegram_service, "edit_message_text", return_value=True):

        # 1. sub:plans
        res1 = telegram_service.handle_callback_query("sub:plans", user_id=999, chat_id="999", callback_query_id="cb1")
        assert res1["status"] == "SUCCESS"
        assert res1["action"] == "sub_plans"

        # 2. sub:tier:PRO
        res2 = telegram_service.handle_callback_query("sub:tier:PRO", user_id=999, chat_id="999", callback_query_id="cb2")
        assert res2["status"] == "SUCCESS"
        assert res2["tier"] == "PRO"

        # 3. sub:pay:bakong:PRO
        res3 = telegram_service.handle_callback_query("sub:pay:bakong:PRO", user_id=999, chat_id="999", callback_query_id="cb3")
        assert res3["status"] == "SUCCESS"
        assert res3["method"] == "bakong"

        # 4. sub:myplan
        res4 = telegram_service.handle_callback_query("sub:myplan", user_id=999, chat_id="999", callback_query_id="cb4")
        assert res4["status"] == "SUCCESS"
        assert res4["action"] == "sub_myplan"

        # 5. sub:support
        res5 = telegram_service.handle_callback_query("sub:support", user_id=999, chat_id="999", callback_query_id="cb5")
        assert res5["status"] == "SUCCESS"
        assert res5["action"] == "sub_support"


def test_rest_api_vip_endpoints():
    """Tests all FastAPI REST endpoints for the VIP subscription system."""
    client = TestClient(app)

    # 1. GET /api/v1/vip/tiers
    r_tiers = client.get("/api/v1/vip/tiers")
    assert r_tiers.status_code == 200
    tiers_data = r_tiers.json()
    assert "PRO" in tiers_data
    assert "VIP" in tiers_data

    # 2. POST /api/v1/vip/grant
    with patch.object(telegram_service, "create_chat_invite_link", return_value=(True, "https://t.me/+REST_INVITE", None)), \
         patch.object(telegram_service, "send_message", return_value=True):

        grant_payload = {
            "user_id": "4433221100",
            "username": "api_trader",
            "full_name": "API Trader Pro",
            "tier": "VIP",
            "duration_days": 90,
            "payment_ref": "API_GRANT_REF",
            "payment_amount": 129.0
        }
        r_grant = client.post("/api/v1/vip/grant", json=grant_payload)
        assert r_grant.status_code == 200
        grant_resp = r_grant.json()
        assert grant_resp["status"] == "SUCCESS"
        assert grant_resp["subscription"]["tier"] == "VIP"
        assert grant_resp["subscription"]["invite_link"] == "https://t.me/+REST_INVITE"

        # 3. GET /api/v1/vip/subscribers
        r_subs = client.get("/api/v1/vip/subscribers")
        assert r_subs.status_code == 200
        subs_data = r_subs.json()
        assert subs_data["count"] >= 1
        assert any(s["user_id"] == "4433221100" for s in subs_data["subscribers"])

        # 4. GET /api/v1/vip/subscribers/{user_id}
        r_single = client.get("/api/v1/vip/subscribers/4433221100")
        assert r_single.status_code == 200
        assert r_single.json()["user_id"] == "4433221100"

        # 5. POST /api/v1/vip/renew
        r_renew = client.post("/api/v1/vip/renew", json={"user_id": "4433221100", "duration_days": 30})
        assert r_renew.status_code == 200
        assert r_renew.json()["status"] == "SUCCESS"

        # 6. GET /api/v1/vip/stats
        r_stats = client.get("/api/v1/vip/stats")
        assert r_stats.status_code == 200
        stats_data = r_stats.json()
        assert stats_data["total_subscribers"] >= 1

        # 7. POST /api/v1/vip/check-expirations
        r_check = client.post("/api/v1/vip/check-expirations")
        assert r_check.status_code == 200
        assert "checked_count" in r_check.json()

        # 8. POST /api/v1/vip/revoke
        with patch.object(telegram_service, "revoke_chat_invite_link", return_value=(True, None)), \
             patch.object(telegram_service, "kick_chat_member", return_value=(True, None)):
            r_revoke = client.post("/api/v1/vip/revoke", json={"user_id": "4433221100", "reason": "Test revoke"})
            assert r_revoke.status_code == 200
            assert r_revoke.json()["result"]["status"] == "REVOKED"
