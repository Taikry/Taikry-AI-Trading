from types import SimpleNamespace

from taikry.trading.xauusd_signal_engine import SIGNAL_VOTER_IDS, xauusd_signal_engine
from taikry.agents.registry import agent_registry
from taikry.agents.portfolio_analysis_agent import portfolio_analysis_agent


class FakeModelOutput:
    def __init__(self, **values):
        self.values = values

    def model_dump(self):
        return dict(self.values)


class FakeAdapter:
    def __init__(self, agent_id, output=None):
        self.metadata = SimpleNamespace(
            agent_id=agent_id,
            name=agent_id,
            specialization="test",
            model_provider="test",
            model_identifier="test",
        )
        self.output = output or {}
        self.calls = []

    def execute(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.output


def _voter_outputs():
    outputs = {
        "technical_analyst": {"bias": "BULLISH", "confidence": 90, "key_levels": {"atr": 2.0}, "evidence": []},
        "ict_smc_analyst": {"bias": "BULLISH", "confidence": 90, "evidence": []},
        "macro_analyst": {"bias": "BULLISH", "confidence": 90, "evidence": []},
        "orderflow_sentiment_analyst": {"bias": "BULLISH", "confidence": 90, "evidence": []},
        "fractal_mtf_analyst": {"overall_direction": "BUY", "bias": "BULLISH", "confidence": 90, "evidence": []},
        "regime_detection_agent": {"regime": "TRENDING_BULLISH", "bias": "BULLISH", "confidence": 65, "volatility_state": "NORMAL_LIQUIDITY", "evidence": []},
        "quantitative_research_agent": {"bias": "BULLISH", "confidence": 90, "mean_reversion_probability": 90, "evidence": []},
        "ml_forecast_agent": {"predicted_direction": "BULLISH", "bias": "BULLISH", "confidence": 90, "evidence": []},
    }
    return {
        agent_id: {
            **report,
            "agent_id": agent_id,
            "status": "SUCCESS",
            "contributes_to_consensus": True,
        }
        for agent_id, report in outputs.items()
    }


def test_xau_scan_routes_agent_signatures_and_tracks_fallback(monkeypatch):
    ids = [
        "data_quality_agent", "technical_analyst", "ict_smc_analyst", "macro_analyst",
        "risk_validator", "consensus_engine", "debate_engine", "self_trainer",
        "orderflow_sentiment_analyst", "fractal_mtf_analyst", "regime_detection_agent",
        "quantitative_research_agent", "ml_forecast_agent", "concept_recommender",
        "counter_analysis_agent", "portfolio_analysis_agent", "execution_simulation_agent",
    ]
    reports = {
        "data_quality_agent": {"feed_status": "HEALTHY", "is_fresh": True, "evidence": []},
        "technical_analyst": {"bias": "BULLISH", "confidence": 80, "key_price_levels": {"atr": 2.0}},
        "ict_smc_analyst": {"bias": "BULLISH", "confidence": 80},
        "macro_analyst": {"bias": "NEUTRAL", "confidence": 50},
        "orderflow_sentiment_analyst": FakeModelOutput(bias="BULLISH", confidence=70, evidence=[]),
        "fractal_mtf_analyst": FakeModelOutput(overall_direction="BUY", confidence=75, evidence=[]),
        "regime_detection_agent": {"regime": "TRENDING_BULLISH", "volatility_state": "NORMAL_LIQUIDITY"},
        "quantitative_research_agent": {"bias": "LONG", "mean_reversion_probability": 75},
        "ml_forecast_agent": {"bias": "BULLISH", "confidence": 80, "_fallback_applied": True, "_fallback_reason": "test fallback"},
        "concept_recommender": {"status": "NO_QUALIFIED_CONCEPT", "evidence": []},
    }
    adapters = [FakeAdapter(agent_id, reports.get(agent_id, {})) for agent_id in ids]
    monkeypatch.setattr(xauusd_signal_engine, "discover_eligible_agents", lambda: adapters)

    m15 = object()
    results = xauusd_signal_engine.execute_all_agents("XAUUSD", {"M15": m15}, 2700.0)

    by_id = {adapter.metadata.agent_id: adapter for adapter in adapters}
    quality_call = by_id["data_quality_agent"].calls[0][1]
    assert quality_call["symbol"] == "XAUUSD"
    assert quality_call["timeframe"] == "M15"
    assert quality_call["market_snapshot"]["multi_tf_data"]["M15"] is m15
    assert quality_call["market_snapshot"]["verified_price"] == 2700.0
    assert by_id["technical_analyst"].calls[0][1]["multi_tf_data"]["M15"] is m15
    assert by_id["orderflow_sentiment_analyst"].calls[0][1] == {
        "symbol": "XAUUSD", "df_m15": m15, "verified_price": 2700.0
    }
    assert by_id["concept_recommender"].calls[0][1]["regime_data"]["regime"] == "TRENDING_BULLISH"
    assert results["fractal_mtf_analyst"]["bias"] == "BULLISH"
    assert results["quantitative_research_agent"]["bias"] == "BULLISH"
    assert results["ml_forecast_agent"]["status"] == "FALLBACK"
    assert results["ml_forecast_agent"]["contributes_to_consensus"] is False
    assert results["risk_validator"]["status"] == "PENDING_CANDIDATE"
    assert results["self_trainer"]["status"] == "DEFERRED"
    assert results["consensus_engine"]["status"] == "DEFERRED"
    assert set(SIGNAL_VOTER_IDS) <= set(results)


def test_consensus_runs_candidate_specialists_and_enforces_hard_gates(monkeypatch):
    eligible = [FakeAdapter(agent_id) for agent_id in SIGNAL_VOTER_IDS]
    monkeypatch.setattr(xauusd_signal_engine, "discover_eligible_agents", lambda: eligible)
    monkeypatch.setattr(xauusd_signal_engine, "_load_agent_weights", lambda: {})

    risk = FakeAdapter("risk_validator", {"decision": "APPROVE", "reasons": []})
    counter = FakeAdapter("counter_analysis_agent", {"critique_stance": "CHALLENGE_CLEARED", "fragility_score": 20})
    portfolio = FakeAdapter("portfolio_analysis_agent", {"is_approved": True, "projected_risk_pct": 1.0})
    execution = FakeAdapter("execution_simulation_agent", {"is_execution_viable": True, "net_risk_reward": 2.0})
    adapters = {a.metadata.agent_id: a for a in (risk, counter, portfolio, execution)}
    monkeypatch.setattr(agent_registry, "get_adapter", lambda agent_id: adapters.get(agent_id))

    consensus = xauusd_signal_engine.synthesize_consensus(
        "XAUUSD", 2700.0, _voter_outputs(), {},
        price_timestamp=None, spread_price=0.25,
    )

    assert consensus["decision"] == "BUY"
    assert consensus["eligible_count"] == len(SIGNAL_VOTER_IDS)
    assert consensus["participating_count"] == len(SIGNAL_VOTER_IDS)
    assert consensus["agent_opinions"]["counter_analysis_agent"]["status"] == "SUCCESS"
    assert consensus["agent_opinions"]["portfolio_analysis_agent"]["status"] == "SUCCESS"
    assert consensus["agent_opinions"]["execution_simulation_agent"]["status"] == "SUCCESS"
    assert counter.calls[0][1]["technical_report"]["bias"] == "BULLISH"
    assert execution.calls[0][1]["current_spread_points"] == 0.25

    portfolio.output = {"is_approved": False}
    blocked = xauusd_signal_engine.synthesize_consensus(
        "XAUUSD", 2700.0, _voter_outputs(), {}, spread_price=0.25,
    )
    assert blocked["decision"] == "NO TRADE"
    assert "Portfolio exposure" in blocked["rejection_reason"]


def test_stale_data_quality_report_blocks_signal(monkeypatch):
    eligible = [FakeAdapter(agent_id) for agent_id in SIGNAL_VOTER_IDS]
    monkeypatch.setattr(xauusd_signal_engine, "discover_eligible_agents", lambda: eligible)
    reports = _voter_outputs()
    reports["data_quality_agent"] = {
        "status": "SUCCESS", "feed_status": "STALE", "is_fresh": False,
    }

    result = xauusd_signal_engine.synthesize_consensus("XAUUSD", 2700.0, reports, {})

    assert result["decision"] == "NO TRADE"
    assert "data quality" in result["rejection_reason"].lower()


def test_portfolio_database_error_fails_closed(monkeypatch):
    class BrokenSession:
        def query(self, *_args, **_kwargs):
            raise RuntimeError("database unavailable")

        def close(self):
            pass

    monkeypatch.setattr("taikry.agents.portfolio_analysis_agent.SessionLocal", BrokenSession)

    result = portfolio_analysis_agent.evaluate_portfolio("XAUUSD")

    assert result["is_approved"] is False
    assert result["portfolio_status"] == "UNAVAILABLE_LOCKOUT"
