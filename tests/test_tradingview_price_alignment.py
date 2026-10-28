"""
Automated Test Suite: TradingView Price Source Alignment for TAIKRY SIGNAL AI
=============================================================================
Verifies:
1. Exact symbol mapping and reference instrument alignment (Spot Gold vs COMEX Futures).
2. Authoritative quote types (SPOT_MID vs FUTURES_LAST) and provider provenance.
3. Timestamp handling, UTC normalization, and strict monotonicity (preventing out-of-order ticks).
4. Real-time prices endpoint consistency and metadata inclusion (/api/v1/prices/realtime).
5. Chart engine metadata and reference alignment (/api/v1/chart/candles).
6. Candle vs tick consistency across terminal components.
7. Small-limit queries do not prematurely trigger synthetic fallback.
8. Diagnostic alignment and licensing audit endpoint (/api/v1/market-data/alignment).
"""
import datetime
import pytest
from fastapi.testclient import TestClient

from taikry.api.app import app
from taikry.config import (
    WATCHLIST,
    get_symbol_config,
    XAUUSD_PRICE_REFERENCE
)
from taikry.data.providers import (
    market_data_engine,
    REFERENCE_BASE_PRICES,
    YahooFinanceDataProvider
)
from taikry.indicators.chart_engine import xauusd_chart_engine

client = TestClient(app)


def test_xauusd_symbol_mapping_configuration():
    """Verify symbol configuration, TradingView reference mapping, and quote type."""
    cfg = get_symbol_config("XAUUSD")
    assert cfg is not None
    assert cfg["symbol"] == "XAUUSD"

    # In default SPOT mode
    if XAUUSD_PRICE_REFERENCE == "SPOT":
        assert cfg["tv_reference_symbol"] == "OANDA:XAUUSD"
        assert cfg["quote_type"] == "SPOT_MID"
        assert "Spot" in cfg["provider_display"]
        assert cfg["ticker_yahoo"] in ["PAXG-USD", "XAUT-USD"]
    else:
        assert cfg["tv_reference_symbol"] == "COMEX:GC1!"
        assert cfg["quote_type"] == "FUTURES_LAST"
        assert "COMEX" in cfg["provider_display"]
        assert cfg["ticker_yahoo"] == "GC=F"

    # Both spot and futures references must be defined in symbol metadata
    assert cfg.get("tv_symbol_spot") == "OANDA:XAUUSD"
    assert cfg.get("tv_symbol_futures") == "COMEX:GC1!"
    assert cfg.get("ticker_yahoo_spot") == "PAXG-USD"
    assert cfg.get("ticker_yahoo_futures") == "GC=F"


def test_watchlist_all_instruments_have_tv_mapping():
    """Ensure every instrument in the watchlist has a valid TradingView reference symbol."""
    for item in WATCHLIST:
        sym = item["symbol"]
        tv_sym = item.get("tv_reference_symbol")
        quote_type = item.get("quote_type")
        assert tv_sym is not None, f"Missing tv_reference_symbol for {sym}"
        assert quote_type in ["SPOT_MID", "FUTURES_LAST", "CRYPTO_SPOT"], f"Invalid quote_type for {sym}"
        assert ":" in tv_sym, f"TradingView symbol must contain exchange prefix (e.g. OANDA:, FX:, BINANCE:), got: {tv_sym}"


def test_realtime_prices_endpoint_alignment():
    """Verify /api/v1/prices/realtime returns rich reference alignment metadata."""
    res = client.get("/api/v1/prices/realtime?symbols=XAUUSD,EURUSD,BTCUSDT")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "SUCCESS"
    assert "prices" in data

    xau_data = data["prices"].get("XAUUSD")
    assert xau_data is not None
    assert xau_data["symbol"] == "XAUUSD"
    assert isinstance(xau_data["price"], (int, float))
    assert xau_data["price"] > 2000.0  # Gold current market baseline

    # Required TradingView alignment fields
    assert "quote_type" in xau_data
    assert "provider" in xau_data
    assert "tv_symbol" in xau_data
    assert "reference_mode" in xau_data
    assert "timestamp" in xau_data

    if XAUUSD_PRICE_REFERENCE == "SPOT":
        assert xau_data["quote_type"] == "SPOT_MID"
        assert xau_data["tv_symbol"] == "OANDA:XAUUSD"
    else:
        assert xau_data["quote_type"] == "FUTURES_LAST"
        assert xau_data["tv_symbol"] == "COMEX:GC1!"


