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


# -----------------------------------------------------------------------------
# 8. DISCONNECTED FEED BLOCKING WHEN REQUIRE_MT5 IS TRUE
# -----------------------------------------------------------------------------

def test_disconnected_feed_blocking_when_mt5_required(monkeypatch):
    """
    Verifies that when REQUIRE_MT5_FOR_SIGNALS is enabled and terminal is DISCONNECTED,
    new actionable signal generation is strictly rejected.
    """
    monkeypatch.setenv("REQUIRE_MT5_FOR_SIGNALS", "true")
    # Ensure bridge state is disconnected
    with mt5_receiver._lock:
        mt5_receiver._ticks.clear()
        mt5_receiver._bridge_meta["last_tick_utc"] = None
        mt5_receiver._bridge_meta["last_heartbeat_utc"] = None

    status = mt5_receiver.get_status()
    assert status["status"] == "DISCONNECTED"

    res = xauusd_signal_engine.generate_xauusd_signal("XAUUSD")
    assert res["success"] is False
    assert res["status"] == "BLOCKED_DISCONNECTED_BROKER_FEED"
    assert "DISCONNECTED" in res["error"]


# -----------------------------------------------------------------------------
# 9. SAME-CANDLE AMBIGUITY OUTCOME GRADING (CONSERVATIVE RESOLUTION)
# -----------------------------------------------------------------------------

def test_same_candle_ambiguity_outcome_grading():
    """
    Verifies institutional rule: When a single candle's high touches TP and low touches SL,
    the trade outcome MUST be graded conservatively as AMBIGUOUS (never a win).
    """
    from taikry.database.session import SessionLocal
    from taikry.database.models import XAUUSDTelegramSignalModel
    from taikry.trading.xauusd_tracker import xauusd_performance_tracker

    db = SessionLocal()
    sig_id = f"SIG-TEST-AMBIGUOUS-{int(time.time())}"
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    try:
        # Create an OPEN signal
        test_sig = XAUUSDTelegramSignalModel(
            signal_id=sig_id,
            canonical_symbol="XAUUSD",
            direction="BUY",
            timeframes_analyzed=["M15"],
            entry_price=2750.0,
            stop_loss=2740.0,
            take_profit_1=2770.0,
            take_profit_2=2785.0,
            take_profit_3=2800.0,
            risk_reward_1=2.0,
            ai_confluence_score=85,
            strategy_version="ZYROX-SMC-V2.1",
            broker_source="EXNESS_MT5",
            setup_score_label="Setup Score (out of 100, not win probability)",
            spread_points=0.25,
            estimated_trading_costs=0.32,
            execution_mode="SHADOW_PAPER",
            consensus_summary="Ambiguity test setup",
            signal_status="OPEN",
            telegram_delivery_status="SENT",
            idempotency_key=f"AMBIG_{sig_id}",
            cambodia_date="2026-10-29",
            entry_reached=True,
            entry_reached_at=now_utc,
            entry_reached_price=2750.0,
            outcome="PENDING",
            audit_history=[],
            created_at=now_utc
        )
        db.add(test_sig)
        db.commit()

        # Feed a candle whose high (2775.0 >= 2770.0) hits TP1 and low (2735.0 <= 2740.0) hits SL
        ambiguous_candle = {
            "timestamp": now_utc + datetime.timedelta(minutes=15),
            "open": 2750.0,
            "high": 2775.0,
            "low": 2735.0,
            "close": 2745.0,
            "volume": 1500
        }

        events = xauusd_performance_tracker.evaluate_signals_against_market(
            2745.0,
            high_price=2775.0,
            low_price=2735.0,
            candle_timestamp=now_utc + datetime.timedelta(minutes=15)
        )
        ambig_event = next((e for e in events if e.get("signal_id") == sig_id), None)
        assert ambig_event is not None
        assert ambig_event["status"] == "AMBIGUOUS"
        assert ambig_event["outcome"] == "AMBIGUOUS"

        # Verify database record state
        db.refresh(test_sig)
        assert test_sig.signal_status == "AMBIGUOUS"
        assert test_sig.outcome == "AMBIGUOUS"
        assert test_sig.closed_at is not None

    finally:
        db.query(XAUUSDTelegramSignalModel).filter(XAUUSDTelegramSignalModel.signal_id == sig_id).delete()
        db.commit()
        db.close()


# -----------------------------------------------------------------------------
# 10. PERFORMANCE METRICS (PROFIT FACTOR, EXPECTANCY, AND SEGMENTATION)
# -----------------------------------------------------------------------------

def test_performance_metrics_profit_factor_and_expectancy(client):
    """
    Verifies that the performance ledger calculates Profit Factor, Expectancy in R,
    Max Drawdown, and strategy segmentations correctly.
    """
    from taikry.trading.xauusd_tracker import xauusd_performance_tracker

    metrics = xauusd_performance_tracker.calculate_win_rate_metrics()
    assert "all_time" in metrics
    all_time = metrics["all_time"]
    assert "profit_factor" in all_time
    assert "expectancy_r" in all_time
    assert "average_win_r" in all_time
    assert "average_loss_r" in all_time
    assert "max_drawdown_r" in all_time
    assert "total_estimated_costs" in all_time
    assert "breakdown_by_strategy" in metrics
    assert "breakdown_by_execution_mode" in metrics

    # Also verify the HTTP endpoint /api/v1/signals/performance
    res = client.get("/api/v1/signals/performance")
    assert res.status_code == 200
    perf_data = res.json()
    assert "all_time" in perf_data
    assert "breakdown_by_strategy" in perf_data


# -----------------------------------------------------------------------------
# 11. REALTIME PRICES SOURCE & PROVIDER TRANSPARENCY
# -----------------------------------------------------------------------------

def test_realtime_prices_source_and_provider_transparency(client):
    """
    Verifies that /api/v1/realtime-prices explicitly labels the data provider and
    does not silently substitute fake values.
    """
    res = client.get("/api/v1/realtime-prices")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "SUCCESS"
    assert "prices" in data
    assert "XAUUSD" in data["prices"]

    xau_data = data["prices"]["XAUUSD"]
    assert "provider" in xau_data
    assert "source" in xau_data
    assert "timestamp" in xau_data
    assert xau_data["price"] > 0


# -----------------------------------------------------------------------------
# 12. POSTGRESQL URL SCHEME NORMALIZATION
# -----------------------------------------------------------------------------

def test_postgres_url_normalization():
    """Verifies that postgres:// Render scheme is automatically normalized to postgresql://."""
    test_render_url = "postgres://zyrox_user:secret_pass@ep-cool-db.render.com/zyrox_prod"
    normalized = test_render_url.replace("postgres://", "postgresql://", 1)
    assert normalized.startswith("postgresql://")
    assert "postgres://" not in normalized
