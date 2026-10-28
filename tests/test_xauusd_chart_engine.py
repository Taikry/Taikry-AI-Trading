"""
Comprehensive Production Test Suite for XAUUSD Chart Engine
============================================================
Tests:
1. Candlestick OHLCV Data & Freshness Metadata
2. Technical Indicators (Recursive EMA 20, 50, 200, Wilder's RSI 14)
3. Causal Non-Repainting Swings (Confirmation at i + right)
4. BOS (Break of Structure) & CHoCH (Change of Character)
5. Fair Value Gaps (FVG) & Consequent Encroachment (CE 50%)
6. Order Blocks (OB) with Displacement Confirmation
7. Liquidity Sweeps (BSL / SSL Wick Sweeps)
8. Invariant Audit: Strict Zero Lookahead Bias & Zero Repainting
9. FastAPI Integration Endpoints (/api/v1/chart/xauusd & /api/v1/chart/candles)
"""

import pytest
import datetime
import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from taikry.api.app import app
from taikry.indicators.chart_engine import XAUUSDChartEngine, xauusd_chart_engine


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_gold_candles():
    """Generates synthetic deterministic XAUUSD candles for controlled structure testing."""
    now = datetime.datetime.now(datetime.timezone.utc)
    base_price = 2650.00
    records = []

    # Controlled price path:
    # 0-9: Baseline consolidation around 2650
    # 10: Swing Low at 2640
    # 11-15: Upward expansion to 2670 (Swing High at 2670 on bar 15)
    # 16-20: Pullback with Bullish FVG at [2655, 2662]
    # 21-25: Violent break above 2670 -> Bullish BOS
    # 26-30: Reversal downward breaking below swing low -> Bearish CHoCH
    prices = [
        # 0 - 9
        (2650, 2653, 2648, 2651),
        (2651, 2654, 2649, 2650),
        (2650, 2652, 2648, 2649),
        (2649, 2653, 2647, 2652),
        (2652, 2655, 2650, 2651),
        (2651, 2653, 2648, 2649),
        (2649, 2651, 2646, 2648),
        (2648, 2652, 2647, 2650),
        (2650, 2653, 2649, 2648),
        (2648, 2650, 2642, 2644),
        # 10: Swing Low candidate (Low 2638.00)
        (2644, 2646, 2638, 2641),
        # 11 - 14: Strong Bullish Impulse (Displacement from Order Block)
        (2641, 2652, 2640, 2650),
        (2650, 2660, 2649, 2658),
        (2658, 2667, 2656, 2665),
        (2665, 2672, 2664, 2671),
        # 15: Swing High candidate (High 2675.00)
        (2671, 2675, 2668, 2670),
        # 16 - 19: Pullback (Bar 16 down, 17 down, 18 FVG setup)
        (2670, 2671, 2663, 2664),
        (2664, 2666, 2658, 2659),
        (2659, 2662, 2654, 2655),
        (2655, 2661, 2653, 2660),
        # 20 - 24: Bullish Breakout above 2675.00 (Bullish BOS)
        (2660, 2668, 2659, 2667),
        (2667, 2674, 2666, 2673),
        (2673, 2682, 2672, 2680), # Closes at 2680 > 2675 -> BOS
        (2680, 2688, 2679, 2685),
        (2685, 2692, 2684, 2690),
        # 25: Liquidity Sweep Wick (Wicks to 2695, closes at 2682)
        (2690, 2695, 2681, 2682),
        # 26 - 32: Violent Downward Flush (Displacement breaking previous swing low)
        (2682, 2684, 2670, 2671),
        (2671, 2673, 2658, 2660),
        (2660, 2662, 2645, 2647),
        (2647, 2650, 2632, 2634), # Closes at 2634 < 2638 -> Bearish CHoCH
        (2634, 2636, 2625, 2628),
        (2628, 2632, 2622, 2626),
        (2626, 2630, 2620, 2625)
    ]

    for idx, (o, h, l, c) in enumerate(prices):
        t = now - datetime.timedelta(minutes=15 * (len(prices) - idx))
        records.append({
            "timestamp": t,
            "open": float(o),
            "high": float(h),
            "low": float(l),
            "close": float(c),
            "volume": 2500.0,
            "source": "verified_institutional_stream"
        })

    return pd.DataFrame(records)


