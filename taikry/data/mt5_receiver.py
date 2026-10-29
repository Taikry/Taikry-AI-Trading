"""
Exness MT5 Windows Bridge Data Receiver & Validator for ZYROX AI.
Provides in-memory caching, timestamp validation, data freshness checking,
stale-feed protection, and authentication for outbound Windows MT5 bridge connections.
"""

import hmac
import hashlib
import time
import datetime
import threading
import logging
from typing import Dict, Any, Optional, Tuple, List
import pandas as pd

from taikry.config import (
    MT5_BRIDGE_TOKEN,
    MT5_BRIDGE_ENABLED,
    MT5_BRIDGE_STALE_SECONDS
)

logger = logging.getLogger("zyrox.mt5_receiver")


class MT5BridgeReceiver:
    """
    Thread-safe store for real-time market data streamed from the user's
    Windows Exness MT5 bridge client into the ZYROX AI backend.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._ticks: Dict[str, Dict[str, Any]] = {}
        self._candles: Dict[str, pd.DataFrame] = {}
        self._seen_signatures: Dict[str, float] = {}
        self._bridge_meta: Dict[str, Any] = {
            "connected": False,
            "last_heartbeat_utc": None,
            "last_tick_utc": None,
            "broker": None,
            "server": None,
            "terminal_ping_ms": 0.0,
            "bridge_version": "2.1.0",
            "active_symbols": []
        }

    # -------------------------------------------------------------------------
    # 1. SECURITY & AUTHENTICATION
    # -------------------------------------------------------------------------

    def verify_auth_token(
        self,
        token: str,
        timestamp_header: Optional[str] = None,
        signature: Optional[str] = None,
        body_bytes: Optional[bytes] = None
    ) -> bool:
        """
        Validates the configured token, required timestamp, and HMAC-SHA256
        signature over timestamp + exact request body. Rejects repeated signatures.
        """
        if not MT5_BRIDGE_ENABLED:
            logger.warning("[MT5_BRIDGE] Inbound request rejected: MT5_BRIDGE_ENABLED is False")
            return False

        expected_token = MT5_BRIDGE_TOKEN
        if not expected_token or len(expected_token) < 32 or expected_token == "zyrox_mt5_bridge_secure_token_change_me":
            logger.warning("[MT5_BRIDGE] Inbound request rejected: MT5_BRIDGE_TOKEN is not configured on server")
            return False

        # Constant-time token comparison
        if not hmac.compare_digest(str(token).strip(), str(expected_token).strip()):
            logger.warning("[MT5_BRIDGE] Inbound request rejected: invalid auth token")
            return False

        # Timestamp drift validation (within 60 seconds)
        if not timestamp_header or not signature or body_bytes is None:
            logger.warning("[MT5_BRIDGE] Inbound request rejected: timestamp, signature, and body are required")
            return False
        try:
            req_ts = float(timestamp_header)
        except (ValueError, TypeError):
            return False
        now_ts = time.time()
        if abs(now_ts - req_ts) > 60.0:
            logger.warning(f"[MT5_BRIDGE] Inbound request rejected: timestamp drift {abs(now_ts - req_ts):.1f}s > 60s")
            return False

        signed_payload = timestamp_header.encode("utf-8") + b"." + body_bytes
        expected_sig = hmac.new(expected_token.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            logger.warning("[MT5_BRIDGE] Inbound request rejected: HMAC signature mismatch")
            return False

        with self._lock:
            self._seen_signatures = {sig: seen_at for sig, seen_at in self._seen_signatures.items() if now_ts - seen_at <= 120.0}
            if signature in self._seen_signatures:
                logger.warning("[MT5_BRIDGE] Inbound request rejected: repeated signed request")
                return False
            self._seen_signatures[signature] = now_ts

        return True

    # -------------------------------------------------------------------------
    # 2. INGESTION METHODS
    # -------------------------------------------------------------------------

    def record_heartbeat(self, meta: Dict[str, Any]) -> Dict[str, Any]:
        """Updates bridge connection metadata and terminal health."""
        with self._lock:
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            self._bridge_meta["connected"] = True
            self._bridge_meta["last_heartbeat_utc"] = now_utc.isoformat()
            self._bridge_meta["broker"] = meta.get("broker", self._bridge_meta["broker"])
            self._bridge_meta["server"] = meta.get("server", self._bridge_meta["server"])
            ping_value = meta.get("terminal_ping_ms")
            self._bridge_meta["terminal_ping_ms"] = float(ping_value) if ping_value is not None else None
            self._bridge_meta["bridge_version"] = meta.get("bridge_version", "2.1.0")
            if "active_symbols" in meta:
                self._bridge_meta["active_symbols"] = meta["active_symbols"]

            return self.get_status()

    def record_tick(self, symbol: str, tick_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Stores an authentic broker tick with bid, ask, spread, and broker timestamp.
        Canonicalizes broker symbol variants (e.g., XAUUSDm -> XAUUSD).
        """
        with self._lock:
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            canonical = self.normalize_symbol(symbol)

            bid = float(tick_data.get("bid", 0.0))
            ask = float(tick_data.get("ask", 0.0))
            last = float(tick_data.get("last", 0.0)) or ((bid + ask) / 2.0 if bid > 0 and ask > 0 else 0.0)
            spread = float(tick_data.get("spread", 0.0))
            digits = int(tick_data.get("digits", 2 if "XAU" in canonical else 5))
            broker_time = str(tick_data.get("time", now_utc.isoformat()))

            record = {
                "raw_symbol": symbol,
                "canonical_symbol": canonical,
                "bid": round(bid, digits),
                "ask": round(ask, digits),
                "price": round(last, digits),
                "spread": spread,
                "digits": digits,
                "broker_time": broker_time,
                "received_at": now_utc,
                "received_at_iso": now_utc.isoformat(),
                "source": "EXNESS_MT5",
                "is_fresh": True
            }

            self._ticks[canonical] = record
            self._bridge_meta["last_tick_utc"] = now_utc.isoformat()
            if canonical not in self._bridge_meta["active_symbols"]:
                self._bridge_meta["active_symbols"].append(canonical)

            return record

    def record_candles(
        self,
        symbol: str,
        timeframe: str,
        candles_list: List[Dict[str, Any]]
    ) -> int:
        """Stores historical/live OHLCV candles streamed from MT5."""
        if not candles_list:
            return 0

        with self._lock:
            canonical = self.normalize_symbol(symbol)
            key = f"{canonical}:{timeframe.upper()}"

            records = []
            for c in candles_list:
                ts = c.get("timestamp")
                if isinstance(ts, (int, float)):
                    dt = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
                elif isinstance(ts, str):
                    try:
                        dt = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    except Exception:
                        dt = datetime.datetime.now(datetime.timezone.utc)
                else:
                    dt = datetime.datetime.now(datetime.timezone.utc)

                records.append({
                    "timestamp": dt,
                    "open": float(c.get("open", 0.0)),
                    "high": float(c.get("high", 0.0)),
                    "low": float(c.get("low", 0.0)),
                    "close": float(c.get("close", 0.0)),
                    "volume": float(c.get("volume", 0.0)),
                    "source": "EXNESS_MT5"
                })

            df = pd.DataFrame(records)
            if not df.empty:
                df.sort_values("timestamp", inplace=True)
                df.drop_duplicates(subset=["timestamp"], keep="last", inplace=True)
                df.reset_index(drop=True, inplace=True)
                self._candles[key] = df

            return len(records)

    # -------------------------------------------------------------------------
    # 3. QUERY & FRESHNESS METHODS
    # -------------------------------------------------------------------------

    def normalize_symbol(self, symbol: str) -> str:
        """
        Normalizes broker-specific symbol variations to standard canonical symbols.
        E.g., XAUUSDm, XAUUSD.m, XAUUSD_i -> XAUUSD
        """
        s = symbol.upper().strip()
        if "XAU" in s or "GOLD" in s:
            return "XAUUSD"
        if "XAG" in s or "SILVER" in s:
            return "XAGUSD"
        if "EURUSD" in s:
            return "EURUSD"
        if "GBPUSD" in s:
            return "GBPUSD"
        if "USDJPY" in s:
            return "USDJPY"
        if "BTCUSD" in s or "BTCUSDT" in s:
            return "BTCUSDT"
        if "ETHUSD" in s or "ETHUSDT" in s:
            return "ETHUSDT"

        # General strip of trailing 'm', '.m', '_raw', etc.
        for suffix in [".M", "M", "_RAW", "_PRO", ".A", ".B"]:
            if s.endswith(suffix) and len(s) > len(suffix) + 3:
                return s[:-len(suffix)]

        return s

    def get_status(self) -> Dict[str, Any]:
        """
        Returns real-time connection status of the Windows MT5 bridge.
        Status values:
          - CONNECTED: Heartbeat / tick received within MT5_BRIDGE_STALE_SECONDS (30s)
          - STALE: Between 30s and 60s since last transmission
          - DISCONNECTED: >60s or no heartbeat received
        """
        with self._lock:
            now = datetime.datetime.now(datetime.timezone.utc)
            last_hb_str = self._bridge_meta.get("last_heartbeat_utc")
            last_tick_str = self._bridge_meta.get("last_tick_utc")

            # Determine most recent activity
            most_recent_dt = None
            for dt_str in [last_hb_str, last_tick_str]:
                if dt_str:
                    try:
                        d = datetime.datetime.fromisoformat(dt_str)
                        if most_recent_dt is None or d > most_recent_dt:
                            most_recent_dt = d
                    except Exception:
                        pass

            if most_recent_dt is None:
                status = "DISCONNECTED"
                seconds_ago = None
            else:
                seconds_ago = (now - most_recent_dt).total_seconds()
                if seconds_ago <= MT5_BRIDGE_STALE_SECONDS:
                    status = "CONNECTED"
                elif seconds_ago <= 60.0:
                    status = "STALE"
                else:
                    status = "DISCONNECTED"

            fresh_tick_symbols = []
            for symbol, tick in self._ticks.items():
                received_at = tick.get("received_at")
                if received_at is None:
                    continue
                if received_at.tzinfo is None:
                    received_at = received_at.replace(tzinfo=datetime.timezone.utc)
                bid = float(tick.get("bid", 0.0) or 0.0)
                ask = float(tick.get("ask", 0.0) or 0.0)
                if (now - received_at).total_seconds() <= MT5_BRIDGE_STALE_SECONDS and bid > 0 and ask >= bid:
                    fresh_tick_symbols.append(symbol)

            return {
                "status": status,
                "seconds_since_last_activity": round(seconds_ago, 1) if seconds_ago is not None else None,
                "broker": self._bridge_meta.get("broker"),
                "server": self._bridge_meta.get("server"),
                "terminal_ping_ms": self._bridge_meta.get("terminal_ping_ms", 0.0),
                "active_symbols": self._bridge_meta.get("active_symbols", []),
                "fresh_tick_symbols": sorted(fresh_tick_symbols),
                "last_heartbeat_utc": last_hb_str,
                "last_tick_utc": last_tick_str,
                "stale_threshold_seconds": MT5_BRIDGE_STALE_SECONDS,
                "is_active_for_signals": bool(fresh_tick_symbols)
            }

    def is_symbol_fresh(self, symbol: str) -> bool:
        """
        Returns True ONLY if an authentic tick was received within the stale threshold.
        Used by the AI signal engine to strictly block issuing signals on stale broker data.
        """
        canonical = self.normalize_symbol(symbol)
        with self._lock:
            tick = self._ticks.get(canonical)
            if not tick:
                return False

            now = datetime.datetime.now(datetime.timezone.utc)
            recv_at = tick.get("received_at")
            if not recv_at:
                return False

            if recv_at.tzinfo is None:
                recv_at = recv_at.replace(tzinfo=datetime.timezone.utc)

            age_seconds = (now - recv_at).total_seconds()
            return age_seconds <= MT5_BRIDGE_STALE_SECONDS

    def get_latest_price(self, symbol: str) -> Tuple[float, str, bool, Dict[str, Any]]:
        """
        Returns (price, source, is_fresh, full_tick_dict).
        If MT5 bridge has a fresh tick, returns (price, 'EXNESS_MT5', True, tick).
        If stale, returns (price, 'EXNESS_MT5_STALE', False, tick).
        If no MT5 tick exists, returns (0.0, 'none', False, {}).
        """
        canonical = self.normalize_symbol(symbol)
        with self._lock:
            tick = self._ticks.get(canonical)
            if not tick:
                return 0.0, "none", False, {}

            now = datetime.datetime.now(datetime.timezone.utc)
            recv_at = tick.get("received_at")
            age = (now - recv_at).total_seconds() if recv_at else 9999.0
            is_fresh = age <= MT5_BRIDGE_STALE_SECONDS
            source = "EXNESS_MT5" if is_fresh else "EXNESS_MT5_STALE"

            return float(tick["price"]), source, is_fresh, tick

    def get_candles(self, symbol: str, timeframe: str = "M15", limit: int = 200) -> pd.DataFrame:
        """Returns cached MT5 candles if available and populated."""
        canonical = self.normalize_symbol(symbol)
        key = f"{canonical}:{timeframe.upper()}"
        with self._lock:
            df = self._candles.get(key)
            if df is not None and not df.empty:
                if limit and len(df) > limit:
                    return df.tail(limit).reset_index(drop=True)
                return df.copy()
            return pd.DataFrame()


# Global singleton instance
mt5_receiver = MT5BridgeReceiver()
