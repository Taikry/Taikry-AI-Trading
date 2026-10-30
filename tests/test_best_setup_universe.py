import time

from taikry.agents import consensus_engine
from taikry.api import routes


def _analysis(symbol, status, score, direction="NONE"):
    return {
        "symbol": symbol,
        "setup_status": status,
        "ai_score": score,
        "confidence_score": score,
        "market_bias": "BEARISH",
        "proposed_direction": direction,
        "verified_price": 100.0,
        "price_source": "TEST_FEED",
        "entry_price": 100.0 if status == "APPROVE" else None,
        "stop_loss": 98.0 if status == "APPROVE" else None,
        "take_profit_1": 104.0 if status == "APPROVE" else None,
        "risk_reward_ratio": "1:2.00",
        "smart_analysis": {"risk_causes": ["test risk note"]},
        "agents": {},
        "timestamp_utc": "2026-10-30T00:00:00+00:00",
    }


def test_best_setup_returns_ranked_results_for_entire_selected_universe(monkeypatch):
    universe = [
        {"symbol": "XAUUSD", "category": "Commodities"},
        {"symbol": "BTCUSDT", "category": "Crypto"},
        {"symbol": "EURUSD", "category": "Forex"},
    ]
    cache = {
        "XAUUSD:quant": (time.time(), _analysis("XAUUSD", "REJECT", 92)),
        "BTCUSDT:quant": (time.time(), _analysis("BTCUSDT", "APPROVE", 84, "SHORT")),
        "EURUSD:quant": (time.time(), _analysis("EURUSD", "APPROVE", 89, "LONG")),
    }
    monkeypatch.setattr("taikry.config.WATCHLIST", universe)
    monkeypatch.setattr(consensus_engine, "_ANALYSIS_CACHE", cache)
    monkeypatch.setattr(
        routes.ai_consensus_engine,
        "analyze_symbol",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("fresh results should be reused")),
    )

    result = routes.get_best_market_setup("ALL")

    assert result["candidate_count"] == 3
    assert result["scanned_count"] == 3
    assert result["qualified_count"] == 2
    assert [item["symbol"] for item in result["setups"]] == ["EURUSD", "BTCUSDT", "XAUUSD"]
    assert result["best_setup"]["symbol"] == "EURUSD"
    assert result["setups"][0]["reason_summary"] == "test risk note"


def test_best_setup_refreshes_every_stale_symbol_in_filtered_market(monkeypatch):
    universe = [
        {"symbol": "BTCUSDT", "category": "Crypto"},
        {"symbol": "ETHUSDT", "category": "Crypto"},
        {"symbol": "EURUSD", "category": "Forex"},
    ]
    cache = {
        f"{symbol}:quant": (time.time() - 3600, _analysis(symbol, "REJECT", 40))
        for symbol in ("BTCUSDT", "ETHUSDT", "EURUSD")
    }
    refreshed = []

    def analyze(symbol, **kwargs):
        refreshed.append(symbol)
        assert kwargs["preferred_llm"] == "quant"
        assert kwargs["force_refresh"] is True
        return _analysis(symbol, "REJECT", 60)

    monkeypatch.setattr("taikry.config.WATCHLIST", universe)
    monkeypatch.setattr(consensus_engine, "_ANALYSIS_CACHE", cache)
    monkeypatch.setattr(routes.ai_consensus_engine, "analyze_symbol", analyze)

    result = routes.get_best_market_setup("CRYPTO")

    assert refreshed == ["BTCUSDT", "ETHUSDT"]
    assert result["scanned_universe"] == ["BTCUSDT", "ETHUSDT"]
    assert result["candidate_count"] == result["scanned_count"] == 2
    assert [item["analysis_source"] for item in result["setups"]] == ["LIVE_SCAN", "LIVE_SCAN"]


def test_best_setup_selects_swing_cache_and_exposes_swing_levels(monkeypatch):
    universe = [{"symbol": "EURUSD", "category": "Forex"}]
    intraday = _analysis("EURUSD", "APPROVE", 88, "LONG")
    swing = _analysis("EURUSD", "APPROVE", 91, "SHORT")
    swing.update({"trade_style": "SWING", "entry_price": 1.08, "stop_loss": 1.09, "take_profit_1": 1.06, "take_profit_2": 1.05})
    cache = {
        "EURUSD:quant": (time.time(), intraday),
        "EURUSD:quant:SWING": (time.time(), swing),
    }
    monkeypatch.setattr("taikry.config.WATCHLIST", universe)
    monkeypatch.setattr(consensus_engine, "_ANALYSIS_CACHE", cache)
    monkeypatch.setattr(
        routes.ai_consensus_engine,
        "analyze_symbol",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("fresh swing result should be reused")),
    )

    result = routes.get_best_market_setup("FOREX", "SWING")

    assert result["trade_style"] == "SWING"
    assert result["best_setup"]["trade_style"] == "SWING"
    assert result["best_setup"]["proposed_direction"] == "SHORT"
    assert result["best_setup"]["entry_price"] == 1.08
    assert result["best_setup"]["stop_loss"] == 1.09

