import time

from taikry.agents import consensus_engine
from taikry.api import routes
from taikry.agents.consensus_engine import _build_candidate_plan


def _risk_report(**overrides):
    report = {
        "proposed_direction": "LONG",
        "entry_price": 100.0,
        "stop_loss": 95.0,
        "take_profit_1": 110.0,
        "take_profit_2": 115.0,
        "reasons": ["Verified bid/ask spread is unavailable; execution cost cannot be checked."],
    }
    report.update(overrides)
    return report


def _data_quality(**overrides):
    quality = {
        "is_fresh": True,
        "feed_status": "HEALTHY",
        "bid_price": None,
        "ask_price": None,
        "reference_source": "YAHOO_FALLBACK",
    }
    quality.update(overrides)
    return quality


def test_waiting_plan_is_exposed_as_non_executable_analysis_only():
    plan = _build_candidate_plan(
        risk_report=_risk_report(),
        setup_status="REJECT",
        consensus_direction="BUY",
        directional_share=0.72,
        material_conflict=False,
        data_quality=_data_quality(),
        price_source="YAHOO_FALLBACK",
    )

    assert plan is not None
    assert plan["status"] == "ANALYSIS_ONLY"
    assert plan["can_execute"] is False
    assert plan["direction"] == "LONG"
    assert plan["entry_basis"] == "REFERENCE_PRICE_NO_BID_ASK"
    assert plan["risk_reward_ratio"] == "1:2.00"


def test_candidate_plan_is_hidden_without_fresh_unconflicted_consensus():
    assert _build_candidate_plan(
        risk_report=_risk_report(),
        setup_status="WAIT",
        consensus_direction="SELL",
        directional_share=0.72,
        material_conflict=False,
        data_quality=_data_quality(),
        price_source="YAHOO_FALLBACK",
    ) is None
    assert _build_candidate_plan(
        risk_report=_risk_report(),
        setup_status="WAIT",
        consensus_direction="BUY",
        directional_share=0.72,
        material_conflict=False,
        data_quality=_data_quality(is_fresh=False),
        price_source="YAHOO_FALLBACK",
    ) is None


def test_candidate_plan_rejects_invalid_level_geometry():
    plan = _build_candidate_plan(
        risk_report=_risk_report(stop_loss=105.0),
        setup_status="WAIT",
        consensus_direction="BUY",
        directional_share=0.72,
        material_conflict=False,
        data_quality=_data_quality(),
        price_source="YAHOO_FALLBACK",
    )
    assert plan is None


def test_best_setup_endpoint_preserves_analysis_only_levels(monkeypatch):
    candidate = _build_candidate_plan(
        risk_report=_risk_report(),
        setup_status="REJECT",
        consensus_direction="BUY",
        directional_share=0.72,
        material_conflict=False,
        data_quality=_data_quality(),
        price_source="YAHOO_FALLBACK",
    )
    analysis = {
        "symbol": "EURUSD",
        "setup_status": "REJECT",
        "ai_score": 75,
        "market_bias": "BULLISH",
        "proposed_direction": "NONE",
        "verified_price": 1.1,
        "price_source": "YAHOO_FALLBACK",
        "candidate_plan": candidate,
        "smart_analysis": {"risk_causes": candidate["reasons"]},
    }
    monkeypatch.setattr("taikry.config.WATCHLIST", [{"symbol": "EURUSD", "category": "Forex"}])
    monkeypatch.setattr(consensus_engine, "_ANALYSIS_CACHE", {"EURUSD:quant": (time.time(), analysis)})

    result = routes.get_best_market_setup("FOREX")

    assert result["best_setup"]["candidate_plan"] == candidate
    assert result["best_setup"]["entry_price"] is None
    assert result["best_setup"]["stop_loss"] is None