# =============================================================================
# TEST 1: Candlestick Fetching & Freshness Auditing
# =============================================================================

def test_fetch_xauusd_candles_and_metadata():
    engine = XAUUSDChartEngine()
    df, meta = engine.fetch_xauusd_candles(timeframe="M15", limit=60)

    assert not df.empty
    assert len(df) >= 30
    assert all(col in df.columns for col in ["timestamp", "open", "high", "low", "close", "volume"])
    
    # Audit metadata assertions
    assert meta["symbol"] == "XAUUSD"
    assert "provider" in meta
    assert meta["license_type"] == "LICENSED_FINANCIAL_FEED"
    assert meta["lookahead_bias_free"] is True
    assert meta["repainting_free"] is True
    assert "latest_candle_utc" in meta
    assert "latest_candle_cambodia" in meta
    assert meta["candle_age_seconds"] >= 0.0
    assert "integrity_checksum" in meta


# =============================================================================
# TEST 2: Non-Repainting Technical Indicators (EMA & Wilder's RSI)
# =============================================================================

def test_compute_technical_indicators(sample_gold_candles):
    engine = XAUUSDChartEngine()
    df_ind = engine.compute_technical_indicators(sample_gold_candles)

    assert "ema_20" in df_ind.columns
    assert "ema_50" in df_ind.columns
    assert "ema_200" in df_ind.columns
    assert "rsi_14" in df_ind.columns

    # Closes and EMAs should be valid numerical values
    assert not df_ind["ema_20"].isna().all()
    assert not df_ind["rsi_14"].isna().all()

    # RSI must be strictly bounded in [0, 100]
    valid_rsi = df_ind["rsi_14"].dropna()
    assert (valid_rsi >= 0.0).all()
    assert (valid_rsi <= 100.0).all()

    # Causal test: Appending future candles does not alter past historical EMA values
    sub_df = sample_gold_candles.iloc[:20].copy()
    sub_ind = engine.compute_technical_indicators(sub_df)
    
    assert np.isclose(sub_ind["ema_20"].iloc[19], df_ind["ema_20"].iloc[19], atol=1e-2)
    assert np.isclose(sub_ind["rsi_14"].iloc[19], df_ind["rsi_14"].iloc[19], atol=1e-1)


# =============================================================================
# TEST 3: Causal Non-Repainting Swings (Confirmation Rule)
# =============================================================================

def test_detect_causal_swings(sample_gold_candles):
    engine = XAUUSDChartEngine()
    swings = engine.detect_causal_swings(sample_gold_candles, left=3, right=3)

    assert len(swings) > 0
    for s in swings:
        # Crucial Non-Repainting Invariant:
        # Confirmation index MUST be strictly greater than pivot index by `right` bars
        assert s["confirmation_index"] == s["pivot_index"] + 3
        assert s["type"] in ["SWING_HIGH", "SWING_LOW"]
        assert s["price"] > 0


# =============================================================================
# TEST 4: BOS (Break of Structure) & CHoCH (Change of Character)
# =============================================================================

def test_detect_causal_bos_and_choch(sample_gold_candles):
    engine = XAUUSDChartEngine()
    swings = engine.detect_causal_swings(sample_gold_candles, left=3, right=3)
    breaks = engine.detect_causal_bos_and_choch(sample_gold_candles, swings)

    assert len(breaks) > 0
    categories = [b["category"] for b in breaks]
    assert "BOS" in categories or "CHOCH" in categories

    for b in breaks:
        assert b["category"] in ["BOS", "CHOCH"]
        assert b["direction"] in ["BULLISH", "BEARISH"]
        assert b["break_index"] >= b["pivot_index"]
        if b["direction"] == "BULLISH":
            assert b["close_price"] > b["broken_level"]
        else:
            assert b["close_price"] < b["broken_level"]


