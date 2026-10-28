"""
Unit & Integration Tests for Persistent Signal Lifecycle State Machine,
Institutional XAUUSD Multi-Timeframe Analysis Engine, and Priority Queue Monitoring.
"""

import pytest
import datetime
from fastapi.testclient import TestClient

from taikry.api.app import app
from taikry.database.session import init_db, SessionLocal
from taikry.database.models import SignalLifecycleModel
from taikry.trading.lifecycle import signal_lifecycle_manager, SignalState
from taikry.indicators.multi_timeframe import multi_timeframe_engine
from taikry.monitoring.engine import market_monitor_247


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    init_db()


@pytest.fixture(autouse=True)
def fast_mock_notifications(monkeypatch):
    """Mocks notification dispatches so tests execute in milliseconds without external network latency."""
    monkeypatch.setattr(signal_lifecycle_manager, "_notify_transition", lambda *args, **kwargs: None)


def test_signal_lifecycle_creation_and_fields():
    """Verifies that signals are created as persistent stateful objects with valid initial state."""
    sig = signal_lifecycle_manager.create_signal(
        symbol="XAUUSD",
        direction="BUY",
        entry_price=4050.0,
        stop_loss=4035.0,
        take_profit_1=4085.0,
        take_profit_2=4110.0,
        risk_reward="1:2.33",
        ai_score=88,
        timeframe="M15",
        initial_state=SignalState.WAITING_CONFIRMATION,
        trigger_cause="Initial test creation"
    )

    assert sig is not None
    assert sig["signal_id"].startswith("SIG-")
    assert sig["symbol"] == "XAUUSD"
    assert sig["direction"] == "BUY"
    assert sig["current_state"] == "WAITING_CONFIRMATION"
    assert sig["entry_price"] == 4050.0
    assert sig["stop_loss"] == 4035.0
    assert sig["take_profit_1"] == 4085.0
    assert sig["take_profit_2"] == 4110.0
    assert sig["ai_score"] == 88
    assert len(sig["state_history"]) >= 1


def test_signal_lifecycle_valid_transitions():
    """Verifies valid transitions from WAITING_CONFIRMATION -> ACTIVE -> TARGET_HIT."""
    sig = signal_lifecycle_manager.create_signal(
        symbol="XAUUSD",
        direction="BUY",
        entry_price=4050.0,
        stop_loss=4035.0,
        take_profit_1=4085.0,
        initial_state=SignalState.WAITING_CONFIRMATION
    )
    sig_id = sig["signal_id"]

    # 1. Transition to ACTIVE
    res_active = signal_lifecycle_manager.transition_signal(
        signal_id=sig_id,
        to_state=SignalState.ACTIVE,
        trigger_cause="Price reached entry",
        current_price=4050.0
    )
    assert res_active is not None
    assert res_active["current_state"] == "ACTIVE"

    # 2. Transition to TARGET_HIT
    res_target = signal_lifecycle_manager.transition_signal(
        signal_id=sig_id,
        to_state=SignalState.TARGET_HIT,
        trigger_cause="TP1 reached",
        current_price=4085.0
    )
    assert res_target is not None
    assert res_target["current_state"] == "TARGET_HIT"


def test_signal_lifecycle_disallow_illegal_transitions():
    """Verifies that the state machine rejects disallowed transitions."""
    sig = signal_lifecycle_manager.create_signal(
        symbol="EURUSD",
        direction="SELL",
        entry_price=1.1150,
        stop_loss=1.1200,
        take_profit_1=1.1050,
        initial_state=SignalState.WAITING_CONFIRMATION
    )
    sig_id = sig["signal_id"]

    # Trying to jump directly from WAITING_CONFIRMATION to TARGET_HIT is illegal
    res_illegal = signal_lifecycle_manager.transition_signal(
        signal_id=sig_id,
        to_state=SignalState.TARGET_HIT,
        trigger_cause="Illegal jump",
        current_price=1.1050
    )
    assert res_illegal is None


def test_signal_lifecycle_evaluation_invalidation_prior_to_entry():
    """Verifies that if price breaks SL before entry fill, signal transitions to INVALIDATED with bilingual reason."""
    sig = signal_lifecycle_manager.create_signal(
        symbol="XAUUSD",
        direction="BUY",
        entry_price=4050.0,
        stop_loss=4035.0,
        take_profit_1=4085.0,
        initial_state=SignalState.WAITING_CONFIRMATION
    )
    sig_id = sig["signal_id"]

    # Market price drops below stop loss (4030.0 < 4035.0) before reaching entry
    eval_events = signal_lifecycle_manager.evaluate_signals({"XAUUSD": 4030.0})
    target_event = next((e for e in eval_events if e["signal_id"] == sig_id), None)

    assert target_event is not None
    assert target_event["current_state"] == "INVALIDATED"
    assert "Stop Loss" in target_event["invalidation_reason_en"]
    assert "រចនាសម្ព័ន្ធទីផ្សារ" in target_event["invalidation_reason_kh"]


