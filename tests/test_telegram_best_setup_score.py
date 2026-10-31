import pytest
from unittest.mock import patch, MagicMock

from taikry.monitoring.engine import MarketMonitor247
from taikry.notifications.telegram_service import TelegramService
from taikry.agents.consensus_engine import AIConsensusEngine
from fastapi.testclient import TestClient
from taikry.api.app import app

client = TestClient(app)

def test_telegram_bilingual_report_score_threshold_enforced():
    """Only complete, fresh and approved non-gold setups may use the generic sender."""
    svc = TelegramService()
    svc.token = "unit-test-token"
    svc.default_chat_id = "-1001234567890"

    with patch.object(svc, "_dispatch_persistent_message", return_value=(True, "777", None, "SENT")) as mock_send, \
         patch.object(svc, "_fanout_plan_signal", return_value=(0, 0)), \
         patch("taikry.data.validator.check_data_freshness", return_value={"fresh": True, "status": "LIVE_FRESH"}):
        # 1. Setup with low score (75%) -> Must be suppressed
        low_score_setup = {
            "symbol": "BTCUSDT",
            "market_bias": "BULLISH",
            "setup_status": "MONITOR",
            "ai_score": 75,
            "confidence_score": 75,
            "proposed_direction": "BUY",
            "entry_price": 80000.0,
            "stop_loss": 79000.0,
            "take_profit_1": 82000.0,
            "take_profit_2": 84000.0
        }
        sent = svc.send_bilingual_report(low_score_setup, force=False)
        assert sent is False, "Setups with score < 80% must not be sent to Telegram"
        mock_send.assert_not_called()

        # 2. A complete, fresh non-XAU setup uses the persistent dispatcher.
        high_score_setup = {
            "symbol": "EURUSD",
            "market_bias": "BULLISH",
            "setup_status": "APPROVE",
            "ai_score": 88,
            "confidence_score": 88,
            "proposed_direction": "BUY",
            "entry_price": 1.10000,
            "stop_loss": 1.09500,
            "take_profit_1": 1.11000,
            "take_profit_2": 1.11500,
            "risk_reward_ratio": "1:2.0",
            "price_source": "OANDA_V20",
            "timestamp_utc": "2026-10-31T00:00:00+00:00",
            "timeframe": "M15",
        }
        sent2 = svc.send_bilingual_report(high_score_setup, force=True)
        assert sent2 is True, "Legacy force=True must not bypass validation but valid setups still dispatch"
        assert mock_send.called
        call_text = mock_send.call_args.args[0]
        assert "AI SCORE:</b> 88%" in call_text
        assert "ACTION:</b> BUY" in call_text
        assert "<code>1.1000</code>" in call_text
        assert "<code>1.0950</code>" in call_text
        assert "<code>1.1100</code>" in call_text

        # 3. A forced incomplete setup and XAUUSD generic dispatch are still rejected.
        assert svc.send_bilingual_report({"symbol": "EURUSD", "setup_status": "WAIT"}, force=True) is False
        gold = dict(high_score_setup, symbol="XAUUSD")
        assert svc.send_bilingual_report(gold, force=True) is False

def test_market_monitor_dispatches_only_single_best_setup():
    """Verifies MarketMonitor247 scans universe and dispatches ONLY the #1 highest scoring setup in 80%-95%."""
    monitor = MarketMonitor247()

    mock_analysis_gold = {
        "symbol": "XAUUSD",
        "verified_price": 2745.0,
        "price_source": "MT5",
        "data_quality": {"synthetic_timeframes": [], "freshness": {"fresh": True}},
        "setup_status": "APPROVE",
        "proposed_direction": "BUY",
        "ai_score": 92,
        "entry_price": 2745.0,
        "stop_loss": 2735.0,
        "take_profit_1": 2770.0,
        "take_profit_2": 2790.0,
        "risk_reward_ratio": "1:2.5"
    }

    mock_analysis_eur = {
        "symbol": "EURUSD",
        "verified_price": 1.0850,
        "price_source": "YAHOO_FINANCE",
        "data_quality": {"synthetic_timeframes": [], "freshness": {"fresh": True}},
        "setup_status": "APPROVE",
        "proposed_direction": "BUY",
        "ai_score": 83,
        "entry_price": 1.0850,
        "stop_loss": 1.0820,
        "take_profit_1": 1.0920,
        "take_profit_2": 1.0960,
        "risk_reward_ratio": "1:2.3"
    }

    mock_analysis_btc = {
        "symbol": "BTCUSDT",
        "verified_price": 80000.0,
        "setup_status": "REJECT",
        "proposed_direction": "HOLD",
        "ai_score": 65,  # Rejected sub-80%
        "entry_price": 80000.0
    }

    def fake_analyze(sym, **kwargs):
        if sym == "XAUUSD": return mock_analysis_gold
        if sym == "EURUSD": return mock_analysis_eur
        return mock_analysis_btc

    fake_consensus_adapter = MagicMock()
    fake_consensus_adapter.execute.side_effect = lambda **kwargs: fake_analyze(kwargs["symbol"])
    with patch("taikry.monitoring.engine.is_market_open", return_value=(True, "Open")), \
         patch("taikry.monitoring.engine.agent_registry.get_adapter", return_value=fake_consensus_adapter), \
         patch.object(monitor, "_handle_approved_setup") as mock_handle:

        monitor.scan_once(symbols=["XAUUSD", "EURUSD", "BTCUSDT"])

        # Must be called EXACTLY ONCE for the single BEST setup (Gold with 92% > EUR with 83%)
        assert mock_handle.call_count == 1, "Only the single best setup must be dispatched"
        called_setup = mock_handle.call_args[0][0]
        assert called_setup["symbol"] == "XAUUSD"
        assert called_setup["ai_score"] == 92
        assert fake_consensus_adapter.execute.call_count == 3

def test_broadcast_alert_api_endpoint():
    """Tests POST /api/v1/telegram/broadcast-alert returns ai_score in 80%-95% range."""
    with patch("taikry.notifications.telegram_service.TelegramService._fanout_plan_signal", return_value=(0, 0)):
        resp = client.post("/api/v1/telegram/broadcast-alert", json={"symbol": "BEST"})
    assert resp.status_code == 200
    data = resp.json()
    assert "ai_score" in data
    assert 80 <= data["ai_score"] <= 95
    assert data["action"] in ["BUY ENTRY", "SELL ENTRY"]
    assert "target_chat_id" in data
