import pytest
from unittest.mock import patch, MagicMock

from taikry.monitoring.engine import MarketMonitor247
from taikry.notifications.telegram_service import TelegramService
from taikry.agents.consensus_engine import AIConsensusEngine
from fastapi.testclient import TestClient
from taikry.api.app import app

client = TestClient(app)

def test_telegram_bilingual_report_score_threshold_enforced():
    """Verifies Telegram alert strictly suppresses setups with score < 80% and allows 80%-95%."""
    svc = TelegramService()

    with patch.object(svc, "send_message", return_value=True) as mock_send:
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

        # 2. Setup with high score in 80%-95% range (88%) -> Must be sent
        high_score_setup = {
            "symbol": "XAUUSD",
            "market_bias": "BULLISH",
            "setup_status": "APPROVE",
            "ai_score": 88,
            "confidence_score": 88,
            "proposed_direction": "BUY",
            "entry_price": 2740.50,
            "stop_loss": 2730.00,
            "take_profit_1": 2765.00,
            "take_profit_2": 2785.00,
            "risk_reward_ratio": "1:2.4"
        }
        sent2 = svc.send_bilingual_report(high_score_setup, force=False)
        assert sent2 is True, "High conviction setups with score 80%-95% must be dispatched to Telegram"
        assert mock_send.called
        call_text = mock_send.call_args[0][0]
        assert "⭐ <b>AI CONFLUENCE SCORE:</b> <b>88%</b>" in call_text
        assert "🎯 <b>ACTION:</b> <b>🟢 BUY ENTRY</b>" in call_text
        assert "💵 <b>BUY ENTRY:</b> <code>2740.5</code>" in call_text
        assert "🛑 <b>STOP LOSS (SL):</b> <code>2730.0</code>" in call_text
        assert "🎯 <b>TAKE PROFIT 1 (TP 1):</b> <code>2765.0</code>" in call_text
        assert "🚀 <b>TAKE PROFIT 2 (TP 2):</b> <code>2785.0</code>" in call_text
        assert "⚖️ <b>RISK / REWARD:</b> 1:2.4" in call_text
        assert "🛡️ <b>RISK GUARD:</b> 0.5% Institutional Cap" in call_text

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
    resp = client.post("/api/v1/telegram/broadcast-alert", json={"symbol": "BEST"})
    assert resp.status_code == 200
    data = resp.json()
    assert "ai_score" in data
    assert 80 <= data["ai_score"] <= 95
    assert data["action"] in ["BUY ENTRY", "SELL ENTRY"]
    assert "target_chat_id" in data
