"""
Market Data Provider Adapters for TAIKRY AI MARKET INTELLIGENCE PRO
Modular, replaceable provider adapters for XAUUSD, Forex, and Crypto.
Includes a feed circuit breaker and an explicitly labeled demo-candle generator.
Live market data is reported unavailable when no verified provider responds.
"""
import time
import datetime
import threading
import math
from typing import Dict, Any, Optional, Tuple
import requests
import pandas as pd
import numpy as np

import logging
from taikry.config import (
    get_symbol_config,
    XAUUSD_PRICE_REFERENCE,
    OANDA_API_TOKEN,
    OANDA_ACCOUNT_ID,
    OANDA_ENV,
)

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

# Stores only prices received from a provider during this process. It is not seeded
# with reference values, so it cannot be mistaken for a live quote.
REFERENCE_BASE_PRICES: Dict[str, float] = {}

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

    def get_status(self) -> Dict[str, Any]:
        now = time.time()
        return {
            "yahoo": {
                "available_for_probe": self.can_try_yahoo(),
                "failing": self.yahoo_failing,
                "recent_failures": self.yahoo_failures,
                "retry_in_seconds": max(0, int(60 - (now - self.last_check_yahoo))) if self.yahoo_failing else 0,
            },
            "binance": {
                "available_for_probe": self.can_try_binance(),
                "failing": self.binance_failing,
                "recent_failures": self.binance_failures,
                "retry_in_seconds": max(0, int(300 - (now - self.last_check_binance))) if self.binance_failing else 0,
            },
        }

circuit_breaker = FeedCircuitBreaker()


def generate_synthetic_candles(symbol: str, timeframe: str = "M15", limit: int = 150) -> pd.DataFrame:
    """
    Generates clearly labeled demo candles from a previously observed provider price.
    This function is not used as an automatic market-data fallback.
    """
    cfg = get_symbol_config(symbol)
    sym = symbol.upper()
    base = REFERENCE_BASE_PRICES.get(sym)
    if base is None or base <= 0:
        logger.warning("Cannot generate demo candles for %s without a previously observed provider price.", sym)
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume", "source"])
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


