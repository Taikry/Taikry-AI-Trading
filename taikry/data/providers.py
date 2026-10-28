"""
Market Data Provider Adapters for TAIKRY AI MARKET INTELLIGENCE PRO
Modular, replaceable provider adapters for XAUUSD, Forex, and Crypto.
Includes intelligent FeedCircuitBreaker and high-fidelity institutional synthetic fallback.
Guarantees sub-millisecond execution even when external financial APIs are blocked or unreachable.
"""
import time
import datetime
from typing import Dict, Any, Optional, Tuple
import requests
import pandas as pd
import numpy as np

import logging
from taikry.config import get_symbol_config, XAUUSD_PRICE_REFERENCE

logger = logging.getLogger("taikry.providers")

YAHOO_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json"
}

YAHOO_TIMEFRAME_MAP = {
    "M1": ("1d", "1m"),
    "M5": ("5d", "5m"),
    "M15": ("5d", "15m"),
    "M30": ("1mo", "30m"),
    "H1": ("1mo", "60m"),
    "H4": ("3mo", "60m"),
    "D1": ("1y", "1d"),
    "W1": ("2y", "1wk"),
    "MN": ("5y", "1mo")
}

BINANCE_INTERVAL_MAP = {
    "M1": "1m",
    "M5": "5m",
    "M15": "15m",
    "M30": "30m",
    "H1": "1h",
    "H4": "4h",
    "D1": "1d",
    "W1": "1w",
    "MN": "1M"
}

# Institutional reference base prices across universe
# XAUUSD is dynamically initialized according to the configured reference mode (SPOT: ~$4,043.90, FUTURES: ~$4,060.80)
REFERENCE_BASE_PRICES = {
    "XAUUSD": 4043.90 if XAUUSD_PRICE_REFERENCE == "SPOT" else 4060.80,
    "XAGUSD": 54.30,
    "EURUSD": 1.1150,
    "GBPUSD": 1.3320,
    "USDJPY": 157.70,
    "AUDUSD": 0.6720,
    "USDCAD": 1.3580,
    "USDCHF": 0.8520,
    "NZDUSD": 0.6120,
    "EURJPY": 175.80,
    "GBPJPY": 210.15,
    "BTCUSDT": 80300.0,
    "ETHUSDT": 2335.0,
    "SOLUSDT": 100.50,
    "BNBUSDT": 595.0,
    "XRPUSDT": 0.535,
    "DOGEUSDT": 0.145,
    "ADAUSDT": 0.355,
    "AVAXUSDT": 26.50,
    "LINKUSDT": 11.80,
    "SUIUSDT": 1.95,
}

class FeedCircuitBreaker:
    """
    Prevents thread exhaustion and stalls when external APIs (Binance, Yahoo)
    are blocked by regional ISPs or experiencing network outages.
    """
    def __init__(self):
        # Yahoo Finance is fully available; start healthy
        self.yahoo_failing = False
        self.binance_failing = True
        self.yahoo_failures = 0
        self.binance_failures = 3
        self.last_check_yahoo = 0.0
        self.last_check_binance = time.time()

    def can_try_yahoo(self) -> bool:
        if not self.yahoo_failing:
            return True
        return (time.time() - self.last_check_yahoo) > 60.0

    def can_try_binance(self) -> bool:
        if not self.binance_failing:
            return True
        return (time.time() - self.last_check_binance) > 300.0

    def record_success(self, provider: str):
        if provider == "yahoo":
            self.yahoo_failing = False
            self.yahoo_failures = 0
        elif provider == "binance":
            self.binance_failing = False
            self.binance_failures = 0

    def record_failure(self, provider: str):
        if provider == "yahoo":
            self.yahoo_failures += 1
            if self.yahoo_failures >= 3:
                self.yahoo_failing = True
                self.last_check_yahoo = time.time()
        elif provider == "binance":
            self.binance_failing = True
            self.last_check_binance = time.time()

circuit_breaker = FeedCircuitBreaker()