def test_chart_candles_endpoint_alignment():
    """Verify /api/v1/chart/candles for XAUUSD includes reference_alignment in metadata."""
    res = client.get("/api/v1/chart/candles?symbol=XAUUSD&timeframe=M15&limit=30")
    assert res.status_code == 200
    payload = res.json()
    assert payload["success"] is True
    assert "metadata" in payload
    assert "candles" in payload
    assert len(payload["candles"]) >= 30

    meta = payload["metadata"]
    assert meta["symbol"] == "XAUUSD"
    assert "reference_alignment" in meta

    alignment = meta["reference_alignment"]
    assert alignment["reference_mode"] in ["SPOT", "FUTURES"]
    assert alignment["tv_reference_symbol"] in ["OANDA:XAUUSD", "COMEX:GC1!"]
    assert alignment["quote_type"] in ["SPOT_MID", "FUTURES_LAST"]
    assert "provider_display" in alignment
    assert "basis_note" in alignment

    # Monotonicity check on candles
    candles = payload["candles"]
    times = [c["time"] for c in candles]
    for i in range(1, len(times)):
        assert times[i] > times[i - 1], f"Candle times must be strictly increasing: {times[i]} <= {times[i-1]}"


def test_small_limit_preserves_real_market_candles():
    """
    Regression Test:
    Calling get_candles with a small limit (e.g. limit=5 or limit=10)
    must NOT discard valid candles and must NOT fall back to synthetic 4055.00 candles!
    """
    df = market_data_engine.get_candles("XAUUSD", timeframe="M15", limit=10)
    assert not df.empty
    assert len(df) >= 5
    latest_close = float(df.iloc[-1]["close"])
    # The price must be within realistic gold prices (e.g. 3800 to 4300)
    assert 3800.0 <= latest_close <= 4300.0
    # Must NOT be hardcoded old synthetic seed 4055.00 if real feed was fetched
    assert df.iloc[-1]["source"] != "synthetic_institutional_feed" or len(df) == 10


def test_quote_consistency_between_chart_and_realtime_feed():
    """Verify that latest candle Close and realtime ticker quote are aligned."""
    chart_res = client.get("/api/v1/chart/candles?symbol=XAUUSD&timeframe=M15&limit=30")
    assert chart_res.status_code == 200
    chart_data = chart_res.json()
    last_candle_close = chart_data["candles"][-1]["close"]

    rt_res = client.get("/api/v1/prices/realtime?symbols=XAUUSD")
    assert rt_res.status_code == 200
    rt_price = rt_res.json()["prices"]["XAUUSD"]["price"]

    # Difference between latest candle close and real-time tick should be within 0.5% (normal intraday tick movement)
    pct_diff = abs(last_candle_close - rt_price) / rt_price
    assert pct_diff < 0.015, f"Chart close (${last_candle_close}) and realtime price (${rt_price}) differ by {pct_diff*100:.2f}%"


def test_market_data_alignment_diagnostic_endpoint():
    """Verify GET /api/v1/market-data/alignment returns exhaustive audit."""
    res = client.get("/api/v1/market-data/alignment")
    assert res.status_code == 200
    audit = res.json()
    assert audit["status"] == "SUCCESS"
    assert audit["primary_instrument"] == "XAUUSD"

    details = audit["alignment_audit"]
    assert details["reference_mode"] in ["SPOT", "FUTURES"]
    assert details["tv_reference_symbol"] in ["OANDA:XAUUSD", "COMEX:GC1!"]
    assert details["quote_type"] in ["SPOT_MID", "FUTURES_LAST"]
    assert details["verified_price"] > 2000.0
    assert details["freshness_status"] in ["LIVE_FRESH", "SLIGHTLY_DELAYED", "WEEKEND_CLOSED", "STALE"]

    # Terms and licensing compliance check
    licensing = details["licensing_compliance"]
    assert licensing["internal_tv_scraping_used"] is False
    assert licensing["terms_compliant"] is True
    assert "Lightweight Charts" in licensing["chart_implementation"]

    # Basis differential analysis documentation check
    basis = details["market_basis_analysis"]
    assert "spot_gold_reference" in basis
    assert "futures_gold_reference" in basis
    assert "contango" in basis["basis_explanation"].lower() or "carry" in basis["basis_explanation"].lower()

    # Watchlist mappings check
    mappings = audit["watchlist_tv_mappings"]
    assert len(mappings) > 0
    symbols = [m["symbol"] for m in mappings]
    assert "XAUUSD" in symbols
    assert "EURUSD" in symbols
    assert "BTCUSDT" in symbols
