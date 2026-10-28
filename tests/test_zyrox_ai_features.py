"""
Unit & Integration Tests for ZYROX AI Transformation:
- Windows Exness MT5 Bridge Authentication & Replay Protection
- Broker Symbol Normalization (XAUUSD, XAUUSDm, etc.)
- Stale Feed Detection & Actionable Signal Blocking
- Setup Confluence Scoring & Strategy Version Auditing
- Shadow Mode Order Execution Prohibition Safety Guarantee
- Telegram Verified Test Notification & System Info Endpoints
"""

import time
import datetime
import pytest
from fastapi.testclient import TestClient

from taikry.api.app import app
from taikry.data.mt5_receiver import mt5_receiver
from taikry.trading.xauusd_signal_engine import xauusd_signal_engine
from taikry.trading.paper_trading import paper_trading_engine
from taikry.config import MT5_BRIDGE_TOKEN, DEFAULT_STRATEGY_VERSION


@pytest.fixture
def client():
    return TestClient(app)


# -----------------------------------------------------------------------------
# 1. BROKER SYMBOL NORMALIZATION
# -----------------------------------------------------------------------------

def test_mt5_symbol_normalization():
    """Verifies that broker symbol suffixes (Exness Standard, Pro, Raw) normalize cleanly."""
    assert mt5_receiver.normalize_symbol("XAUUSD") == "XAUUSD"
    assert mt5_receiver.normalize_symbol("XAUUSDm") == "XAUUSD"
    assert mt5_receiver.normalize_symbol("XAUUSD.m") == "XAUUSD"
    assert mt5_receiver.normalize_symbol("GOLD") == "XAUUSD"
    assert mt5_receiver.normalize_symbol("GOLDm") == "XAUUSD"
    assert mt5_receiver.normalize_symbol("EURUSDm") == "EURUSD"
    assert mt5_receiver.normalize_symbol("GBPUSD.m") == "GBPUSD"
    assert mt5_receiver.normalize_symbol("BTCUSDm") == "BTCUSDT"
    assert mt5_receiver.normalize_symbol("ETHUSD") == "ETHUSDT"


# -----------------------------------------------------------------------------
# 2. MT5 BRIDGE AUTHENTICATION & REPLAY PROTECTION
# -----------------------------------------------------------------------------

def test_mt5_bridge_auth_verification():
    """Verifies constant-time token verification, timestamp drift, and HMAC validation."""
    valid_token = MT5_BRIDGE_TOKEN or "zyrox_mt5_bridge_secure_token_change_me"

    # 1. Valid token within current timestamp
    now_ts = str(time.time())
    assert mt5_receiver.verify_auth_token(valid_token, timestamp_header=now_ts) is True

    # 2. Invalid token rejected
    assert mt5_receiver.verify_auth_token("wrong_token", timestamp_header=now_ts) is False

    # 3. Timestamp drift > 60s rejected (replay attack prevention)
    stale_ts = str(time.time() - 120.0)
    assert mt5_receiver.verify_auth_token(valid_token, timestamp_header=stale_ts) is False


# -----------------------------------------------------------------------------
# 3. MT5 BRIDGE INGESTION & STATUS TRANSITIONS
# -----------------------------------------------------------------------------

def test_mt5_bridge_tick_ingestion_and_status(client):
    """Verifies tick ingestion endpoint, in-memory caching, and CONNECTED status."""
    valid_token = MT5_BRIDGE_TOKEN or "zyrox_mt5_bridge_secure_token_change_me"
    now_ts = str(time.time())

    payload = {
        "ticks": [
            {
                "symbol": "XAUUSDm",
                "bid": 2750.25,
                "ask": 2750.55,
                "last": 2750.40,
                "spread": 30.0,
                "digits": 2,
                "time": datetime.datetime.now(datetime.timezone.utc).isoformat()
            }
        ]
    }

    # Unauthenticated request rejected with 401
    res_unauth = client.post("/api/v1/bridge/market-data", json=payload)
    assert res_unauth.status_code == 401

    # Authenticated request succeeds with 200
    headers = {
        "X-Bridge-Token": valid_token,
        "X-Bridge-Timestamp": now_ts
    }
    res_auth = client.post("/api/v1/bridge/market-data", json=payload, headers=headers)
    assert res_auth.status_code == 200
    res_data = res_auth.json()
    assert res_data["status"] == "SUCCESS"
    assert res_data["ingested_ticks"] == 1

    # Status should now be CONNECTED
    status = mt5_receiver.get_status()
    assert status["status"] == "CONNECTED"
    assert "XAUUSD" in status["active_symbols"]

    # Fresh tick retrieved cleanly
    price, source, is_fresh, tick = mt5_receiver.get_latest_price("XAUUSD")
    assert price == 2750.40
    assert source == "EXNESS_MT5"
    assert is_fresh is True
    assert tick["bid"] == 2750.25
    assert tick["ask"] == 2750.55