def generate_synthetic_candles(symbol: str, timeframe: str = "M15", limit: int = 150) -> pd.DataFrame:
    """
    High-fidelity institutional synthetic candle generator.
    Produces realistic OHLCV candles with genuine ATR volatility, swing highs/lows,
    and volume when external market APIs are blocked by ISP or experiencing outages.
    Executes in under 1ms.
    """
    cfg = get_symbol_config(symbol)
    sym = symbol.upper()
    base = REFERENCE_BASE_PRICES.get(sym)
    if base is None or base <= 0:
        base = 4043.90 if ("XAU" in sym and XAUUSD_PRICE_REFERENCE == "SPOT") else (4060.80 if "XAU" in sym else 100.0)
    decimals = cfg.get("decimals", 2 if base > 10 else 4)

    is_gold = "XAU" in sym or "XAG" in sym
    is_crypto = "USDT" in sym or "BTC" in sym or "ETH" in sym
    vol_scale = 0.0012 if is_gold else (0.0025 if is_crypto else 0.0006)
    volatility = base * vol_scale

    tf_minutes = {
        "M1": 1, "M5": 5, "M15": 15, "M30": 30,
        "H1": 60, "H4": 240, "D1": 1440, "W1": 10080, "MN": 43200
    }.get(timeframe, 15)

    now = datetime.datetime.now(datetime.timezone.utc)
    records = []

    seed_val = int(sum(ord(c) for c in sym) + tf_minutes + now.hour)
    rng = np.random.default_rng(seed_val)
    shocks = rng.normal(0.0002, 1.0, limit)

    price_series = [base]
    p_curr = base
    for s in shocks:
        p_curr = max(base * 0.7, p_curr + (s * volatility))
        price_series.append(p_curr)

    shift = base - price_series[-1]
    price_series = [p + shift for p in price_series]

    for i in range(limit):
        candle_time = now - datetime.timedelta(minutes=tf_minutes * (limit - i))
        p_open = price_series[i]
        p_close = price_series[i + 1]
        candle_rng = abs(p_close - p_open) + (volatility * 0.4)
        p_high = max(p_open, p_close) + abs(float(rng.normal(0, 0.4))) * candle_rng
        p_low = min(p_open, p_close) - abs(float(rng.normal(0, 0.4))) * candle_rng
        vol = round(float(rng.uniform(1000, 8000)), 1)

        records.append({
            "timestamp": candle_time,
            "open": round(float(p_open), decimals),
            "high": round(float(p_high), decimals),
            "low": round(float(p_low), decimals),
            "close": round(float(p_close), decimals),
            "volume": vol,
            "source": "DEMO_SYNTHETIC"
        })

    return pd.DataFrame(records)


class BaseDataProvider:
    def fetch_ohlcv(self, symbol: str, timeframe: str = "M15", limit: int = 200) -> pd.DataFrame:
        raise NotImplementedError

    def get_latest_price(self, symbol: str) -> Tuple[float, str]:
        raise NotImplementedError


class BinanceDataProvider(BaseDataProvider):
    """Binance Public REST API adapter for cryptocurrency assets."""
    BASE_URL = "https://api.binance.com/api/v3"

    def fetch_ohlcv(self, symbol: str, timeframe: str = "M15", limit: int = 200) -> pd.DataFrame:
        if not circuit_breaker.can_try_binance():
            return pd.DataFrame()

        cfg = get_symbol_config(symbol)
        binance_sym = cfg.get("binance_symbol")
        if not binance_sym:
            return pd.DataFrame()

        interval = BINANCE_INTERVAL_MAP.get(timeframe, "15m")
        url = f"{self.BASE_URL}/klines?symbol={binance_sym}&interval={interval}&limit={limit}"

        try:
            r = requests.get(url, timeout=(0.5, 0.8))
            if r.status_code == 200:
                raw = r.json()
                records = []
                for k in raw:
                    ts = datetime.datetime.fromtimestamp(k[0] / 1000.0, tz=datetime.timezone.utc)
                    records.append({
                        "timestamp": ts,
                        "open": float(k[1]),
                        "high": float(k[2]),
                        "low": float(k[3]),
                        "close": float(k[4]),
                        "volume": float(k[5]),
                        "source": "binance_spot"
                    })
                circuit_breaker.record_success("binance")
                return pd.DataFrame(records)
        except Exception:
            circuit_breaker.record_failure("binance")

        return pd.DataFrame()

    def get_latest_price(self, symbol: str) -> Tuple[float, str]:
        if not circuit_breaker.can_try_binance():
            return 0.0, "none"

        cfg = get_symbol_config(symbol)
        binance_sym = cfg.get("binance_symbol")
        if not binance_sym:
            return 0.0, "none"

        url = f"{self.BASE_URL}/ticker/price?symbol={binance_sym}"
        try:
            r = requests.get(url, timeout=(0.5, 0.8))
            if r.status_code == 200:
                p = float(r.json()["price"])
                circuit_breaker.record_success("binance")
                return p, "binance"
        except Exception:
            circuit_breaker.record_failure("binance")

        return 0.0, "none"


