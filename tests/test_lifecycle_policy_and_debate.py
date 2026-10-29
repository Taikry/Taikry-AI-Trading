"""
Unit tests for Telegram lifecycle notification suppression policy,
4/4 daily quota enforcement, and live agent debate resilience.
"""
import pytest
from taikry.config import TELEGRAM_SEND_LIFECYCLE_EVENTS
from taikry.notifications.telegram_service import telegram_service
from taikry.trading.xauusd_signal_engine import xauusd_signal_engine
from taikry.agents.debate_engine import agent_debate_engine

def test_telegram_lifecycle_events_disabled_by_default():
    """Verify that by default, lifecycle transitions (TP/SL/BE) are not sent to Telegram."""
    assert TELEGRAM_SEND_LIFECYCLE_EVENTS is False

def test_lifecycle_notification_suppression():
    """Verify send_lifecycle_event_notification respects the policy flag."""
    event_dict = {
        "idempotency_key": "TEST-EVENT-001",
        "signal_id": "SIG-TEST-001",
        "symbol": "XAUUSD",
        "event_type": "TP1_HIT",
        "to_state": "TARGET_1_REACHED"
    }
    sent, msg_id, err = telegram_service.send_lifecycle_event_notification(event_dict)
    assert sent is False
    assert err == "LIFECYCLE_NOTIFICATIONS_DISABLED_BY_POLICY"

def test_daily_quota_structure():
    """Verify that XAUUSD daily hard limit is 4 and quota status reports correctly."""
    quota = xauusd_signal_engine.get_daily_quota_status()
    assert quota["daily_hard_limit"] == 4
    assert "signals_reserved_or_sent_today" in quota
    assert "remaining_quota" in quota
    assert quota["remaining_quota"] <= 4

def test_debate_engine_resilience():
    """Verify conduct_debate executes safely without throwing exceptions."""
    res = agent_debate_engine.conduct_debate("XAUUSD", "M15")
    assert isinstance(res, dict)
    assert res["symbol"] == "XAUUSD"
    assert "status" in res
    assert "turns" in res
    assert len(res["turns"]) >= 4
    assert "verdict" in res
    assert res["verdict"]["decision"] in ("APPROVE", "REJECT", "WAIT", "HOLD", "STANDBY")
