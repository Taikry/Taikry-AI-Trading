"""
Unit tests for Milestone 2: Quantitative Indicators and ICT/SMC Engine
"""
import pytest
import datetime
import pandas as pd
import numpy as np
from taikry.indicators.technical import (
    compute_technical_indicators,
    extract_technical_summary,
    calculate_rsi,
    calculate_atr,
    detect_candlestick_patterns
)
from taikry.indicators.ict_smc import (
    detect_fair_value_gaps,
    detect_order_blocks,
    compute_premium_discount,
    get_current_session,
    extract_ict_smc_summary
)

@pytest.fixture
def sample_market_df():
    # 60 bars of synthetic trend
    timestamps = [datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=15 * (60 - i)) for i in range(60)]
    closes = [2000.0 + (i * 0.5) + (2.0 if i % 2 == 0 else -1.0) for i in range(60)]
    opens = [c - 0.2 for c in closes]
    highs = [max(o, c) + 1.0 for o, c in zip(opens, closes)]
    lows = [min(o, c) - 1.0 for o, c in zip(opens, closes)]
    volumes = [500.0 + i * 10 for i in range(60)]

    return pd.DataFrame({
        "timestamp": timestamps,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes
    })

def test_technical_indicator_computation(sample_market_df):
    df_ind = compute_technical_indicators(sample_market_df)
    assert "ema_20" in df_ind.columns
    assert "ema_50" in df_ind.columns
    assert "rsi" in df_ind.columns
    assert "atr" in df_ind.columns
    assert "macd" in df_ind.columns
    assert "bb_upper" in df_ind.columns

    summary = extract_technical_summary(df_ind)
    assert "current_price" in summary
    assert "trend" in summary
    assert 0 <= summary["rsi"] <= 100
    assert summary["atr"] > 0

def test_candlestick_hammer_detection():
    # Construct a hammer / pin bar: small body at top, long lower wick
    df = pd.DataFrame({
        "timestamp": [datetime.datetime.now(datetime.timezone.utc) for _ in range(5)],
        "open": [100.0, 100.0, 100.0, 100.0, 104.0],
        "high": [101.0, 101.0, 101.0, 101.0, 105.0],
        "low": [99.0, 99.0, 99.0, 99.0, 95.0],   # Lower wick = 104 - 95 = 9.0, body = 1.0
        "close": [100.5, 100.5, 100.5, 100.5, 105.0],
        "volume": [100.0] * 5
    })
    patterns = detect_candlestick_patterns(df)
    assert "BULLISH_PIN_BAR_HAMMER" in patterns

def test_fair_value_gap_detection():
    # 3-candle bullish FVG: candle 0 high < candle 2 low
    timestamps = [datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=15 * i) for i in range(5)]
    df = pd.DataFrame({
        "timestamp": timestamps,
        "open": [100.0, 102.0, 106.0, 107.0, 108.0],
        "high": [101.0, 105.0, 109.0, 110.0, 111.0],  # Candle 0 high = 101.0
        "low": [99.0, 101.5, 104.0, 106.0, 107.0],   # Candle 2 low = 104.0 > 101.0 -> FVG [101.0, 104.0]
        "close": [100.5, 104.5, 108.5, 109.5, 110.5],
        "volume": [100.0] * 5
    })
    fvgs = detect_fair_value_gaps(df)
    assert len(fvgs) > 0
    bullish = [f for f in fvgs if f["type"] == "BULLISH_FVG"]
    assert len(bullish) > 0
    assert bullish[0]["bottom"] == 101.0
    assert bullish[0]["top"] == 104.0

def test_premium_discount():
    df = pd.DataFrame({
        "timestamp": [datetime.datetime.now(datetime.timezone.utc) for _ in range(15)],
        "open": [100.0] * 15,
        "high": [110.0] * 15,
        "low": [90.0] * 15,
        "close": [106.0] * 14 + [108.0], # Current price 108 is > equilibrium 100
        "volume": [100.0] * 15
    })
    pd_info = compute_premium_discount(df)
    assert pd_info["equilibrium"] == 100.0
    assert pd_info["current_zone"] == "PREMIUM"

def test_session_detection():
    session = get_current_session()
    assert "active_sessions" in session
    assert "volatility_context" in session

def test_optimal_trade_entry():
    from taikry.indicators.ict_smc import compute_optimal_trade_entry, identify_swing_points
    # 20 bars ranging between 100.0 and 200.0 (span = 100.0)
    # Range: Low = 100.0, High = 200.0
    # Eq 50% = 150.0
    # Bullish OTE: Retracement down from 200.0
    # fib_618 = 200 - 61.8 = 138.2
    # fib_705 = 200 - 70.5 = 129.5
    # fib_786 = 200 - 78.6 = 121.4
    df = pd.DataFrame({
        "timestamp": [datetime.datetime.now(datetime.timezone.utc) for _ in range(20)],
        "open": [150.0] * 20,
        "high": [160.0] * 19 + [200.0],
        "low": [100.0] + [140.0] * 18 + [125.0],
        "close": [150.0] * 19 + [128.0], # Current price 128.0 is between 121.4 and 138.2 (In OTE)
        "volume": [100.0] * 20
    })
    swings = identify_swing_points(df, left=1, right=1)
    ote = compute_optimal_trade_entry(df, swings)
    assert "fib_705_sweet_spot" in ote
    assert "fib_618" in ote
    assert "fib_786" in ote
    assert ote["equilibrium_50"] == 150.0