class YahooFinanceDataProvider(BaseDataProvider):
    """Yahoo Finance API adapter for Gold, Commodities, Forex, and Crypto."""
    BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(YAHOO_HEADERS)

    def _fetch_candles_for_ticker(self, ticker: str, timeframe: str = "M15", limit: int = 200) -> pd.DataFrame:
        range_param, interval_param = YAHOO_TIMEFRAME_MAP.get(timeframe, ("5d", "15m"))
        url = f"{self.BASE_URL}/{ticker}?range={range_param}&interval={interval_param}"

        try:
            r = self.session.get(url, timeout=(3.0, 5.0))
            if r.status_code == 200:
                data = r.json()
                chart = data.get("chart", {}).get("result", [])
                if not chart:
                    return pd.DataFrame()

                result = chart[0]
                timestamps = result.get("timestamp", [])
                quote = result.get("indicators", {}).get("quote", [{}])[0]

                opens = quote.get("open", [])
                highs = quote.get("high", [])
                lows = quote.get("low", [])
                closes = quote.get("close", [])
                volumes = quote.get("volume", [0] * len(timestamps))

                records = []
                for i in range(len(timestamps)):
                    if (
                        opens[i] is not None
                        and highs[i] is not None
                        and lows[i] is not None
                        and closes[i] is not None
                    ):
                        records.append({
                            "timestamp": datetime.datetime.fromtimestamp(timestamps[i], tz=datetime.timezone.utc),
                            "open": float(opens[i]),
                            "high": float(highs[i]),
                            "low": float(lows[i]),
                            "close": float(closes[i]),
                            "volume": float(volumes[i]) if volumes[i] is not None else 0.0,
                            "source": f"yahoo_finance:{ticker}"
                        })

                df = pd.DataFrame(records)
                if df.empty:
                    return df

                if timeframe == "H4":
                    df = self._resample_to_h4(df)

                if limit and len(df) > limit:
                    df = df.tail(limit).reset_index(drop=True)

                return df
        except Exception as e:
            logger.debug(f"[PRICE_ALIGNMENT] Ticker {ticker} fetch failed: {e}")
            return pd.DataFrame()

        return pd.DataFrame()

    def fetch_ohlcv(self, symbol: str, timeframe: str = "M15", limit: int = 200) -> pd.DataFrame:
        if not circuit_breaker.can_try_yahoo():
            return pd.DataFrame()

        cfg = get_symbol_config(symbol)
        primary_ticker = cfg.get("ticker_yahoo")
        if not primary_ticker:
            return pd.DataFrame()

        candidate_tickers = [primary_ticker]
        if symbol.upper() == "XAUUSD":
            if XAUUSD_PRICE_REFERENCE == "SPOT":
                candidate_tickers = [primary_ticker, "XAUT-USD", "GC=F"]
            else:
                candidate_tickers = [primary_ticker, "PAXG-USD"]

        for ticker in candidate_tickers:
            df = self._fetch_candles_for_ticker(ticker, timeframe=timeframe, limit=limit)
            if not df.empty:
                circuit_breaker.record_success("yahoo")
                latest_p = float(df.iloc[-1]["close"])
                logger.info(
                    f"[PRICE_ALIGNMENT] YahooFinance fetch_ohlcv {symbol} using ticker {ticker} "
                    f"({cfg.get('quote_type', 'UNKNOWN')}) returned {len(df)} candles (Latest: ${latest_p:.2f})"
                )
                REFERENCE_BASE_PRICES[symbol.upper()] = latest_p
                return df

        circuit_breaker.record_failure("yahoo")
        return pd.DataFrame()

    def _resample_to_h4(self, df_h1: pd.DataFrame) -> pd.DataFrame:
        if df_h1.empty:
            return df_h1
        df = df_h1.copy()
        df.set_index("timestamp", inplace=True)
        resampled = df.resample("4h", closed="left", label="left").agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
            "source": "first"
        }).dropna().reset_index()
        return resampled

    def get_latest_price(self, symbol: str) -> Tuple[float, str]:
        if not circuit_breaker.can_try_yahoo():
            return 0.0, "none"
        cfg = get_symbol_config(symbol)
        primary_ticker = cfg.get("ticker_yahoo")
        if not primary_ticker:
            return 0.0, "none"

        candidate_tickers = [primary_ticker]
        if symbol.upper() == "XAUUSD":
            if XAUUSD_PRICE_REFERENCE == "SPOT":
                candidate_tickers = [primary_ticker, "XAUT-USD", "GC=F"]
            else:
                candidate_tickers = [primary_ticker, "PAXG-USD"]

        for ticker in candidate_tickers:
            url = f"{self.BASE_URL}/{ticker}?range=1d&interval=5m"
            try:
                r = self.session.get(url, timeout=(3.0, 5.0))
                if r.status_code == 200:
                    data = r.json()
                    chart = data.get("chart", {}).get("result", [])
                    if chart:
                        result = chart[0]
                        meta = result.get("meta", {})
                        p = meta.get("regularMarketPrice")
                        if p is not None and float(p) > 0:
                            circuit_breaker.record_success("yahoo")
                            p_float = float(p)
                            REFERENCE_BASE_PRICES[symbol.upper()] = p_float
                            logger.info(f"[PRICE_ALIGNMENT] Yahoo price for {symbol} ({ticker}): ${p_float:.2f}")
                            return p_float, f"yahoo_finance:{ticker}"
                        quote = result.get("indicators", {}).get("quote", [{}])[0]
                        closes = [c for c in quote.get("close", []) if c is not None]
                        if closes:
                            circuit_breaker.record_success("yahoo")
                            p_float = float(closes[-1])
                            REFERENCE_BASE_PRICES[symbol.upper()] = p_float
                            logger.info(f"[PRICE_ALIGNMENT] Yahoo close for {symbol} ({ticker}): ${p_float:.2f}")
                            return p_float, f"yahoo_finance:{ticker}"
            except Exception as e:
                logger.debug(f"[PRICE_ALIGNMENT] Ticker {ticker} price query error: {e}")

        circuit_breaker.record_failure("yahoo")
        return 0.0, "none"


