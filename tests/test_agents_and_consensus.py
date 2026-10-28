"""
Unit and Integration tests for Milestone 3: Four AI Agents and Consensus Engine
"""
import pytest
from taikry.agents.technical_analyst import technical_analyst_agent
from taikry.agents.ict_smc_analyst import ict_smc_analyst_agent
from taikry.agents.macro_analyst import macro_analyst_agent
from taikry.agents.risk_validator import risk_validator_agent
from taikry.agents.consensus_engine import ai_consensus_engine

def test_risk_validator_rejects_insufficient_rr():
    """Risk validator MUST reject setups with R:R < 1:2.0."""
    fake_a1 = {
        "bias": "BULLISH",
        "key_price_levels": {
            "suggested_stop_loss": 2000.0, # Entry 2010 -> Risk = 10
            "take_profit_1": 2015.0        # Reward = 5 -> R:R is 1:0.5 (Fails 1:2.0 rule)
        }
    }
    fake_a2 = {"bias": "BULLISH", "key_price_zones": {}}
    fake_a3 = {"bias": "NEUTRAL"}

    import datetime
    res = risk_validator_agent.validate(
        symbol="XAUUSD",
        verified_price=2010.0,
        price_timestamp=datetime.datetime.now(datetime.timezone.utc),
        agent1_report=fake_a1,
        agent2_report=fake_a2,
        agent3_report=fake_a3
    )
    assert res["decision"] == "REJECT"
    assert any("Insufficient Risk-to-Reward" in r for r in res["reasons"])

def test_risk_validator_approves_valid_setup(monkeypatch):
    """Risk validator approves setups with valid R:R >= 1:2.0 and risk sizing."""
    from taikry.data.economic_calendar import economic_calendar_provider
    monkeypatch.setattr(economic_calendar_provider, "check_news_blackout", lambda sym: {"is_blackout": False, "advisory_en": None, "advisory_kh": None})

    fake_a1 = {
        "bias": "BULLISH",
        "key_price_levels": {
            "suggested_stop_loss": 2000.0, # Entry 2010 -> Risk = 10
            "take_profit_1": 2032.0,       # Reward = 22 -> R:R is 1:2.2 (Passes)
            "take_profit_2": 2045.0
        }
    }
    fake_a2 = {"bias": "BULLISH", "key_price_zones": {}}
    fake_a3 = {"bias": "BULLISH"}

    import datetime
    res = risk_validator_agent.validate(
        symbol="XAUUSD",
        verified_price=2010.0,
        price_timestamp=datetime.datetime.now(datetime.timezone.utc),
        agent1_report=fake_a1,
        agent2_report=fake_a2,
        agent3_report=fake_a3
    )
    assert res["decision"] == "APPROVE"
    assert "1:2.2" in res["calculated_rr"]
    assert res["position_sizing"]["risk_percent"] == 0.5

def test_macro_analyst_returns_verified_dxy():
    res = macro_analyst_agent.analyze("XAUUSD")
    assert "usd_index" in res
    assert "high_impact_events" in res
    assert res["bias"] in ["BULLISH", "BEARISH", "NEUTRAL"]

def test_full_consensus_engine_gold():
    """End-to-end integration test on real XAUUSD market data."""
    result = ai_consensus_engine.analyze_symbol("XAUUSD")
    assert result["symbol"] == "XAUUSD"
    assert result["verified_price"] > 0
    assert result["market_bias"] in [
        "STRONG BULLISH", "BULLISH", "NEUTRAL", "BEARISH",
        "STRONG BEARISH", "WAIT FOR CONFIRMATION", "NO TRADE"
    ]
    assert result["setup_status"] in ["APPROVE", "REJECT", "WAIT", "NO TRADE"]
    assert "report_english" in result
    assert "TAIKRY AI MARKET INTELLIGENCE PRO" in result["report_english"]
    assert "report_khmer" in result
    assert "TAIKRY AI MARKET INTELLIGENCE PRO" in result["report_khmer"]