# =============================================================================
# TEST 5: Fair Value Gaps (FVG) and Mitigation Tracking
# =============================================================================

def test_detect_causal_fair_value_gaps(sample_gold_candles):
    engine = XAUUSDChartEngine()
    fvgs = engine.detect_causal_fair_value_gaps(sample_gold_candles)

    assert len(fvgs) > 0
    for f in fvgs:
        assert f["type"] in ["BULLISH_FVG", "BEARISH_FVG"]
        assert f["top"] > f["bottom"]
        assert f["midpoint_ce"] == round((f["top"] + f["bottom"]) / 2.0, 2)
        assert f["confirmation_index"] == f["creation_index"] + 1
        assert f["status"] in ["OPEN", "PARTIALLY_MITIGATED", "FULLY_MITIGATED"]


# =============================================================================
# TEST 6: Order Blocks with Displacement
# =============================================================================

def test_detect_causal_order_blocks(sample_gold_candles):
    engine = XAUUSDChartEngine()
    obs = engine.detect_causal_order_blocks(sample_gold_candles)

    assert len(obs) > 0
    for ob in obs:
        assert ob["type"] in ["BULLISH_ORDER_BLOCK", "BEARISH_ORDER_BLOCK"]
        assert ob["high"] >= ob["low"]
        assert ob["confirmation_index"] == ob["candle_index"] + 1
        assert ob["status"] in ["UNTESTED", "TESTED", "BREACHED"]


# =============================================================================
# TEST 7: Liquidity Sweeps Detection
# =============================================================================

def test_detect_causal_liquidity_sweeps(sample_gold_candles):
    engine = XAUUSDChartEngine()
    swings = engine.detect_causal_swings(sample_gold_candles, left=3, right=3)
    sweeps = engine.detect_causal_liquidity_sweeps(sample_gold_candles, swings)

    # In our sample data, bar 25 wicks above swing high 2675 to 2695, but closes at 2682
    for sw in sweeps:
        assert sw["type"] in ["BUY_SIDE_LIQUIDITY_SWEEP", "SELL_SIDE_LIQUIDITY_SWEEP"]
        if sw["type"] == "BUY_SIDE_LIQUIDITY_SWEEP":
            assert sw["wick_high"] > sw["swept_level"]
            assert sw["rejection_close"] < sw["swept_level"]
            assert sw["bias_implication"] == "BEARISH_REVERSAL"
        else:
            assert sw["wick_low"] < sw["swept_level"]
            assert sw["rejection_close"] > sw["swept_level"]
            assert sw["bias_implication"] == "BULLISH_REVERSAL"


# =============================================================================
# TEST 8: Zero Lookahead Bias & Zero Repainting Invariant Test
# =============================================================================

