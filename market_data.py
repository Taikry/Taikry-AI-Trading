import requests
import pandas as pd
import datetime

# Interval mappings for Yahoo Finance chart API
TIMEFRAME_MAP = {
    "M5": ("5d", "5m"),
    "M15": ("5d", "15m"),
    "H1": ("1mo", "60m"),
    "H4": ("3mo", "1d"),   # YFinance does not support 4h directly; 60m or 1d can be used
    "D1": ("1y", "1d"),
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json"
}

def fetch_candles(ticker: str, timeframe: str = "M15") -> pd.DataFrame:
    """
    Fetches real-time and historical OHLCV candle data for a given ticker.
    Supports Crypto, Forex, and Commodities without requiring any API keys.
    """
    range_param, interval_param = TIMEFRAME_MAP.get(timeframe, ("5d", "15m"))
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range={range_param}&interval={interval_param}"

    try:
        response = requests.get(url, headers=HEADERS, timeout=8)
        response.raise_for_status()
        data = response.json()

        result = data["chart"]["result"][0]
        timestamps = result.get("timestamp", [])
        quote = result["indicators"]["quote"][0]

        df = pd.DataFrame({
            "timestamp": [datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc) for ts in timestamps],
            "open": quote.get("open", []),
            "high": quote.get("high", []),
            "low": quote.get("low", []),
            "close": quote.get("close", []),
            "volume": quote.get("volume", [])
        })

        # Clean NaN values
        df.dropna(subset=["open", "high", "low", "close"], inplace=True)
        df.reset_index(drop=True, inplace=True)

        return df
    except Exception as e:
        print(f"[MarketData Error] Failed to fetch candles for {ticker}: {e}")
        return pd.DataFrame()

def get_current_price(ticker: str) -> float:
    """Quick lookup for latest asset price."""
    df = fetch_candles(ticker, "M5")
    if not df.empty:
        return float(df["close"].iloc[-1])
    return 0.0