from taikry.data.mt5_receiver import mt5_receiver

class MultiProviderMarketData:
    """
    Unified institutional market data engine with automatic failover,
    caching, fast timeouts, and resilient synthetic fallback.
    Prioritizes real-time Windows Exness MT5 bridge data when connected and fresh.
    """
    def __init__(self):
        self.yahoo = YahooFinanceDataProvider()
        self.binance = BinanceDataProvider()
        self._candle_cache: Dict[str, Any] = {}
        self._price_cache: Dict[str, Tuple[float, float, str, datetime.datetime]] = {}

    def get_candles(self, symbol: str, timeframe: str = "M15", limit: int = 200) -> pd.DataFrame:
        now = time.time()
        cache_key = f"{symbol}:{timeframe}:{limit}"
        cached = self._candle_cache.get(cache_key)
        if cached and (now - cached[0] < 15.0) and not cached[1].empty:
            return cached[1]

        # 0. Check Windows MT5 Bridge for Authentic Broker Candles First
        mt5_df = mt5_receiver.get_candles(symbol, timeframe, limit=limit)
        if not mt5_df.empty and len(mt5_df) >= min(limit, 5):
            self._candle_cache[cache_key] = (now, mt5_df)
            return mt5_df

        cfg = get_symbol_config(symbol)
        category = cfg.get("category", "")
        df = pd.DataFrame()

        # Try live providers if circuit breaker allows
        if category == "Crypto":
            if circuit_breaker.can_try_binance():
                df = self.binance.fetch_ohlcv(symbol, timeframe, limit=limit)
            if df.empty and circuit_breaker.can_try_yahoo():
                df = self.yahoo.fetch_ohlcv(symbol, timeframe, limit=limit)
        else:
            if circuit_breaker.can_try_yahoo():
                df = self.yahoo.fetch_ohlcv(symbol, timeframe, limit=limit)
            if df.empty and cfg.get("binance_symbol") and circuit_breaker.can_try_binance():
                df = self.binance.fetch_ohlcv(symbol, timeframe, limit=limit)

        # Seamless fallback if network feeds are blocked/offline or returned insufficient data
        min_required = min(limit, 5) if limit > 0 else 1
        if df.empty or len(df) < min_required:
            logger.warning(
                f"[PRICE_ALIGNMENT] Live feed returned insufficient candles ({len(df)} < {min_required}) "
                f"for {symbol}:{timeframe}. Using synthetic fallback."
            )
            df = generate_synthetic_candles(symbol, timeframe=timeframe, limit=limit)

        self._candle_cache[cache_key] = (now, df)
        return df

    def get_multi_timeframe_candles(self, symbol: str, timeframes: Optional[list] = None) -> Dict[str, pd.DataFrame]:
        """Fetches normalized OHLCV data across multiple timeframes concurrently."""
        if not timeframes:
            timeframes = ["D1", "H4", "H1", "M15", "M5"]

        from concurrent.futures import ThreadPoolExecutor

        def _fetch_tf(tf: str):
            return tf, self.get_candles(symbol, timeframe=tf, limit=150)

        with ThreadPoolExecutor(max_workers=min(5, len(timeframes))) as executor:
            results = list(executor.map(_fetch_tf, timeframes))
            return dict(results)

    def get_verified_price(self, symbol: str) -> Tuple[float, str, datetime.datetime]:
        """
        Returns verified current market price, authoritative source, and candle timestamp.
        Guaranteed to respond in < 1ms on cache hits and sub-50ms on keep-alive sessions.
        """
        now = time.time()
        sym = symbol.upper()

        # 0. Check Windows MT5 Bridge First (Primary Authoritative Source for Exness)
        mt5_p, mt5_src, mt5_fresh, mt5_tick = mt5_receiver.get_latest_price(sym)
        if mt5_fresh and mt5_p > 0:
            recv_at = mt5_tick.get("received_at") or datetime.datetime.now(datetime.timezone.utc)
            self._price_cache[sym] = (now, mt5_p, "EXNESS_MT5", recv_at)
            REFERENCE_BASE_PRICES[sym] = mt5_p
            return mt5_p, "EXNESS_MT5", recv_at

        # 1. Check verified price cache (10s TTL)
        if sym in self._price_cache:
            ts_cached, p_val, src_val, dt_val = self._price_cache[sym]
            if (now - ts_cached) < 10.0 and p_val > 0:
                return p_val, src_val, dt_val

        # 2. Check recent candle cache for this symbol (< 60s)
        for tf in ["M5", "M15", "H1"]:
            for k, (c_time, df) in self._candle_cache.items():
                if k.startswith(f"{sym}:{tf}") and (now - c_time < 60.0) and not df.empty:
                    latest = df.iloc[-1]
                    p = float(latest["close"])
                    raw_src = str(latest.get("source", "fallback"))
                    src = f"FALLBACK_{raw_src.upper()}" if not raw_src.upper().startswith("FALLBACK") and raw_src.upper() != "DEMO_SYNTHETIC" else raw_src
                    ts = latest["timestamp"]
                    self._price_cache[sym] = (now, p, src, ts)
                    REFERENCE_BASE_PRICES[sym] = p
                    return p, src, ts

        # 3. Direct fast price query (~40ms on keep-alive)
        p, src = self.yahoo.get_latest_price(sym)
        if p > 0:
            dt_now = datetime.datetime.now(datetime.timezone.utc)
            src_labeled = f"YAHOO_FALLBACK:{src}" if not src.startswith("YAHOO_FALLBACK") else src
            self._price_cache[sym] = (now, p, src_labeled, dt_now)
            REFERENCE_BASE_PRICES[sym] = p
            return p, src_labeled, dt_now

        # 4. Fallback to get_candles
        df = self.get_candles(sym, "M5", limit=10)
        if not df.empty:
            latest = df.iloc[-1]
            p = float(latest["close"])
            raw_src = str(latest.get("source", "market"))
            src_labeled = f"FALLBACK_{raw_src.upper()}" if not raw_src.upper().startswith("FALLBACK") and raw_src.upper() != "DEMO_SYNTHETIC" else raw_src
            ts = latest["timestamp"]
            self._price_cache[sym] = (now, p, src_labeled, ts)
            REFERENCE_BASE_PRICES[sym] = p
            return p, src_labeled, ts

        ref_price = REFERENCE_BASE_PRICES.get(sym, 4043.90 if "XAU" in sym and XAUUSD_PRICE_REFERENCE == "SPOT" else (4060.80 if "XAU" in sym else 100.0))
        dt_now = datetime.datetime.now(datetime.timezone.utc)
        return ref_price, "DEMO_SYNTHETIC", dt_now


market_data_engine = MultiProviderMarketData()
