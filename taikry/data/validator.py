"""
Market Data Validator for TAIKRY AI MARKET INTELLIGENCE PRO
Ensures data integrity, detects anomalies, handles weekend closures, and validates candle timestamps.
"""
import datetime
from typing import Dict, Any, Tuple
import pandas as pd
from taikry.config import get_symbol_config

def is_market_open(symbol: str, check_time: datetime.datetime = None) -> Tuple[bool, str]:
    """
    Determines if the market for a given symbol is currently open.
    - Crypto trades 24/7/365.
    - Forex & Metals (Gold) close from Friday 22:00 UTC to Sunday 21:00 UTC.
    """
    cfg = get_symbol_config(symbol)
    category = cfg.get("category")

    if category == "Crypto":
        return True, "24/7 Market Active"

    if check_time is None:
        check_time = datetime.datetime.now(datetime.timezone.utc)
    elif check_time.tzinfo is None:
        check_time = check_time.replace(tzinfo=datetime.timezone.utc)

    # Day of week: Monday is 0, Sunday is 6
    weekday = check_time.weekday()
    hour = check_time.hour

    # Friday after 22:00 UTC -> Market closed
    if weekday == 4 and hour >= 22:
        return False, "Weekend Closure (Friday close)"
    # Saturday all day -> Closed
    if weekday == 5:
        return False, "Weekend Closure (Saturday)"
    # Sunday before 21:00 UTC -> Closed
    if weekday == 6 and hour < 21:
        return False, "Weekend Closure (Sunday pre-open)"

    return True, "Regular Market Hours"

def validate_dataframe(df: pd.DataFrame, min_bars: int = 30) -> Dict[str, Any]:
    """
    Comprehensive OHLCV data validation.
    Checks:
    - Minimum row count
    - Required columns
    - Price sanity: high >= max(open, close), low <= min(open, close)
    - No NaNs or infinite values
    """
    if df is None or df.empty:
        return {"valid": False, "reason": "DataFrame is empty or None", "rows": 0}

    if len(df) < min_bars:
        return {"valid": False, "reason": f"Insufficient bars ({len(df)} < {min_bars})", "rows": len(df)}

    req_cols = ["timestamp", "open", "high", "low", "close"]
    for col in req_cols:
        if col not in df.columns:
            return {"valid": False, "reason": f"Missing required column '{col}'", "rows": len(df)}

    # Check for NaNs
    if df[req_cols].isna().any().any():
        return {"valid": False, "reason": "DataFrame contains NaN values in OHLCV columns", "rows": len(df)}

    # Sanity checks: high should be >= open, close, low
    invalid_high = (df["high"] < df["low"]) | (df["high"] < df["open"]) | (df["high"] < df["close"])
    if invalid_high.any():
        return {"valid": False, "reason": "High price is lower than Open/Close/Low in one or more candles", "rows": len(df)}

    invalid_low = (df["low"] > df["open"]) | (df["low"] > df["close"])
    if invalid_low.any():
        return {"valid": False, "reason": "Low price is higher than Open/Close in one or more candles", "rows": len(df)}

    return {"valid": True, "reason": "Passes all integrity checks", "rows": len(df)}

def check_data_freshness(symbol: str, latest_timestamp: datetime.datetime, timeframe: str = "M15") -> Dict[str, Any]:
    """
    Checks if the latest candle timestamp is fresh or stale.
    Accounts for weekend closures to prevent false alert triggers on non-crypto assets.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    if isinstance(latest_timestamp, str):
        try:
            latest_timestamp = datetime.datetime.fromisoformat(latest_timestamp.replace("Z", "+00:00"))
        except Exception:
            latest_timestamp = None
    elif latest_timestamp is None:
        latest_timestamp = None

    if latest_timestamp is None:
        return {
            "fresh": False,
            "status": "UNKNOWN_TIMESTAMP",
            "age_minutes": None,
            "note": "Timestamp is missing or invalid; data freshness cannot be verified."
        }

    if latest_timestamp.tzinfo is None:
        latest_timestamp = latest_timestamp.replace(tzinfo=datetime.timezone.utc)

    age_minutes = (now - latest_timestamp).total_seconds() / 60.0
    open_now, open_status = is_market_open(symbol, now)

    # Max acceptable lag in minutes based on timeframe
    tf_lag_map = {
        "M1": 5,
        "M5": 20,
        "M15": 45,
        "M30": 90,
        "H1": 150,
        "H4": 400,
        "D1": 2000
    }
    max_lag = tf_lag_map.get(timeframe, 45)

    if not open_now:
        return {
            "fresh": True,
            "status": "WEEKEND_CLOSED",
            "age_minutes": round(age_minutes, 1),
            "note": f"Market closed ({open_status}). Preserving latest verified settlement candle."
        }

    if age_minutes <= max_lag:
        return {
            "fresh": True,
            "status": "LIVE_FRESH",
            "age_minutes": round(age_minutes, 1),
            "note": "Market data is up-to-date"
        }
    else:
        return {
            "fresh": False,
            "status": "STALE_DATA",
            "age_minutes": round(age_minutes, 1),
            "note": f"Data delayed by {round(age_minutes, 1)} minutes (threshold {max_lag}m)"
        }
