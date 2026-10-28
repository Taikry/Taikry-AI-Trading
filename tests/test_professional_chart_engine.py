"""
Unit & Integration Tests for Professional XAUUSD Chart Engine,
Technical Indicators Suite, ICT/SMC Overlays, and Chart API Endpoints.
"""
import pytest
import datetime
import pandas as pd
import numpy as np
from fastapi.testclient import TestClient

from taikry.api.app import app
from taikry.indicators.chart_engine import xauusd_chart_engine, XAUUSDChartEngine
from taikry.indicators.technical import (
    calculate_sma,
    calculate_ema,
    calculate_rsi,
    calculate_macd,
    calculate_stochastic,
    calculate_bollinger_bands,
    calculate_keltner_channels,
    calculate_vwap,
    calculate_session_levels,
    compute_technical_indicators
)

client = TestClient(app)


@pytest.fixture
def sample_ohlcv_dataframe():
    """Generates a deterministic 50-bar synthetic OHLCV DataFrame for testing."""
    np.random.seed(42)
    base_price = 2700.0
    dates = pd.date_range("2026-10-20 00:00:00", periods=50, freq="15min", tz="UTC")

    records = []
    curr = base_price
    for d in dates:
        change = float(np.random.normal(0, 2.5))
        o = curr
        c = round(curr + change, 2)
        h = round(max(o, c) + abs(np.random.normal(1.0, 0.5)), 2)
        l = round(min(o, c) - abs(np.random.normal(1.0, 0.5)), 2)
        vol = round(float(np.random.uniform(500, 3000)), 1)
        records.append({
            "timestamp": d,
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "volume": vol
        })
        curr = c

    return pd.DataFrame(records)


# =========================================================================
# 1. TECHNICAL INDICATORS CALCULATIONS TESTS
# =========================================================================

def test_moving_averages_calculation(sample_ohlcv_dataframe):
    """Verifies that SMA and EMA are calculated accurately and deterministically."""
    closes = sample_ohlcv_dataframe["close"]

    # 1. Simple Moving Average
    sma_20 = calculate_sma(closes, 20)
    assert len(sma_20) == len(closes)
    # The 20th bar SMA should equal the mean of the first 20 bars
    expected_sma_20 = closes.iloc[:20].mean()
    assert abs(sma_20.iloc[19] - expected_sma_20) < 1e-4

    # 2. Exponential Moving Average
    ema_20 = calculate_ema(closes, 20)
    assert len(ema_20) == len(closes)
    assert not ema_20.isna().any()

    # EMA 9, 50, 200
    ema_9 = calculate_ema(closes, 9)
    ema_50 = calculate_ema(closes, 50)
    assert len(ema_9) == len(closes)
    assert len(ema_50) == len(closes)


def test_rsi_wilders_smoothing(sample_ohlcv_dataframe):
    """Verifies Wilder's RSI calculation stays bounded between 0 and 100."""
    closes = sample_ohlcv_dataframe["close"]
    rsi = calculate_rsi(closes, period=14)
    assert len(rsi) == len(closes)
    valid_rsi = rsi.dropna()
    assert (valid_rsi >= 0.0).all()
    assert (valid_rsi <= 100.0).all()


def test_macd_calculation(sample_ohlcv_dataframe):
    """Verifies MACD line, signal line, and histogram relations."""
    closes = sample_ohlcv_dataframe["close"]
    macd_res = calculate_macd(closes, fast=12, slow=26, signal=9)

    assert "macd" in macd_res
    assert "macd_signal" in macd_res
    assert "macd_hist" in macd_res

    # Hist should be macd - signal
    diff = macd_res["macd"] - macd_res["macd_signal"]
    np.testing.assert_allclose(macd_res["macd_hist"].values, diff.values, rtol=1e-5)


def test_stochastic_oscillator(sample_ohlcv_dataframe):
    """Verifies Stochastic Oscillator %K and %D stay bounded between 0 and 100."""
    stoch = calculate_stochastic(sample_ohlcv_dataframe, period=14, smooth_k=3, smooth_d=3)
    assert "stoch_k" in stoch
    assert "stoch_d" in stoch
    assert (stoch["stoch_k"] >= 0.0).all() and (stoch["stoch_k"] <= 100.0).all()
    assert (stoch["stoch_d"] >= 0.0).all() and (stoch["stoch_d"] <= 100.0).all()


def test_bollinger_bands_and_keltner(sample_ohlcv_dataframe):
    """Verifies Bollinger Bands and Keltner Channels envelope ordering."""
    closes = sample_ohlcv_dataframe["close"]
    bb = calculate_bollinger_bands(closes, period=20, num_std=2.0)

    # Upper >= Middle >= Lower
    assert (bb["bb_upper"] >= bb["bb_middle"]).all()
    assert (bb["bb_middle"] >= bb["bb_lower"]).all()

    kc = calculate_keltner_channels(sample_ohlcv_dataframe, ema_period=20, atr_period=14, multiplier=1.5)
    valid_kc_up = kc["kc_upper"].dropna()
    valid_kc_low = kc["kc_lower"].dropna()
    assert (valid_kc_up >= valid_kc_low).all()