def test_signal_lifecycle_evaluation_entry_trigger_to_active():
    """Verifies that when market price reaches the entry price, signal transitions to ACTIVE."""
    sig = signal_lifecycle_manager.create_signal(
        symbol="BTCUSDT",
        direction="BUY",
        entry_price=80000.0,
        stop_loss=79000.0,
        take_profit_1=82000.0,
        initial_state=SignalState.WAITING_CONFIRMATION
    )
    sig_id = sig["signal_id"]

    # Price pulls back to entry level (79995.0)
    eval_events = signal_lifecycle_manager.evaluate_signals({"BTCUSDT": 79995.0})
    target_event = next((e for e in eval_events if e["signal_id"] == sig_id), None)

    assert target_event is not None
    assert target_event["current_state"] == "ACTIVE"


def test_signal_lifecycle_evaluation_tp_hit_when_active():
    """Verifies that an ACTIVE signal transitions to TARGET_HIT when market hits take profit."""
    sig = signal_lifecycle_manager.create_signal(
        symbol="SOLUSDT",
        direction="BUY",
        entry_price=100.0,
        stop_loss=95.0,
        take_profit_1=110.0,
        take_profit_2=120.0,
        initial_state=SignalState.ACTIVE
    )
    sig_id = sig["signal_id"]

    eval_events = signal_lifecycle_manager.evaluate_signals({"SOLUSDT": 111.0})
    target_event = next((e for e in eval_events if e["signal_id"] == sig_id), None)

    assert target_event is not None
    assert target_event["current_state"] == "TARGET_HIT"


def test_multi_timeframe_engine_hierarchy_and_sessions():
    """Verifies institutional 5-timeframe hierarchy analysis and session timing context."""
    analysis = multi_timeframe_engine.analyze_asset_hierarchy("XAUUSD")

    assert analysis["symbol"] == "XAUUSD"
    assert analysis["verified_price"] > 0
    assert analysis["overall_bias"] in ["BULLISH", "BEARISH", "NEUTRAL"]
    assert 55 <= analysis["confluence_score"] <= 95

    # Check all 5 timeframes exist in details
    tf_details = analysis["timeframe_details"]
    for tf in ["D1", "H4", "H1", "M15", "M5"]:
        assert tf in tf_details
        assert "bias" in tf_details[tf]
        assert "ema_20" in tf_details[tf]
        assert "rsi_14" in tf_details[tf]

    # Check dealing range equilibrium and OTE levels
    dr = analysis["dealing_range"]
    assert "daily_high" in dr
    assert "daily_low" in dr
    assert "equilibrium_price" in dr
    assert dr["pricing_tier"] in ["PREMIUM (EXPENSIVE)", "DISCOUNT (CHEAP)", "EQUILIBRIUM"]

    # Check session context
    sess = analysis["session_context"]
    assert "current_session" in sess
    assert "is_overlap_window" in sess

    # Check bilingual synthesis
    assert len(analysis["summary_en"]) > 20
    assert len(analysis["summary_kh"]) > 20


def test_api_signal_lifecycle_endpoints():
    """Verifies REST endpoints for signal lifecycle querying and manual transition."""
    client = TestClient(app)

    # 1. Query lifecycle list
    res = client.get("/api/v1/signals/lifecycle")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "SUCCESS"
    assert isinstance(data["signals"], list)

    # 2. Query specific signal
    if data["signals"]:
        first_sig = data["signals"][0]
        sig_id = first_sig["signal_id"]
        res_detail = client.get(f"/api/v1/signals/{sig_id}")
        assert res_detail.status_code == 200
        assert res_detail.json()["signal"]["signal_id"] == sig_id

    # 3. Create a candidate and transition via POST endpoint
    test_sig = signal_lifecycle_manager.create_signal(
        symbol="XAUUSD",
        direction="SELL",
        entry_price=4055.0,
        stop_loss=4070.0,
        take_profit_1=4020.0,
        initial_state=SignalState.CANDIDATE
    )
    sig_id = test_sig["signal_id"]

    trans_payload = {
        "to_state": "WAITING_CONFIRMATION",
        "trigger_cause": "Confluence approved by consensus",
        "current_price": 4055.0,
        "reason_en": "Multi-agent quorum reached.",
        "reason_kh": "សំឡេងភាគច្រើនរបស់ភ្នាក់ងារ AI ត្រូវបានសម្រេច។"
    }
    res_trans = client.post(f"/api/v1/signals/{sig_id}/transition", json=trans_payload)
    assert res_trans.status_code == 200
    assert res_trans.json()["signal"]["current_state"] == "WAITING_CONFIRMATION"


def test_api_xauusd_multi_timeframe_endpoint():
    """Verifies GET /api/v1/xauusd/multi-timeframe endpoint returns 5-timeframe hierarchy."""
    client = TestClient(app)
    res = client.get("/api/v1/xauusd/multi-timeframe?symbol=XAUUSD")
    assert res.status_code == 200
    data = res.json()
    assert data["symbol"] == "XAUUSD"
    assert "timeframe_details" in data
    assert "D1" in data["timeframe_details"]
    assert "H4" in data["timeframe_details"]
    assert "H1" in data["timeframe_details"]
    assert "M15" in data["timeframe_details"]
    assert "M5" in data["timeframe_details"]
    assert "summary_kh" in data
