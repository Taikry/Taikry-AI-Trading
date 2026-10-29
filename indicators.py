import pandas as pd
import numpy as np

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / (loss + 1e-9)
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
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

def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes technical indicators:
    - EMA: 9, 21, 50, 200
    - RSI: 14
    - MACD: (12, 26, 9)
    - ATR: 14
    - Bollinger Bands: (20, 2)
    """
    if df is None or df.empty or len(df) < 30:
        return df

    data = df.copy()

    # Exponential Moving Averages
    data["ema_9"] = data["close"].ewm(span=9, adjust=False).mean()
    data["ema_21"] = data["close"].ewm(span=21, adjust=False).mean()
    data["ema_50"] = data["close"].ewm(span=50, adjust=False).mean()
    if len(data) >= 200:
        data["ema_200"] = data["close"].ewm(span=200, adjust=False).mean()
    else:
        data["ema_200"] = np.nan

    # RSI
    data["rsi"] = calculate_rsi(data["close"], period=14)

    # MACD
    ema_fast = data["close"].ewm(span=12, adjust=False).mean()
    ema_slow = data["close"].ewm(span=26, adjust=False).mean()
    data["macd"] = ema_fast - ema_slow
    data["macd_signal"] = data["macd"].ewm(span=9, adjust=False).mean()
    data["macd_hist"] = data["macd"] - data["macd_signal"]

    # ATR (Volatility)
    data["atr"] = calculate_atr(data, period=14)

    # Bollinger Bands
    sma_20 = data["close"].rolling(window=20).mean()
    std_20 = data["close"].rolling(window=20).std()
    data["bb_upper"] = sma_20 + (std_20 * 2)
    data["bb_middle"] = sma_20
    data["bb_lower"] = sma_20 - (std_20 * 2)

    return data

def extract_market_summary(df_with_indicators: pd.DataFrame) -> dict:
    """Extracts latest indicator metrics into a concise dictionary for AI agents."""
    if df_with_indicators is None or df_with_indicators.empty or len(df_with_indicators) < 30:
        return {}

    required = {"close", "high", "low", "atr", "rsi", "ema_9", "ema_21", "ema_50", "macd_hist"}
    if not required.issubset(df_with_indicators.columns):
        return {}

    latest = df_with_indicators.iloc[-1]
    prev = df_with_indicators.iloc[-2]

    curr_price = float(latest["close"])
    atr_val = float(latest["atr"])
    rsi_val = float(latest["rsi"])

    ema_9 = float(latest["ema_9"])
    ema_21 = float(latest["ema_21"])
    ema_50 = float(latest["ema_50"])
    ema_200 = float(latest["ema_200"]) if "ema_200" in latest and pd.notna(latest["ema_200"]) else None

    macd_hist = float(latest["macd_hist"])
    prev_macd_hist = float(prev["macd_hist"])
    essential_values = [curr_price, atr_val, rsi_val, ema_9, ema_21, ema_50, macd_hist, prev_macd_hist]
    if not all(np.isfinite(value) for value in essential_values) or curr_price <= 0 or atr_val <= 0:
        return {}

    # Determine trend alignment
    bullish_ema = curr_price > ema_21 and ema_9 > ema_21
    bearish_ema = curr_price < ema_21 and ema_9 < ema_21

    trend = "BULLISH" if bullish_ema else ("BEARISH" if bearish_ema else "NEUTRAL")

    # Support / Resistance swing levels (last 30 candles)
    recent_window = df_with_indicators.tail(30)
    swing_high = float(recent_window["high"].max())
    swing_low = float(recent_window["low"].min())

    return {
        "current_price": curr_price,
        "rsi": round(rsi_val, 2),
        "trend": trend,
        "ema_9": round(ema_9, 4),
        "ema_21": round(ema_21, 4),
        "ema_50": round(ema_50, 4),
        "ema_200": round(ema_200, 4) if ema_200 is not None and np.isfinite(ema_200) else None,
        "macd_hist": round(macd_hist, 4),
        "macd_expanding": abs(macd_hist) > abs(prev_macd_hist),
        "atr": round(atr_val, 4),
        "swing_high": round(swing_high, 4),
        "swing_low": round(swing_low, 4),
        "bb_upper": round(float(latest["bb_upper"]), 4) if "bb_upper" in latest and pd.notna(latest["bb_upper"]) else None,
        "bb_lower": round(float(latest["bb_lower"]), 4) if "bb_lower" in latest and pd.notna(latest["bb_lower"]) else None,
    }
