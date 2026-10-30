import datetime
from unittest.mock import Mock

import pytest

from taikry.agents import consensus_engine
from taikry.ai import llm_client


def test_chat_timeframes_are_normalized_for_dashboard_values():
    assert llm_client._normalize_chat_timeframe("15") == "M15"
    assert llm_client._normalize_chat_timeframe("60") == "H1"
    assert llm_client._normalize_chat_timeframe("4h") == "H4"
    assert llm_client._normalize_chat_timeframe("D") == "D1"


def test_chat_runs_quant_scan_when_consensus_cache_is_missing(monkeypatch):
    cache = {}
    monkeypatch.setattr(consensus_engine, "_ANALYSIS_CACHE", cache)
    calls = []

    def analyze_symbol(**kwargs):
        calls.append(kwargs)
        return {"setup_status": "NO TRADE"}

    monkeypatch.setattr(consensus_engine.ai_consensus_engine, "analyze_symbol", analyze_symbol)

    result, cached, style = llm_client._get_chat_consensus("EURUSD", "15", "check market")

    assert result["setup_status"] == "NO TRADE"
    assert cached is False
    assert style == "INTRADAY"
    assert calls == [{
        "symbol": "EURUSD",
        "preferred_llm": "quant",
        "force_refresh": True,
        "trade_style": "INTRADAY",
    }]


def test_chat_reuses_only_a_recent_quant_scan(monkeypatch):
    cached_result = {"setup_status": "NO TRADE", "timestamp_utc": "current"}
    cache = {"EURUSD:quant": (llm_client.time.time() - 3, cached_result)}
    monkeypatch.setattr(consensus_engine, "_ANALYSIS_CACHE", cache)
    monkeypatch.setattr(
        consensus_engine.ai_consensus_engine,
        "analyze_symbol",
        lambda **_kwargs: pytest.fail("A recent scan should be reused"),
    )

    result, cached, _ = llm_client._get_chat_consensus("EURUSD", "15", "check market")

    assert cached is True
    assert result == cached_result


def test_chat_uses_swing_consensus_for_swing_question(monkeypatch):
    monkeypatch.setattr(consensus_engine, "_ANALYSIS_CACHE", {})
    calls = []
    monkeypatch.setattr(
        consensus_engine.ai_consensus_engine,
        "analyze_symbol",
        lambda **kwargs: calls.append(kwargs) or {"setup_status": "NO TRADE"},
    )

    _, _, style = llm_client._get_chat_consensus("XAUUSD", "15", "build a swing plan")

    assert style == "SWING"
    assert calls[0]["trade_style"] == "SWING"


def test_unavailable_cloud_provider_is_reported_as_degraded(monkeypatch):
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    monkeypatch.setattr(
        llm_client,
        "_get_chat_consensus",
        lambda *_args: ({
            "timestamp_utc": now_utc.isoformat(),
            "setup_timeframe": "M15",
            "setup_status": "NO TRADE",
            "data_quality": {"freshness": {"fresh": True}},
        }, False, "INTRADAY"),
    )
    monkeypatch.setattr(llm_client, "_get_chat_research", lambda *_args: (None, "REFRESHING"))
    monkeypatch.setattr(llm_client, "FREELLMAPI_ENABLED", False)
    for key in ("GROQ_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.setattr(llm_client, key, None)

    from taikry.data import providers, validator

    monkeypatch.setattr(
        providers.market_data_engine,
        "get_verified_price",
        lambda _symbol: (2000.0, "OANDA_V20", now_utc),
    )
    monkeypatch.setattr(
        validator,
        "check_data_freshness",
        lambda *_args: {"fresh": True, "status": "LIVE_FRESH", "age_minutes": 0.0},
    )

    result = llm_client.chat_with_real_ai("what is the current market bias?", "XAUUSD", "15", "auto")

    assert result["status"] == "DEGRADED"
    assert result["ai_status"] == "UNAVAILABLE"
    assert result["market_context"]["price_source"] == "OANDA_V20"
    assert result["consensus_context"]["status"] == "LIVE_FRESH"
    assert result["trade_execution"]["action"] == "HOLD"


@pytest.mark.parametrize("scan_age_seconds, expected_action", [(2, "BUY"), (20, "HOLD")])
def test_chat_only_shows_trade_levels_from_a_fresh_approved_scan(monkeypatch, scan_age_seconds, expected_action):
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    scan_time = now_utc - datetime.timedelta(seconds=scan_age_seconds)
    scan = {
        "timestamp_utc": scan_time.isoformat(),
        "setup_timeframe": "M15",
        "setup_status": "APPROVE",
        "proposed_direction": "BUY",
        "market_bias": "BULLISH",
        "confidence_score": 88,
        "entry_price": 2001.0,
        "stop_loss": 1990.0,
        "take_profit_1": 2025.0,
        "take_profit_2": 2050.0,
        "risk_reward_ratio": "1:2.1",
        "price_source": "OANDA_V20",
        "data_quality": {"freshness": {"fresh": True}},
    }
    monkeypatch.setattr(llm_client, "_get_chat_consensus", lambda *_args: (scan, False, "INTRADAY"))
    monkeypatch.setattr(llm_client, "_get_chat_research", lambda *_args: (None, "REFRESHING"))
    monkeypatch.setattr(llm_client, "FREELLMAPI_ENABLED", False)
    monkeypatch.setattr(llm_client, "GROQ_API_KEY", None)
    monkeypatch.setattr(llm_client, "GEMINI_API_KEY", None)
    monkeypatch.setattr(llm_client, "OPENROUTER_API_KEY", "configured-but-not-selected")
    mock_post = Mock()
    monkeypatch.setattr(llm_client.requests, "post", mock_post)

    from taikry.data import providers, validator

    monkeypatch.setattr(
        providers.market_data_engine,
        "get_verified_price",
        lambda _symbol: (2000.0, "OANDA_V20", now_utc),
    )
    monkeypatch.setattr(
        validator,
        "check_data_freshness",
        lambda *_args: {"fresh": True, "status": "LIVE_FRESH", "age_minutes": 0.0},
    )

    result = llm_client.chat_with_real_ai("show the current setup", "XAUUSD", "15", "groq")

    assert result["trade_execution"]["action"] == expected_action
    if expected_action == "BUY":
        assert result["trade_execution"]["entry_price"] == 2001.0
        assert result["trade_execution"]["stop_loss"] == 1990.0
        assert result["trade_execution"]["take_profit_1"] == 2025.0
    else:
        assert result["trade_execution"]["entry_price"] is None
    mock_post.assert_not_called()


def test_chat_api_forwards_recent_conversation_history(monkeypatch):
    from taikry.api.routes import ChatAIRequest, chat_ai_endpoint

    captured = {}

    def fake_chat(**kwargs):
        captured.update(kwargs)
        return {"status": "SUCCESS", "ai_status": "SUCCESS"}

    monkeypatch.setattr(llm_client, "chat_with_real_ai", fake_chat)
    request = ChatAIRequest(**{
        "query": "and what about the stop?",
        "symbol": "XAUUSD",
        "timeframe": "15",
        "provider": "auto",
        "history": [
            {"role": "user", "content": "show a swing setup"},
            {"role": "assistant", "content": "No fresh approved setup yet."},
        ],
    })
    response = chat_ai_endpoint(request, authorization=None, zyrox_session=None)

    assert response["status"] == "SUCCESS"
    assert captured["history"][0]["content"] == "show a swing setup"
    assert captured["history"][1]["role"] == "assistant"