def test_session_levels_and_pivots(sample_ohlcv_dataframe):
    """Verifies daily open, PDH, PDL, and standard floor pivots."""
    levels = calculate_session_levels(sample_ohlcv_dataframe)

    assert "daily_open" in levels
    assert "previous_day_high" in levels
    assert "previous_day_low" in levels
    assert "pivot_point" in levels
    assert "resistance_1" in levels
    assert "support_1" in levels

    # Resistance 1 must be above Pivot Point, and Support 1 must be below
    assert levels["resistance_1"] >= levels["pivot_point"]
    assert levels["support_1"] <= levels["pivot_point"]


# =========================================================================
# 2. CHART ENGINE & CAUSALITY TESTS
# =========================================================================

def test_chart_payload_synthesis():
    """Verifies end-to-end chart payload structure and indicator inclusion."""
    payload = xauusd_chart_engine.build_chart_payload(timeframe="M15", limit=40)

    assert payload["success"] is True
    assert "candles" in payload
    assert "annotations" in payload
    assert "metadata" in payload
    assert "summary" in payload

    # Verify first candle has full indicator columns
    c0 = payload["candles"][0]
    expected_keys = [
        "time", "open", "high", "low", "close", "volume",
        "ema_9", "ema_20", "ema_50", "ema_100", "ema_200",
        "sma_20", "sma_50", "sma_200", "rsi_14", "macd",
        "stoch_k", "stoch_d", "atr_14", "bb_middle", "vwap"
    ]
    for k in expected_keys:
        assert k in c0, f"Missing key '{k}' in candle payload"

    # Annotations must contain all SMC structures and session levels
    ann = payload["annotations"]
    assert "swings" in ann
    assert "structure_breaks" in ann
    assert "fair_value_gaps" in ann
    assert "order_blocks" in ann
    assert "liquidity_sweeps" in ann
    assert "session_levels" in ann


def test_indicator_catalogue_bilingual():
    """Verifies get_indicator_catalogue returns complete metadata in Khmer and English."""
    catalogue = xauusd_chart_engine.get_indicator_catalogue()
    assert catalogue["success"] is True
    assert len(catalogue["categories"]) >= 5

    categories = [cat["category"] for cat in catalogue["categories"]]
    assert "TREND" in categories
    assert "MOMENTUM" in categories
    assert "VOLATILITY" in categories
    assert "SESSION_VOLUME" in categories
    assert "ICT_SMC" in categories

    for cat in catalogue["categories"]:
        assert "label_en" in cat and len(cat["label_en"]) > 0
        assert "label_kh" in cat and len(cat["label_kh"]) > 0
        for ind in cat["indicators"]:
            assert "name_en" in ind
            assert "name_kh" in ind
            assert "pane" in ind


# =========================================================================
# 3. REST API ENDPOINTS TESTS
# =========================================================================

def test_api_chart_indicators_endpoint():
    """Tests GET /api/v1/chart/indicators returns HTTP 200 and categories."""
    resp = client.get("/api/v1/chart/indicators")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "categories" in data


def test_api_chart_indicators_calculate_endpoint():
    """Tests POST /api/v1/chart/indicators/calculate returns custom calculated indicators."""
    req_body = {
        "symbol": "XAUUSD",
        "timeframe": "M15",
        "limit": 40,
        "indicators": [
            {"id": "EMA", "period": 21},
            {"id": "SMA", "period": 10},
            {"id": "RSI", "period": 7},
            {"id": "MACD"},
            {"id": "BOLLINGER_BANDS", "params": {"period": 20, "std_dev": 2.0}},
            {"id": "STOCHASTIC"},
            {"id": "VWAP"}
        ]
    }
    resp = client.post("/api/v1/chart/indicators/calculate", json=req_body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "indicators" in data
    inds = data["indicators"]
    assert "EMA_21" in inds
    assert "SMA_10" in inds
    assert "RSI_7" in inds
    assert "MACD" in inds
    assert "BOLLINGER_BANDS" in inds
    assert "STOCHASTIC" in inds
    assert "VWAP" in inds


def test_api_chart_overlays_endpoint():
    """Tests GET /api/v1/chart/overlays returns annotations, multi-timeframe, and trade overlays."""
    resp = client.get("/api/v1/chart/overlays?symbol=XAUUSD&timeframe=M15")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "annotations" in data
    assert "multi_timeframe" in data
    assert "trade_overlays" in data


def test_api_chart_candles_multi_asset():
    """Tests GET /api/v1/chart/candles supports Gold, Forex, and Crypto pairs."""
    for sym in ["XAUUSD", "EURUSD", "BTCUSDT"]:
        resp = client.get(f"/api/v1/chart/candles?symbol={sym}&timeframe=M15&limit=35")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert len(data["candles"]) >= 30
        assert "ema_20" in data["candles"][0]
        assert "rsi_14" in data["candles"][0]
        assert "annotations" in data