class OandaDataProvider(BaseDataProvider):
    """Read-only OANDA v20 prices and candles with sanitized failures."""

    BASE_URLS = {
        "practice": "https://api-fxpractice.oanda.com",
        "live": "https://api-fxtrade.oanda.com",
    }
    GRANULARITIES = {"M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1", "MN"}

    def __init__(self, api_token: str = OANDA_API_TOKEN, account_id: str = OANDA_ACCOUNT_ID, environment: str = OANDA_ENV):
        self.api_token = api_token.strip()
        self.account_id = account_id.strip()
        self.environment = environment.strip().lower()
        self.session = requests.Session()
        if self.api_token:
            self.session.headers.update({
                "Authorization": f"Bearer {self.api_token}",
                "Accept": "application/json",
            })
        self._lock = threading.RLock()
        self._resolved_base_url: Optional[str] = None
        self._resolved_account_id: Optional[str] = None
        self._account_check_at = 0.0
        self._account_check_failed = False
        self._quote_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
        self._instrument_cache: Tuple[float, list[Dict[str, Any]]] = (0.0, [])

    @property
    def configured(self) -> bool:
        return bool(self.api_token)

    @staticmethod
    def instrument_for(symbol: str) -> Optional[str]:
        """Maps canonical app symbols to OANDA instrument notation."""
        sym = str(symbol or "").upper().replace("/", "_").replace("-", "_").strip()
        if "_" in sym:
            return sym
        if sym.endswith("USDT"):
            return f"{sym[:-4]}_USD"
        if len(sym) == 6 and sym.isalpha():
            return f"{sym[:3]}_{sym[3:]}"
        return None

    def _environment_candidates(self) -> list[str]:
        if self.environment in self.BASE_URLS:
            return [self.environment]
        return ["practice", "live"]

    def _resolve_account(self) -> Tuple[Optional[str], Optional[str]]:
        if not self.configured:
            return None, None
        with self._lock:
            if self._resolved_base_url and self._resolved_account_id:
                return self._resolved_base_url, self._resolved_account_id
            if self._account_check_failed and time.monotonic() - self._account_check_at < 60.0:
                return None, None

            for environment in self._environment_candidates():
                base_url = self.BASE_URLS[environment]
                # An explicit environment and account ID do not need a discovery call.
                if self.account_id and self.environment in self.BASE_URLS:
                    self._resolved_base_url = base_url
                    self._resolved_account_id = self.account_id
                    return base_url, self.account_id
                try:
                    response = self.session.get(f"{base_url}/v3/accounts", timeout=(2.0, 4.0))
                    if response.status_code != 200:
                        continue
                    accounts = response.json().get("accounts", [])
                    account_ids = [str(item.get("id", "")) for item in accounts if item.get("id")]
                    if self.account_id and self.account_id not in account_ids:
                        continue
                    selected_id = self.account_id or (account_ids[0] if account_ids else "")
                    if selected_id:
                        self._resolved_base_url = base_url
                        self._resolved_account_id = selected_id
                        self._account_check_failed = False
                        return base_url, selected_id
                except Exception:
                    # Do not log request details or headers, which can contain credentials.
                    continue

            self._account_check_at = time.monotonic()
            self._account_check_failed = True
            logger.warning("OANDA v20 account discovery failed; OANDA data is unavailable until the next retry window.")
            return None, None

    @staticmethod
    def _parse_timestamp(value: Any) -> Optional[datetime.datetime]:
        if not value:
            return None
        try:
            result = datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if result.tzinfo is None:
                result = result.replace(tzinfo=datetime.timezone.utc)
            return result.astimezone(datetime.timezone.utc)
        except (TypeError, ValueError):
            return None

    def get_latest_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        instrument = self.instrument_for(symbol)
        if not instrument:
            return None
        now = time.monotonic()
        cached = self._quote_cache.get(instrument)
        if cached and now - cached[0] < 2.0:
            return dict(cached[1])

        base_url, account_id = self._resolve_account()
        if not base_url or not account_id:
            return None
        try:
            response = self.session.get(
                f"{base_url}/v3/accounts/{account_id}/pricing",
                params={"instruments": instrument},
                timeout=(2.0, 4.0),
            )
            if response.status_code != 200:
                return None
            prices = response.json().get("prices", [])
            item = next((entry for entry in prices if entry.get("instrument") == instrument), None)
            if not item or item.get("status") != "tradeable":
                return None
            bids = item.get("bids") or []
            asks = item.get("asks") or []
            if not bids or not asks:
                return None
            bid = float(bids[0].get("price", 0))
            ask = float(asks[0].get("price", 0))
            timestamp = self._parse_timestamp(item.get("time"))
            if bid <= 0 or ask <= bid or timestamp is None:
                return None
            age = (datetime.datetime.now(datetime.timezone.utc) - timestamp).total_seconds()
            if age < -5 or age > 60:
                return None
            quote = {
                "symbol": str(symbol).upper(),
                "instrument": instrument,
                "bid": bid,
                "ask": ask,
                "price": (bid + ask) / 2.0,
                "spread": ask - bid,
                "timestamp": timestamp,
                "source": "OANDA_V20",
                "provider": "OANDA",
            }
            self._quote_cache[instrument] = (now, quote)
            return dict(quote)
        except Exception:
            logger.debug("OANDA v20 price request failed for %s.", instrument)
            return None

    def discover_instruments(self, cache_seconds: int = 21600) -> list[Dict[str, Any]]:
        """Return account-supported OANDA instruments using a bounded six-hour cache."""
        cached_at, cached_items = self._instrument_cache
        now = time.monotonic()
        if cached_at > 0 and now - cached_at < cache_seconds:
            return [dict(item) for item in cached_items]
        base_url, account_id = self._resolve_account()
        if not base_url or not account_id:
            return []
        try:
            response = self.session.get(
                f"{base_url}/v3/accounts/{account_id}/instruments",
                timeout=(2.0, 6.0),
            )
            if response.status_code != 200:
                return []
            items = response.json().get("instruments", [])
            normalized = [
                {
                    "name": str(item.get("name") or "").upper(),
                    "display_name": str(item.get("displayName") or item.get("name") or ""),
                    "type": str(item.get("type") or ""),
                }
                for item in items
                if item.get("name")
            ]
            self._instrument_cache = (now, normalized)
            return [dict(item) for item in normalized]
        except Exception:
            logger.info("OANDA instrument discovery is unavailable; retaining the cached registry.")
            return [dict(item) for item in cached_items]

    def fetch_ohlcv(self, symbol: str, timeframe: str = "M15", limit: int = 200) -> pd.DataFrame:
        instrument = self.instrument_for(symbol)
        granularity = str(timeframe).upper()
        if not instrument or granularity not in self.GRANULARITIES or limit <= 0:
            return pd.DataFrame()
        base_url, _account_id = self._resolve_account()
        if not base_url:
            return pd.DataFrame()
        try:
            response = self.session.get(
                f"{base_url}/v3/instruments/{instrument}/candles",
                params={"granularity": granularity, "count": min(int(limit), 5000), "price": "M"},
                timeout=(2.0, 5.0),
            )
            if response.status_code != 200:
                return pd.DataFrame()
            candles = response.json().get("candles", [])
            records = []
            for candle in candles:
                mid = candle.get("mid") or {}
                timestamp = self._parse_timestamp(candle.get("time"))
                if not timestamp or not all(mid.get(k) is not None for k in ("o", "h", "l", "c")):
                    continue
                records.append({
                    "timestamp": timestamp,
                    "open": float(mid["o"]),
                    "high": float(mid["h"]),
                    "low": float(mid["l"]),
                    "close": float(mid["c"]),
                    "volume": float(candle.get("volume", 0.0)),
                    "source": f"oanda_v20:{instrument}",
                })
            return pd.DataFrame(records)
        except Exception:
            logger.debug("OANDA v20 candle request failed for %s.", instrument)
            return pd.DataFrame()

    def get_latest_price(self, symbol: str) -> Tuple[float, str]:
        quote = self.get_latest_quote(symbol)
        return (float(quote["price"]), "oanda_v20") if quote else (0.0, "none")


