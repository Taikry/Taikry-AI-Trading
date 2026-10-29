"""
Quantitative Technical Indicators Engine for TAIKRY AI MARKET INTELLIGENCE PRO
Includes: EMA 20/50/200, RSI 14, ATR 14, MACD, Bollinger Bands, Swing Support/Resistance,
and Candlestick Pattern Recognition.
"""
from typing import Dict, Any, List
import pandas as pd
import numpy as np

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Computes standard Relative Strength Index."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    
    # Wilder's smoothing
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    
    rs = avg_gain / (avg_loss + 1e-10)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi

def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Computes Average True Range for volatility measurement and dynamic SL/TP."""
    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr

def detect_candlestick_patterns(df: pd.DataFrame) -> List[str]:
    """Detects classical price action patterns on latest candles."""
    if len(df) < 5:
        return []

    patterns = []
    latest = df.iloc[-1]
    prev = df.iloc[-2]

    curr_o, curr_h, curr_l, curr_c = latest["open"], latest["high"], latest["low"], latest["close"]
    prev_o, prev_h, prev_l, prev_c = prev["open"], prev["high"], prev["low"], prev["close"]

    body = abs(curr_c - curr_o)
    candle_range = curr_h - curr_l
    upper_wick = curr_h - max(curr_o, curr_c)
    lower_wick = min(curr_o, curr_c) - curr_l

    if candle_range > 0:
        # Pin Bar / Hammer (Bullish rejection of lower prices)
        if lower_wick >= 2 * body and upper_wick <= 0.2 * candle_range:
            patterns.append("BULLISH_PIN_BAR_HAMMER")

        # Shooting Star (Bearish rejection of higher prices)
        if upper_wick >= 2 * body and lower_wick <= 0.2 * candle_range:
            patterns.append("BEARISH_SHOOTING_STAR")

        # Bullish Engulfing
        if prev_c < prev_o and curr_c > curr_o and curr_c >= prev_o and curr_o <= prev_c:
            patterns.append("BULLISH_ENGULFING")

        # Bearish Engulfing
        if prev_c > prev_o and curr_c < curr_o and curr_c <= prev_o and curr_o >= prev_c:
            patterns.append("BEARISH_ENGULFING")

        # Doji (Indecision)
        if body <= 0.1 * candle_range:
            patterns.append("DOJI_INDECISION")

    return patterns

def calculate_sma(series: pd.Series, period: int = 20) -> pd.Series:
    """Computes Simple Moving Average with minimum warmup periods."""
    return series.rolling(window=period, min_periods=1).mean()

def calculate_ema(series: pd.Series, period: int = 20) -> pd.Series:
    """Computes Exponential Moving Average with recursive smoothing (adjust=False)."""
    return series.ewm(span=period, adjust=False).mean()

def calculate_macd(
    series: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9
) -> Dict[str, pd.Series]:
    """Computes MACD line, signal line, and histogram."""
    fast_ema = series.ewm(span=fast, adjust=False).mean()
    slow_ema = series.ewm(span=slow, adjust=False).mean()
    macd_line = fast_ema - slow_ema
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return {
        "macd": macd_line,
        "macd_signal": signal_line,
        "macd_hist": hist
    }

def calculate_stochastic(
    df: pd.DataFrame,
    period: int = 14,
    smooth_k: int = 3,
    smooth_d: int = 3
) -> Dict[str, pd.Series]:
    """
    Computes Fast & Slow Stochastic Oscillator (%K and %D).
    Strictly causal without lookahead bias.
    """
    low_min = df["low"].rolling(window=period, min_periods=1).min()
    high_max = df["high"].rolling(window=period, min_periods=1).max()
    denom = (high_max - low_min).replace(0, 1e-10)
    raw_k = 100.0 * ((df["close"] - low_min) / denom)
    stoch_k = raw_k.rolling(window=smooth_k, min_periods=1).mean()
    stoch_d = stoch_k.rolling(window=smooth_d, min_periods=1).mean()
    return {
        "stoch_k": stoch_k.clip(0.0, 100.0),
        "stoch_d": stoch_d.clip(0.0, 100.0)
    }

def calculate_bollinger_bands(
    series: pd.Series,
    period: int = 20,
    num_std: float = 2.0
) -> Dict[str, pd.Series]:
    """Computes Bollinger Bands (Middle, Upper, Lower)."""
    sma = series.rolling(window=period, min_periods=1).mean()
    std = series.rolling(window=period, min_periods=1).std().fillna(0.0)
    upper = sma + (std * num_std)
    lower = sma - (std * num_std)
    return {
        "bb_middle": sma,
        "bb_upper": upper,
        "bb_lower": lower
    }

def calculate_keltner_channels(
    df: pd.DataFrame,
    ema_period: int = 20,
    atr_period: int = 14,
    multiplier: float = 1.5
) -> Dict[str, pd.Series]:
    """Computes Keltner Channels (EMA center with ATR envelope)."""
    center = df["close"].ewm(span=ema_period, adjust=False).mean()
    atr = calculate_atr(df, period=atr_period)
    upper = center + (multiplier * atr)
    lower = center - (multiplier * atr)
    return {
        "kc_middle": center,
        "kc_upper": upper,
        "kc_lower": lower
    }

def calculate_vwap(df: pd.DataFrame) -> pd.Series:
    """
    Computes Session-Anchored Volume Weighted Average Price (VWAP).
    Resets at start of each trading day if timestamp is available.
    """
    typical_price = (df["high"] + df["low"] + df["close"]) / 3.0
    vol = df["volume"] if "volume" in df.columns else pd.Series(1000.0, index=df.index)
    pv = typical_price * vol

    if "timestamp" in df.columns and pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
        dates = df["timestamp"].dt.date
        cum_pv = pv.groupby(dates).cumsum()
        cum_vol = vol.groupby(dates).cumsum().replace(0, 1e-10)
        return (cum_pv / cum_vol).round(4)
    else:
        cum_pv = pv.cumsum()
        cum_vol = vol.cumsum().replace(0, 1e-10)
        return (cum_pv / cum_vol).round(4)

def calculate_session_levels(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Computes critical session benchmark price levels:
    - Daily Open (DO)
    - Previous Day High (PDH) & Previous Day Low (PDL)
    - Previous Week High (PWH) & Previous Week Low (PWL)
    - Classical Floor Pivot Points (Pivot, R1, S1, R2, S2)
    """
    if df.empty or len(df) < 5:
        return {}

    curr_close = float(df["close"].iloc[-1])

    # Check datetime grouping if timestamp is present
    if "timestamp" in df.columns and pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
        df_ts = df.copy()
        df_ts["date"] = df_ts["timestamp"].dt.date
        unique_dates = df_ts["date"].unique()

        if len(unique_dates) >= 2:
            prev_date = unique_dates[-2]
            curr_date = unique_dates[-1]

            prev_day_data = df_ts[df_ts["date"] == prev_date]
            curr_day_data = df_ts[df_ts["date"] == curr_date]

            pdh = float(prev_day_data["high"].max())
            pdl = float(prev_day_data["low"].min())
            pdc = float(prev_day_data["close"].iloc[-1])
            do = float(curr_day_data["open"].iloc[0]) if not curr_day_data.empty else curr_close
        else:
            # Fallback for single date: use first half vs second half
            split_idx = len(df) // 2
            prev_chunk = df.iloc[:split_idx]
            curr_chunk = df.iloc[split_idx:]
            pdh = float(prev_chunk["high"].max())
            pdl = float(prev_chunk["low"].min())
            pdc = float(prev_chunk["close"].iloc[-1])
            do = float(curr_chunk["open"].iloc[0])
    else:
        # Standard lookback split (last 20 bars as current day, prior 20 as previous day)
        lb = min(len(df) // 2, 20)
        prev_chunk = df.iloc[-(2 * lb):-lb] if len(df) >= 2 * lb else df.iloc[:lb]
        curr_chunk = df.iloc[-lb:]
        pdh = float(prev_chunk["high"].max())
        pdl = float(prev_chunk["low"].min())
        pdc = float(prev_chunk["close"].iloc[-1])
        do = float(curr_chunk["open"].iloc[0])

    # Standard Floor Pivot Points
    pivot_point = (pdh + pdl + pdc) / 3.0
    r1 = (2 * pivot_point) - pdl
    s1 = (2 * pivot_point) - pdh
    r2 = pivot_point + (pdh - pdl)
    s2 = pivot_point - (pdh - pdl)

    # Weekly estimate (last 100 bars or full history)
    lookback_week = min(len(df), 100)
    pwh = float(df["high"].tail(lookback_week).max())
    pwl = float(df["low"].tail(lookback_week).min())

    return {
        "daily_open": round(do, 4),
        "previous_day_high": round(pdh, 4),
        "previous_day_low": round(pdl, 4),
        "previous_week_high": round(pwh, 4),
        "previous_week_low": round(pwl, 4),
        "pivot_point": round(pivot_point, 4),
        "resistance_1": round(r1, 4),
        "support_1": round(s1, 4),
        "resistance_2": round(r2, 4),
        "support_2": round(s2, 4)
    }

def compute_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes all standard quantitative indicators on OHLCV DataFrame:
    - EMAs: 9, 20, 50, 100, 200
    - SMAs: 20, 50, 200
    - RSI 14
    - ATR 14
    - MACD (12, 26, 9)
    - Stochastic (%K 14, %D 3)
    - Bollinger Bands (20, 2)
    - Keltner Channels (20, 14, 1.5)
    - VWAP
    """
    if len(df) < 5:
        return df

    data = df.copy()
    close_series = data["close"].astype(float)

    # 1. Exponential Moving Averages
    data["ema_9"] = calculate_ema(close_series, 9)
    data["ema_20"] = calculate_ema(close_series, 20)
    data["ema_50"] = calculate_ema(close_series, 50)
    data["ema_100"] = calculate_ema(close_series, 100) if len(data) >= 100 else np.nan
    data["ema_200"] = calculate_ema(close_series, 200) if len(data) >= 200 else np.nan

    # 2. Simple Moving Averages
    data["sma_20"] = calculate_sma(close_series, 20)
    data["sma_50"] = calculate_sma(close_series, 50)
    data["sma_200"] = calculate_sma(close_series, 200 if len(data) >= 200 else len(data))

    # 3. RSI 14
    data["rsi"] = calculate_rsi(close_series, period=14)

    # 4. MACD (12, 26, 9)
    macd_dict = calculate_macd(close_series, fast=12, slow=26, signal=9)
    data["macd"] = macd_dict["macd"]
    data["macd_signal"] = macd_dict["macd_signal"]
    data["macd_hist"] = macd_dict["macd_hist"]

    # 5. ATR 14
    data["atr"] = calculate_atr(data, period=14)

    # 6. Stochastic Oscillator (14, 3)
    stoch_dict = calculate_stochastic(data, period=14, smooth_k=3, smooth_d=3)
    data["stoch_k"] = stoch_dict["stoch_k"]
    data["stoch_d"] = stoch_dict["stoch_d"]

    # 7. Bollinger Bands (20, 2)
    bb_dict = calculate_bollinger_bands(close_series, period=20, num_std=2.0)
    data["bb_middle"] = bb_dict["bb_middle"]
    data["bb_upper"] = bb_dict["bb_upper"]
    data["bb_lower"] = bb_dict["bb_lower"]

    # 8. Keltner Channels (20, 14, 1.5)
    kc_dict = calculate_keltner_channels(data, ema_period=20, atr_period=14, multiplier=1.5)
    data["kc_middle"] = kc_dict["kc_middle"]
    data["kc_upper"] = kc_dict["kc_upper"]
    data["kc_lower"] = kc_dict["kc_lower"]

    # 9. VWAP
    data["vwap"] = calculate_vwap(data)

    return data

def extract_technical_summary(df_ind: pd.DataFrame) -> Dict[str, Any]:
    """Generates a structured technical snapshot for Agent 1."""
    if df_ind is None or df_ind.empty or len(df_ind) < 50:
        return {}

    required = {"close", "high", "low", "ema_20", "ema_50", "rsi", "atr", "macd_hist"}
    if not required.issubset(df_ind.columns):
        return {}

    latest = df_ind.iloc[-1]
    prev = df_ind.iloc[-2]

    curr_price = float(latest["close"])
    ema_20 = float(latest["ema_20"])
    ema_50 = float(latest["ema_50"])
    ema_200 = float(latest["ema_200"]) if "ema_200" in latest and pd.notna(latest["ema_200"]) else None
    rsi = float(latest["rsi"])
    atr = float(latest["atr"])
    macd_hist = float(latest["macd_hist"])
    prev_macd_hist = float(prev["macd_hist"])
    essential_values = [curr_price, ema_20, ema_50, rsi, atr, macd_hist, prev_macd_hist]
    if not all(np.isfinite(value) for value in essential_values) or curr_price <= 0 or atr <= 0:
        return {}

    # Trend calculation
    if curr_price > ema_20 > ema_50 and (curr_price > ema_200 if ema_200 is not None else True):
        trend = "STRONG BULLISH"
    elif curr_price > ema_50:
        trend = "BULLISH"
    elif curr_price < ema_20 < ema_50 and (curr_price < ema_200 if ema_200 is not None else True):
        trend = "STRONG BEARISH"
    elif curr_price < ema_50:
        trend = "BEARISH"
    else:
        trend = "NEUTRAL"

    # Swing levels (last 30 bars)
    recent = df_ind.tail(30)
    swing_high = float(recent["high"].max())
    swing_low = float(recent["low"].min())

    patterns = detect_candlestick_patterns(df_ind)

    return {
        "current_price": curr_price,
        "trend": trend,
        "ema_20": round(ema_20, 4),
        "ema_50": round(ema_50, 4),
        "ema_200": round(ema_200, 4) if ema_200 is not None else None,
        "rsi": round(rsi, 2),
        "atr": round(atr, 4),
        "macd_hist": round(macd_hist, 4),
        "macd_expanding": abs(macd_hist) > abs(prev_macd_hist),
        "swing_high": round(swing_high, 4),
        "swing_low": round(swing_low, 4),
        "bb_upper": round(float(latest["bb_upper"]), 4) if not np.isnan(latest["bb_upper"]) else curr_price,
        "bb_lower": round(float(latest["bb_lower"]), 4) if not np.isnan(latest["bb_lower"]) else curr_price,
        "candlestick_patterns": patterns
    }