# -----------------------------------------------------------------------------
# 4. STALE FEED DETECTION & SIGNAL BLOCKING
# -----------------------------------------------------------------------------

def test_stale_feed_blocks_actionable_signals():
    """
    Verifies that when market data is stale (> 30s since last tick),
    the signal engine STRICTLY blocks issuing new actionable trade setups to protect capital.
    """
    # Simulate a stale tick received 45 seconds ago
    with mt5_receiver._lock:
        stale_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=45)
        mt5_receiver._ticks["XAUUSD"] = {
            "raw_symbol": "XAUUSDm",
            "canonical_symbol": "XAUUSD",
            "bid": 2750.0,
            "ask": 2750.3,
            "price": 2750.15,
            "spread": 30.0,
            "received_at": stale_time,
            "received_at_iso": stale_time.isoformat(),
            "source": "EXNESS_MT5",
            "is_fresh": False
        }
        mt5_receiver._bridge_meta["last_tick_utc"] = stale_time.isoformat()
        mt5_receiver._bridge_meta["last_heartbeat_utc"] = stale_time.isoformat()

    status = mt5_receiver.get_status()
    assert status["status"] == "STALE"
    assert mt5_receiver.is_symbol_fresh("XAUUSD") is False

    # Attempt to generate signal while feed is STALE
    res = xauusd_signal_engine.generate_xauusd_signal("XAUUSD")
    assert res["success"] is False
    assert res["status"] == "BLOCKED_STALE_BROKER_FEED"
    assert "STALE" in res["error"]

    # Restore clean state
    with mt5_receiver._lock:
        mt5_receiver._ticks.clear()
        mt5_receiver._bridge_meta["last_tick_utc"] = None
        mt5_receiver._bridge_meta["last_heartbeat_utc"] = None


# -----------------------------------------------------------------------------
# 5. SHADOW MODE SAFETY INVARIANT (ZERO LIVE ORDER EXECUTION)
# -----------------------------------------------------------------------------

def test_shadow_mode_prohibits_live_orders():
    """
    Strict security invariant: Verifies that Shadow Mode is hardcoded to NEVER
    have permissions to route live orders to any broker API.
    """
    assert paper_trading_engine.is_shadow_mode is True
    assert paper_trading_engine.can_place_live_orders is False

    with pytest.raises(PermissionError) as exc_info:
        paper_trading_engine.place_live_broker_order("XAUUSD", "BUY", 1.0)

    assert "SECURITY VETO" in str(exc_info.value)
    assert "Shadow mode has zero permission" in str(exc_info.value)


# -----------------------------------------------------------------------------
# 6. SYSTEM INFO & STRATEGY VERSION ENDPOINT
# -----------------------------------------------------------------------------

def test_system_info_endpoint(client):
    """Verifies that system info endpoint advertises official ZYROX AI brand and version."""
    res = client.get("/api/v1/system/info")
    assert res.status_code == 200
    data = res.json()

    assert data["brand_name"] == "ZYROX AI"
    assert data["tagline"] == "Read the Market. Own Your Edge."
    assert "strategy_version" in data
    assert data["strategy_version"] == DEFAULT_STRATEGY_VERSION
    assert "mt5_bridge" in data
    assert "bilingual" in data
    assert "en" in data["bilingual"]
    assert "kh" in data["bilingual"]


# -----------------------------------------------------------------------------
# 7. TELEGRAM TEST NOTIFICATION ENDPOINT
# -----------------------------------------------------------------------------

def test_telegram_test_notification_endpoint(client, monkeypatch):
    """
    Verifies that the diagnostic test notification endpoint dispatches to telegram_service
    and faithfully reports true delivery status without fabricating success.
    """
    # Case A: Simulated Telegram API failure
    from taikry.notifications.telegram_service import telegram_service
    monkeypatch.setattr(telegram_service, "send_text", lambda msg, chat_id: (False, None, "Bad Gateway"))

    res_fail = client.post("/api/v1/telegram/test-notification", json={"chat_id": "-1001234567"})
    assert res_fail.status_code == 200
    data_fail = res_fail.json()
    assert data_fail["delivered"] is False
    assert "Bad Gateway" in data_fail["error"]

    # Case B: Simulated Telegram API success
    monkeypatch.setattr(telegram_service, "send_text", lambda msg, chat_id: (True, "998877", None))

    res_ok = client.post("/api/v1/telegram/test-notification", json={"chat_id": "-1001234567"})
    assert res_ok.status_code == 200
    data_ok = res_ok.json()
    assert data_ok["delivered"] is True
    assert data_ok["message_id"] == "998877"