class BinanceDataProvider(BaseDataProvider):
    """Binance Public REST API adapter for cryptocurrency assets."""
    BASE_URL = "https://api.binance.com/api/v3"

    def __init__(self):
        self._quote_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
        self._quote_lock = threading.Lock()
        self._discovery_cache: Tuple[float, list[Dict[str, Any]]] = (0.0, [])

    def discover_spot_symbols(self, cache_seconds: int = 21600) -> list[Dict[str, Any]]:
        """List tradable USDT spot pairs from Binance, cached to avoid search-time calls."""
        cached_at, cached_items = self._discovery_cache
        now = time.monotonic()
        if cached_at > 0 and now - cached_at < cache_seconds:
            return [dict(item) for item in cached_items]
        try:
            response = requests.get(f"{self.BASE_URL}/exchangeInfo", timeout=(2.0, 6.0))
            if response.status_code != 200:
                return [dict(item) for item in cached_items]
            records = response.json().get("symbols", [])
            normalized = []
            for item in records:
                symbol = str(item.get("symbol") or "").upper()
                if (
                    not symbol
                    or item.get("status") != "TRADING"
                    or item.get("quoteAsset") != "USDT"
                    or item.get("isSpotTradingAllowed") is False
                ):
                    continue
                normalized.append({
                    "symbol": symbol,
                    "base_asset": str(item.get("baseAsset") or "").upper(),
                    "quote_asset": "USDT",
                })
            self._discovery_cache = (now, normalized)
            return [dict(item) for item in normalized]
        except Exception:
            logger.info("Binance symbol discovery is unavailable; retaining the cached registry.")
            return [dict(item) for item in cached_items]

    def get_latest_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Return a current public spot bid/ask quote for supported crypto pairs."""
        if not circuit_breaker.can_try_binance():
            return None
        cfg = get_symbol_config(symbol)
        binance_sym = cfg.get("binance_symbol")
        if not binance_sym:
            return None

        now = time.monotonic()
        with self._quote_lock:
            cached = self._quote_cache.get(binance_sym)
            if cached and now - cached[0] < 1.0:
                return dict(cached[1])
        try:
            response = requests.get(
                f"{self.BASE_URL}/ticker/bookTicker",
                params={"symbol": binance_sym},
                timeout=(0.5, 0.8),
            )
            if response.status_code != 200:
                circuit_breaker.record_failure("binance")
                return None
            result = response.json()
            bid = float(result.get("bidPrice", 0.0))
            ask = float(result.get("askPrice", 0.0))
            if not math.isfinite(bid) or not math.isfinite(ask) or bid <= 0 or ask <= bid:
                circuit_breaker.record_failure("binance")
                return None
            quote = {
                "symbol": str(symbol).upper(),
                "instrument": binance_sym,
                "bid": bid,
                "ask": ask,
                "price": (bid + ask) / 2.0,
                "spread": ask - bid,
                "timestamp": datetime.datetime.now(datetime.timezone.utc),
                "source": "BINANCE_SPOT",
                "provider": "Binance Spot",
            }
            circuit_breaker.record_success("binance")
            with self._quote_lock:
                self._quote_cache[binance_sym] = (now, quote)
            return dict(quote)
        except Exception:
            circuit_breaker.record_failure("binance")
            return None

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

    def get_latest_price(self, symbol: str) -> Tuple[float, str, Optional[datetime.datetime]]:
        if not circuit_breaker.can_try_yahoo():
            return 0.0, "none", None
        cfg = get_symbol_config(symbol)
        primary_ticker = cfg.get("ticker_yahoo")
        if not primary_ticker:
            return 0.0, "none", None

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
                        quote_ts = None
                        market_time = meta.get("regularMarketTime")
                        if market_time:
                            quote_ts = datetime.datetime.fromtimestamp(float(market_time), tz=datetime.timezone.utc)
                        p = meta.get("regularMarketPrice")
                        if p is not None and float(p) > 0 and quote_ts is not None:
                            circuit_breaker.record_success("yahoo")
                            p_float = float(p)
                            REFERENCE_BASE_PRICES[symbol.upper()] = p_float
                            logger.info(f"[PRICE_ALIGNMENT] Yahoo price for {symbol} ({ticker}): ${p_float:.2f}")
                            return p_float, f"yahoo_finance:{ticker}", quote_ts
                        quote = result.get("indicators", {}).get("quote", [{}])[0]
                        closes = quote.get("close", [])
                        timestamps = result.get("timestamp", [])
                        valid_indices = [i for i, close in enumerate(closes) if close is not None and i < len(timestamps)]
                        if valid_indices:
                            circuit_breaker.record_success("yahoo")
                            idx = valid_indices[-1]
                            p_float = float(closes[idx])
                            quote_ts = datetime.datetime.fromtimestamp(float(timestamps[idx]), tz=datetime.timezone.utc)
                            REFERENCE_BASE_PRICES[symbol.upper()] = p_float
                            logger.info(f"[PRICE_ALIGNMENT] Yahoo close for {symbol} ({ticker}): ${p_float:.2f}")
                            return p_float, f"yahoo_finance:{ticker}", quote_ts
            except Exception as e:
                logger.debug(f"[PRICE_ALIGNMENT] Ticker {ticker} price query error: {e}")

        circuit_breaker.record_failure("yahoo")
        return 0.0, "none", None


from taikry.data.mt5_receiver import mt5_receiver

class MultiProviderMarketData:
    """
    Unified institutional market data engine with automatic failover,
    and caching. Missing provider data remains unavailable instead of being synthesized.
    Prioritizes real-time Windows Exness MT5 bridge data when connected and fresh.
    """
    def __init__(self):
        self.yahoo = YahooFinanceDataProvider()
        self.binance = BinanceDataProvider()
        self.oanda = OandaDataProvider()
        self._candle_cache: Dict[str, Any] = {}
        self._price_cache: Dict[str, Tuple[float, float, str, Optional[datetime.datetime]]] = {}

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

        # Prefer account-authorized OANDA midpoint candles when its v20 key is configured.
        if self.oanda.configured:
            oanda_df = self.oanda.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            min_required = min(limit, 5) if limit > 0 else 1
            if not oanda_df.empty and len(oanda_df) >= min_required:
                self._candle_cache[cache_key] = (now, oanda_df)
                REFERENCE_BASE_PRICES[symbol.upper()] = float(oanda_df.iloc[-1]["close"])
                return oanda_df

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

        # Do not replace missing live candles with synthetic data. Analysis callers
        # can then distinguish an unavailable feed from a genuine market snapshot.
        min_required = min(limit, 5) if limit > 0 else 1
        if df.empty or len(df) < min_required:
            logger.warning(
                f"[PRICE_ALIGNMENT] Live feed returned insufficient candles ({len(df)} < {min_required}) "
                f"for {symbol}:{timeframe}. Returning unavailable data."
            )
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume", "source"])

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

    def get_verified_price(self, symbol: str) -> Tuple[float, str, Optional[datetime.datetime]]:
        """
        Returns the latest provider quote or candle price with its timestamp.
        Returns price 0.0, source UNAVAILABLE, and no timestamp when no quote is verified.
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

        # A current OANDA bid/ask quote is stronger than cached candle or fallback prices.
        oanda_quote = self.oanda.get_latest_quote(sym)
        if oanda_quote:
            oanda_price = float(oanda_quote["price"])
            oanda_ts = oanda_quote["timestamp"]
            self._price_cache[sym] = (now, oanda_price, "OANDA_V20", oanda_ts)
            REFERENCE_BASE_PRICES[sym] = oanda_price
            return oanda_price, "OANDA_V20", oanda_ts

        # 1. Check verified price cache (10s TTL)
        if sym in self._price_cache:
            ts_cached, p_val, src_val, dt_val = self._price_cache[sym]
            if (now - ts_cached) < 10.0 and p_val > 0:
                return p_val, src_val, dt_val

        # For crypto, fetch a current Binance ticker before using a candle close
        # or Yahoo fallback so the quote corresponds to the supported spot feed.
        if get_symbol_config(sym).get("category") == "Crypto" and circuit_breaker.can_try_binance():
            binance_price, binance_source = self.binance.get_latest_price(sym)
            if binance_price > 0:
                quote_received_at = datetime.datetime.now(datetime.timezone.utc)
                source = "BINANCE_SPOT" if binance_source == "binance" else binance_source.upper()
                self._price_cache[sym] = (now, binance_price, source, quote_received_at)
                REFERENCE_BASE_PRICES[sym] = binance_price
                return binance_price, source, quote_received_at

        # 2. Check recent candle cache for this symbol (< 60s)
        for tf in ["M5", "M15", "H1"]:
            for k, (c_time, df) in self._candle_cache.items():
                if k.startswith(f"{sym}:{tf}") and (now - c_time < 60.0) and not df.empty:
                    latest = df.iloc[-1]
                    p = float(latest["close"])
                    raw_src = str(latest.get("source", "fallback"))
                    if "DEMO_SYNTHETIC" in raw_src.upper():
                        continue
                    src = f"FALLBACK_{raw_src.upper()}" if not raw_src.upper().startswith("FALLBACK") and raw_src.upper() != "DEMO_SYNTHETIC" else raw_src
                    ts = latest["timestamp"]
                    self._price_cache[sym] = (now, p, src, ts)
                    REFERENCE_BASE_PRICES[sym] = p
                    return p, src, ts

        # 3. Direct fast price query (~40ms on keep-alive)
        p, src, quote_ts = self.yahoo.get_latest_price(sym)
        if p > 0 and quote_ts is not None:
            src_labeled = f"YAHOO_FALLBACK:{src}" if not src.startswith("YAHOO_FALLBACK") else src
            self._price_cache[sym] = (now, p, src_labeled, quote_ts)
            REFERENCE_BASE_PRICES[sym] = p
            return p, src_labeled, quote_ts

        # 4. Fallback to get_candles
        df = self.get_candles(sym, "M5", limit=10)
        if not df.empty:
            latest = df.iloc[-1]
            p = float(latest["close"])
            raw_src = str(latest.get("source", "market"))
            if "DEMO_SYNTHETIC" not in raw_src.upper():
                src_labeled = f"FALLBACK_{raw_src.upper()}" if not raw_src.upper().startswith("FALLBACK") else raw_src
                ts = latest["timestamp"]
                self._price_cache[sym] = (now, p, src_labeled, ts)
                REFERENCE_BASE_PRICES[sym] = p
                return p, src_labeled, ts

        return 0.0, "UNAVAILABLE", None

    def get_verified_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Returns a fresh bid/ask quote from MT5 or OANDA, never a candle midpoint."""
        sym = str(symbol or "").upper()
        mt5_price, mt5_source, mt5_fresh, mt5_tick = mt5_receiver.get_latest_price(sym)
        if mt5_fresh and mt5_price > 0:
            try:
                bid = float(mt5_tick.get("bid", 0.0))
                ask = float(mt5_tick.get("ask", 0.0))
                if bid > 0 and ask > bid:
                    return {
                        "symbol": sym,
                        "price": (bid + ask) / 2.0,
                        "bid": bid,
                        "ask": ask,
                        "spread": ask - bid,
                        "timestamp": mt5_tick.get("received_at") or datetime.datetime.now(datetime.timezone.utc),
                        "source": "EXNESS_MT5",
                        "provider": mt5_tick.get("broker") or "Exness MT5",
                    }
            except (TypeError, ValueError):
                pass

        quote = self.oanda.get_latest_quote(sym)
        if quote:
            return quote
        if get_symbol_config(sym).get("category") == "Crypto":
            quote = self.binance.get_latest_quote(sym)
            if quote:
                return quote
        return None


market_data_engine = MultiProviderMarketData()
