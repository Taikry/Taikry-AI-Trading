import datetime
from types import SimpleNamespace

import pandas as pd
import pytest

from taikry.agents import consensus_engine as consensus_module
from taikry.agents.consensus_engine import AIConsensusEngine
from taikry.agents.registry import agent_registry
from taikry.learning.self_trainer import agent_self_trainer


class StubAdapter:
    def __init__(self, agent_id, result):
        self.metadata = SimpleNamespace(agent_id=agent_id)
        self.result = result
        self.calls = []

    def execute(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return dict(self.result)


@pytest.mark.parametrize("trade_style,setup_timeframe", [("INTRADAY", "M15"), ("SWING", "H4")])
def test_consensus_engine_runs_full_signal_fleet_on_one_snapshot(monkeypatch, trade_style, setup_timeframe):
    now = datetime.datetime.now(datetime.timezone.utc)
    frame = pd.DataFrame({
        "timestamp": [now - datetime.timedelta(minutes=15 * i) for i in range(30)],
        "open": [2698.0] * 30,
        "high": [2701.0] * 30,
        "low": [2697.0] * 30,
        "close": [2700.0] * 30,
        "volume": [100.0] * 30,
    })
    snapshot = {tf: frame for tf in ("W1", "D1", "H4", "H1", "M15", "M5")}
    monkeypatch.setattr(consensus_module.market_data_engine, "get_multi_timeframe_candles", lambda *_args: snapshot)
    monkeypatch.setattr(consensus_module.market_data_engine, "get_verified_price", lambda _symbol: (2700.0, "MOCK_BROKER", now))
    monkeypatch.setattr(consensus_module, "validate_dataframe", lambda *_args, **_kwargs: {"valid": True, "reason": None})
    monkeypatch.setattr(consensus_module, "check_data_freshness", lambda *_args, **_kwargs: {"fresh": True, "age_seconds": 30})
    monkeypatch.setattr(agent_self_trainer, "get_current_agent_weights", lambda _symbol: {})
    monkeypatch.setattr(consensus_module, "translate_to_khmer", lambda _report: "Khmer preview report")
    monkeypatch.setattr(consensus_module, "get_llm_status", lambda: {"status": "NOT_PROBED"})

    reports = {
        "data_quality_agent": {"feed_status": "HEALTHY", "is_fresh": True, "spread_points": 0.25, "bid_price": 2699.9, "ask_price": 2700.1},
        "technical_analyst": {"bias": "BULLISH", "confidence": 90, "key_price_levels": {"atr": 2.0}, "evidence": []},
        "ict_smc_analyst": {"bias": "BULLISH", "confidence": 90, "key_price_zones": {}, "evidence": []},
        "macro_analyst": {"bias": "BULLISH", "confidence": 90, "evidence": [], "high_impact_events": []},
        "orderflow_sentiment_analyst": {"bias": "BULLISH", "confidence": 90, "evidence": []},
        "fractal_mtf_analyst": {"overall_direction": "BUY", "confidence": 90, "trap_detected": False, "evidence": []},
        "regime_detection_agent": {"regime": "TRENDING_BULLISH", "volatility_state": "NORMAL_LIQUIDITY", "evidence": []},
        "quantitative_research_agent": {"bias": "LONG", "mean_reversion_probability": 90, "evidence": []},
        "ml_forecast_agent": {"predicted_direction": "BULLISH", "confidence": 90, "evidence": []},
        "concept_recommender": {"status": "CONCEPT_QUALIFIED", "top_concept": {"concept_id": "test"}, "evidence": []},
        "risk_validator": {
            "decision": "APPROVE", "proposed_direction": "LONG", "entry_price": 2700.0,
            "stop_loss": 2690.0, "take_profit_1": 2722.0, "take_profit_2": 2735.0,
            "calculated_rr": "1:2.2", "reasons": [],
        },
        "counter_analysis_agent": {"critique_stance": "CHALLENGE_CLEARED", "fragility_score": 20},
        "portfolio_analysis_agent": {"is_approved": True, "projected_risk_pct": 0.5},
        "execution_simulation_agent": {"is_execution_viable": True, "net_risk_reward": 2.0},
    }
    adapters = {agent_id: StubAdapter(agent_id, result) for agent_id, result in reports.items()}
    monkeypatch.setattr(agent_registry, "get_adapter", lambda agent_id: adapters.get(agent_id))

    result = AIConsensusEngine().analyze_symbol("XAUUSD", preferred_llm="quant", force_refresh=True, trade_style=trade_style)

    assert result["setup_status"] == "APPROVE"
    assert result["proposed_direction"] == "LONG"
    assert result["ai_score"] == 89
    assert result["agent_fleet_count"] == 17
    assert result["agent_run_summary"]["voting_agents"] == 8
    assert result["agent_run_summary"]["voting_agents_participated"] == 8
    assert result["agent_run_summary"]["agent_statuses"]["debate_engine"] == "DEFERRED"
    assert result["agent_run_summary"]["agent_statuses"]["self_trainer"] == "DEFERRED"
    assert result["agents"]["data_quality_agent"]["execution_status"] == "SUCCESS"
    assert result["agents"]["execution_simulation_agent"]["execution_status"] == "SUCCESS"
    assert adapters["data_quality_agent"].calls[0][1]["market_snapshot"]["multi_tf_data"] is snapshot
    assert adapters["orderflow_sentiment_analyst"].calls[0][1]["df_m15"] is frame
    assert adapters["concept_recommender"].calls[0][1]["regime_data"]["regime"] == "TRENDING_BULLISH"
    risk_kwargs = adapters["risk_validator"].calls[0][1]
    assert risk_kwargs["spread_price"] == pytest.approx(0.2)
    assert risk_kwargs["bid_price"] == 2699.9
    assert risk_kwargs["ask_price"] == 2700.1
    assert adapters["data_quality_agent"].calls[0][1]["timeframe"] == setup_timeframe
    if trade_style == "SWING":
        assert adapters["technical_analyst"].calls[0][1]["setup_timeframe"] == "H4"
        assert adapters["ict_smc_analyst"].calls[0][1]["setup_timeframe"] == "H4"
        assert result["setup_timeframe"] == "H4"