def test_breaker_blocks_detection():
    from taikry.indicators.ict_smc import detect_breaker_blocks
    # Given a Bearish Order Block at low=100.0, high=105.0
    # Price breaks violently above 105.0 to 115.0 -> turns into Bullish Breaker
    obs = [{
        "type": "BEARISH_ORDER_BLOCK",
        "high": 105.0,
        "low": 100.0,
        "timestamp": "2026-10-27T00:00:00Z"
    }]
    df = pd.DataFrame({
        "timestamp": [datetime.datetime.now(datetime.timezone.utc) for _ in range(5)],
        "open": [102.0, 104.0, 107.0, 110.0, 112.0],
        "high": [105.0, 106.0, 109.0, 113.0, 115.0],
        "low": [100.0, 103.0, 106.0, 109.0, 111.0],
        "close": [104.0, 105.5, 108.0, 112.0, 114.0],
        "volume": [100.0] * 5
    })
    breakers = detect_breaker_blocks(df, obs)
    assert len(breakers) == 1
    assert breakers[0]["type"] == "BULLISH_BREAKER"
    assert breakers[0]["role"] == "INSTITUTIONAL_SUPPORT"

def test_ict_killzones_and_silver_bullet():
    from taikry.indicators.ict_smc import get_ict_killzones
    # 1. Test 14:30 UTC -> NY AM Silver Bullet (10:00 - 11:00 AM EST)
    dt_sb = datetime.datetime(2026, 10, 27, 14, 30, tzinfo=datetime.timezone.utc)
    kz_sb = get_ict_killzones(dt_sb)
    assert kz_sb["is_silver_bullet"] is True
    assert "SILVER BULLET" in kz_sb["current_label"]

    # 2. Test 08:30 UTC -> London Open Killzone
    dt_lon = datetime.datetime(2026, 10, 27, 8, 30, tzinfo=datetime.timezone.utc)
    kz_lon = get_ict_killzones(dt_lon)
    assert "London Open Killzone" in kz_lon["active_killzones"]

def test_volume_profile_computation(sample_market_df):
    from taikry.indicators.ict_smc import compute_volume_profile
    vp = compute_volume_profile(sample_market_df, num_bins=20, lookback=50)

    assert "poc" in vp
    assert "vah" in vp
    assert "val" in vp
    assert "current_position" in vp
    assert "profile_bars" in vp
    assert len(vp["profile_bars"]) == 20
    assert vp["val"] <= vp["poc"] <= vp["vah"]

    poc_bars = [b for b in vp["profile_bars"] if b["is_poc"]]
    assert len(poc_bars) == 1
    assert poc_bars[0]["in_value_area"] is True
    assert vp["total_volume"] > 0

def test_inversion_fair_value_gaps():
    from taikry.indicators.ict_smc import detect_inversion_fair_value_gaps

    # Create a scenario where a Bearish FVG is formed, then subsequently price breaks above it
    # c0: high=110, low=105
    # c1: candle
    # c2: high=102, low=98 -> Bearish FVG between 102 and 105
    # c3: candle closes at 108 (breaches 105 upward) -> flips to Bullish Support IFVG
    timestamps = [datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=15 * i) for i in range(7)]
    df = pd.DataFrame({
        "timestamp": timestamps,
        "open": [108.0, 104.0, 100.0, 103.0, 106.0, 104.5, 104.0],
        "high": [110.0, 105.0, 102.0, 107.0, 109.0, 105.0, 104.8],
        "low": [105.0, 101.0, 98.0, 101.0, 105.5, 103.0, 103.5],
        "close": [106.0, 102.0, 99.0, 106.5, 108.0, 104.0, 104.2],
        "volume": [100.0] * 7
    })
    res = detect_inversion_fair_value_gaps(df, lookback=10)
    assert "inversion_fvgs" in res
    assert "balanced_price_ranges" in res
    assert len(res["inversion_fvgs"]) > 0
    bullish_ifvgs = [f for f in res["inversion_fvgs"] if f["type"] == "BULLISH_INVERSION_FVG"]
    assert len(bullish_ifvgs) > 0
    assert bullish_ifvgs[0]["role"] == "SUPPORT_FLIP"

def test_extract_ict_smc_summary_extended(sample_market_df):
    summary = extract_ict_smc_summary(sample_market_df)
    assert "volume_profile" in summary
    assert "inversion_fvgs" in summary
    assert "poc" in summary["volume_profile"]
    assert "inversion_fvgs" in summary["inversion_fvgs"]