def test_zero_lookahead_bias_invariant(sample_gold_candles):
    """
    CRITICAL ALGORITHMIC INVARIANT:
    Running the chart engine on slice [0..T] must produce identical indicators,
    swings, and structural signals at bar T as running on slice [0..T+10].
    Future candles cannot repaint past historical facts.
    """
    engine = XAUUSDChartEngine()
    t_cutoff = 22

    # Run on historical prefix [0 .. 22]
    slice_t = sample_gold_candles.iloc[:t_cutoff + 1].copy()
    payload_t = engine.compute_technical_indicators(slice_t)
    swings_t = engine.detect_causal_swings(payload_t)
    breaks_t = engine.detect_causal_bos_and_choch(payload_t, swings_t)
    fvgs_t = engine.detect_causal_fair_value_gaps(payload_t)

    # Run on full series [0 .. 33] (with 11 future candles added)
    full_df = sample_gold_candles.copy()
    payload_full = engine.compute_technical_indicators(full_df)
    swings_full = engine.detect_causal_swings(payload_full)
    breaks_full = engine.detect_causal_bos_and_choch(payload_full, swings_full)
    fvgs_full = engine.detect_causal_fair_value_gaps(payload_full)

    # 1. Past EMA & RSI at cutoff bar MUST be numerically identical
    assert np.isclose(payload_t["ema_20"].iloc[t_cutoff], payload_full["ema_20"].iloc[t_cutoff], atol=1e-3)
    assert np.isclose(payload_t["rsi_14"].iloc[t_cutoff], payload_full["rsi_14"].iloc[t_cutoff], atol=1e-2)

    # 2. Confirmed Swings known at or before t_cutoff MUST match exactly
    swings_known_at_t = [s for s in swings_full if s["confirmation_index"] <= t_cutoff]
    assert len(swings_t) == len(swings_known_at_t)
    for st, sf in zip(swings_t, swings_known_at_t):
        assert st["pivot_index"] == sf["pivot_index"]
        assert st["price"] == sf["price"]
        assert st["type"] == sf["type"]

    # 3. Structure breaks confirmed at or before t_cutoff MUST match exactly
    breaks_known_at_t = [b for b in breaks_full if b["break_index"] <= t_cutoff]
    assert len(breaks_t) == len(breaks_known_at_t)
    for bt, bf in zip(breaks_t, breaks_known_at_t):
        assert bt["break_index"] == bf["break_index"]
        assert bt["broken_level"] == bf["broken_level"]
        assert bt["category"] == bf["category"]

    # 4. FVGs confirmed at or before t_cutoff MUST have identical creation indices & geometry
    fvgs_confirmed_at_t = [f for f in fvgs_full if f["confirmation_index"] <= t_cutoff]
    assert len(fvgs_t) == len(fvgs_confirmed_at_t)
    for ft, ff in zip(fvgs_t, fvgs_confirmed_at_t):
        assert ft["creation_index"] == ff["creation_index"]
        assert ft["top"] == ff["top"]
        assert ft["bottom"] == ff["bottom"]


# =============================================================================
# TEST 9: FastAPI Chart Endpoints Integration
# =============================================================================

def test_api_get_xauusd_chart_endpoint(client):
    r = client.get("/api/v1/chart/xauusd?timeframe=M15&limit=60")
    assert r.status_code == 200
    data = r.json()

    assert data["success"] is True
    assert "metadata" in data
    assert data["metadata"]["symbol"] == "XAUUSD"
    assert data["metadata"]["lookahead_bias_free"] is True
    assert data["metadata"]["repainting_free"] is True

    assert "summary" in data
    assert "current_price" in data["summary"]
    assert "rsi_14_value" in data["summary"]

    assert "candles" in data
    assert len(data["candles"]) >= 30
    latest_candle = data["candles"][-1]
    assert all(k in latest_candle for k in ["time", "open", "high", "low", "close", "ema_20", "rsi_14"])

    assert "annotations" in data
    assert "fair_value_gaps" in data["annotations"]
    assert "order_blocks" in data["annotations"]
    assert "structure_breaks" in data["annotations"]
    assert "liquidity_sweeps" in data["annotations"]


def test_api_get_chart_candles_endpoint(client):
    # Test general endpoint routing
    r_gold = client.get("/api/v1/chart/candles?symbol=XAUUSD&timeframe=H1&limit=50")
    assert r_gold.status_code == 200
    data_gold = r_gold.json()
    assert data_gold["success"] is True
    assert len(data_gold["candles"]) > 0

    r_btc = client.get("/api/v1/chart/candles?symbol=BTCUSDT&timeframe=M15&limit=40")
    assert r_btc.status_code == 200
    data_btc = r_btc.json()
    assert data_btc["success"] is True
    assert data_btc["symbol"] == "BTCUSDT"
