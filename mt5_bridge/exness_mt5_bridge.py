"""
===============================================================================
ZYROX AI — Windows Exness MT5 Secure Market Data Bridge Client
===============================================================================
Tagline: Read the Market. Own Your Edge.
Architecture: Outbound HTTPS Client from Windows MT5 -> ZYROX AI Backend API.
Security: Authenticated via X-Bridge-Token + HMAC-SHA256 + Replay Protection.
Permissions: READ-ONLY market data streaming (Ticks, Bid/Ask/Spread, OHLC Candles).
             Strictly zero order execution capability.
===============================================================================
"""

import sys
import os
import time
import json
import hmac
import hashlib
import datetime
import argparse
import urllib.parse
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional

# Graceful MetaTrader 5 import with guidance
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False


CANDIDATE_GOLD_SYMBOLS = [
    "XAUUSD", "XAUUSDm", "XAUUSD.m", "XAUUSD_i", "XAUUSDpro", "GOLD", "GOLDm"
]

DEFAULT_FOREX_CRYPTO_SYMBOLS = [
    "EURUSD", "EURUSDm", "GBPUSD", "GBPUSDm", "USDJPY", "USDJPYm",
    "BTCUSD", "BTCUSDm", "ETHUSD", "ETHUSDm"
]

TIMEFRAME_MAP = {}
if MT5_AVAILABLE:
    TIMEFRAME_MAP = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1,
    }


class ExnessMT5BridgeClient:
    """
    Connects to the authorized Exness MetaTrader 5 terminal on Windows,
    discovers broker symbols, reads real-time ticks & OHLC candles,
    and streams them to the ZYROX AI backend over authenticated HTTPS.
    """

    def __init__(
        self,
        backend_url: str,
        bridge_token: str,
        login: Optional[int] = None,
        password: Optional[str] = None,
        server: Optional[str] = None,
        terminal_path: Optional[str] = None,
        tick_interval: float = 1.0,
        candle_interval: float = 10.0
    ):
        self.backend_url = backend_url.rstrip("/")
        parsed_backend_url = urllib.parse.urlparse(self.backend_url)
        is_local_backend = parsed_backend_url.hostname in {"localhost", "127.0.0.1", "::1"}
        if parsed_backend_url.scheme != "https" and not (parsed_backend_url.scheme == "http" and is_local_backend):
            raise ValueError("Backend URL must use HTTPS (HTTP is allowed only for localhost).")
        if not bridge_token or len(bridge_token) < 32 or bridge_token == "zyrox_mt5_bridge_secure_token_change_me":
            raise ValueError("Set MT5_BRIDGE_TOKEN to a unique secret of at least 32 characters.")
        self.bridge_token = bridge_token
        self.login = login
        self.password = password
        self.server = server
        self.terminal_path = terminal_path
        self.tick_interval = tick_interval
        self.candle_interval = candle_interval
        self.broker: Optional[str] = None
        self.account_server: Optional[str] = None

        self.discovered_symbols: Dict[str, str] = {}  # canonical -> broker symbol
        self.active_gold_symbol: Optional[str] = None
        self.last_candle_push: float = 0.0
        self.connected_to_mt5: bool = False

    # -------------------------------------------------------------------------
    # 1. MT5 TERMINAL INITIALIZATION & SYMBOL DISCOVERY
    # -------------------------------------------------------------------------

    def initialize_mt5(self) -> bool:
        """Initializes connection to the running MetaTrader 5 terminal."""
        if not MT5_AVAILABLE:
            print("[ERROR] 'MetaTrader5' Python library is not installed.")
            print("Please install it on your Windows machine with: pip install MetaTrader5")
            return False

        init_kwargs = {}
        if self.terminal_path:
            init_kwargs["path"] = self.terminal_path

        print(f"[*] Initializing MetaTrader 5 terminal connection...")
        if not mt5.initialize(**init_kwargs):
            err = mt5.last_error()
            print(f"[!] mt5.initialize() failed. Error code: {err}")
            return False

        if self.login and self.password and self.server:
            print(f"[*] Authorizing MT5 account {self.login} on {self.server}...")
            if not mt5.login(login=self.login, password=self.password, server=self.server):
                err = mt5.last_error()
                print(f"[!] mt5.login() failed. Error: {err}")
                return False

        term_info = mt5.terminal_info()
        acc_info = mt5.account_info()

        broker = acc_info.company if acc_info else None
        server = acc_info.server if acc_info else None
        acc_num = acc_info.login if acc_info else "Active Terminal"

        self.broker = str(broker).strip() if broker else None
        self.account_server = str(server).strip() if server else None

        print(f"[+] MT5 Connected Successfully!")
        print(f"    Broker:  {broker}")
        print(f"    Server:  {server}")
        print(f"    Account: {acc_num}")
        print(f"    Build:   {term_info.build if term_info else 'N/A'}")

        self.connected_to_mt5 = True
        self.discover_symbols()
        return True

    def discover_symbols(self):
        """
        Scans broker symbol catalog to detect exact broker-specific symbols
        (such as XAUUSDm on Exness Standard vs XAUUSD on Pro).
        """
        print("[*] Discovering active broker symbols...")
        # 1. Gold Discovery
        for cand in CANDIDATE_GOLD_SYMBOLS:
            info = mt5.symbol_info(cand)
            if info is not None:
                mt5.symbol_select(cand, True)
                self.discovered_symbols["XAUUSD"] = cand
                self.active_gold_symbol = cand
                print(f"    [+] XAUUSD Mapped -> Broker Symbol: '{cand}' (Digits: {info.digits}, Spread: {info.spread})")
                break

        if not self.active_gold_symbol:
            print("[!] Warning: Could not auto-detect XAUUSD in broker symbols list.")

        # 2. Other Markets Discovery
        for cand in DEFAULT_FOREX_CRYPTO_SYMBOLS:
            canonical = cand.replace("m", "").replace(".m", "")
            if canonical in self.discovered_symbols:
                continue
            info = mt5.symbol_info(cand)
            if info is not None:
                mt5.symbol_select(cand, True)
                self.discovered_symbols[canonical] = cand
                print(f"    [+] {canonical} Mapped -> '{cand}'")

    # -------------------------------------------------------------------------
    # 2. MARKET DATA HARVESTING (READ-ONLY)
    # -------------------------------------------------------------------------

    def get_latest_ticks(self) -> List[Dict[str, Any]]:
        """Harvests authentic ticks (bid, ask, spread, timestamp) for all mapped symbols."""
        if not self.connected_to_mt5 or not MT5_AVAILABLE:
            return []

        ticks_payload = []
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        for canonical, broker_sym in self.discovered_symbols.items():
            tick = mt5.symbol_info_tick(broker_sym)
            sym_info = mt5.symbol_info(broker_sym)
            if tick is None:
                continue

            digits = sym_info.digits if sym_info else 2
            spread_pts = round((tick.ask - tick.bid) * (10 ** digits), 1) if digits else (tick.ask - tick.bid)

            tick_time_dt = datetime.datetime.fromtimestamp(tick.time, tz=datetime.timezone.utc)

            ticks_payload.append({
                "symbol": canonical,
                "broker_symbol": broker_sym,
                "bid": round(float(tick.bid), digits),
                "ask": round(float(tick.ask), digits),
                "last": round(float(tick.last or ((tick.bid + tick.ask) / 2.0)), digits),
                "spread": spread_pts,
                "digits": digits,
                "time": tick_time_dt.isoformat(),
                "volume": float(tick.volume)
            })

        return ticks_payload

    def get_candles(self, canonical: str, timeframe_str: str = "M15", count: int = 100) -> List[Dict[str, Any]]:
        """Extracts authentic OHLCV candles from MT5."""
        if not self.connected_to_mt5 or not MT5_AVAILABLE:
            return []

        broker_sym = self.discovered_symbols.get(canonical)
        if not broker_sym:
            return []

        tf_mt5 = TIMEFRAME_MAP.get(timeframe_str.upper())
        if tf_mt5 is None:
            return []

        rates = mt5.copy_rates_from_pos(broker_sym, tf_mt5, 0, count)
        if rates is None or len(rates) == 0:
            return []

        candles = []
        for r in rates:
            dt = datetime.datetime.fromtimestamp(r["time"], tz=datetime.timezone.utc)
            candles.append({
                "timestamp": dt.isoformat(),
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
                "volume": float(r["tick_volume"])
            })

        return candles

    # -------------------------------------------------------------------------
    # 3. SECURE OUTBOUND HTTPS DISPATCH
    # -------------------------------------------------------------------------

    def send_to_backend(self, endpoint_path: str, payload: Dict[str, Any]) -> bool:
        """
        Sends an authenticated outbound HTTPS request with timestamp and HMAC-SHA256 signature.
        Replay protection is enforced via X-Bridge-Timestamp.
        """
        url = f"{self.backend_url}{endpoint_path}"
        json_bytes = json.dumps(payload).encode("utf-8")
        timestamp_str = str(time.time())

        # Bind the signature to this request timestamp to prevent replay.
        signature = hmac.new(
            self.bridge_token.encode("utf-8"),
            timestamp_str.encode("utf-8") + b"." + json_bytes,
            hashlib.sha256
        ).hexdigest()

        headers = {
            "Content-Type": "application/json",
            "X-Bridge-Token": self.bridge_token,
            "X-Bridge-Timestamp": timestamp_str,
            "X-Bridge-Signature": signature,
            "User-Agent": "ZYROX-AI-MT5-Bridge/2.1.0"
        }

        req = urllib.request.Request(url, data=json_bytes, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                if resp.status == 200:
                    return True
                else:
                    print(f"[!] Backend returned status {resp.status}")
                    return False
        except urllib.error.HTTPError as e:
            print(f"[!] HTTP error from backend {url}: {e.code} - {e.reason}")
            return False
        except Exception as e:
            print(f"[!] Failed to push market data to backend: {e}")
            return False

    # -------------------------------------------------------------------------
    # 4. MAIN CONTINUOUS BRIDGE RUN LOOP
    # -------------------------------------------------------------------------

    def run(self):
        """Main continuous execution loop."""
        print(f"\n========================================================")
        print(f"  ZYROX AI — Exness MT5 Secure Bridge Started")
        print(f"  Target: {self.backend_url}")
        print(f"  Mode:   READ-ONLY Market Data Stream")
        print(f"========================================================\n")

        # Initial terminal connect
        while not self.initialize_mt5():
            print(f"[!] Waiting 10 seconds before retrying MT5 connection...")
            time.sleep(10)

        # Heartbeat announcement
        hb_payload = {
            "broker": self.broker,
            "server": self.server or self.account_server,
            "bridge_version": "2.1.0",
            "terminal_ping_ms": None,
            "active_symbols": list(self.discovered_symbols.keys())
        }
        self.send_to_backend("/api/v1/bridge/heartbeat", hb_payload)

        tick_counter = 0
        while True:
            try:
                # 1. Harvest & Stream Live Ticks
                ticks = self.get_latest_ticks()
                if ticks:
                    payload = {
                        "ticks": ticks,
                        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
                    }
                    ok = self.send_to_backend("/api/v1/bridge/market-data", payload)
                    if ok:
                        tick_counter += 1
                        if tick_counter % 10 == 0:
                            gold_tick = next((t for t in ticks if t["symbol"] == "XAUUSD"), None)
                            if gold_tick:
                                print(f"[+] Synced {len(ticks)} symbols | XAUUSD: Bid {gold_tick['bid']} / Ask {gold_tick['ask']} (Spread: {gold_tick['spread']} pts)")
                            else:
                                print(f"[+] Synced {len(ticks)} symbols to backend.")

                # 2. Periodically harvest & push multi-timeframe candles
                now_time = time.time()
                if (now_time - self.last_candle_push) >= self.candle_interval:
                    self.last_candle_push = now_time
                    for canonical in ["XAUUSD", "EURUSD", "BTCUSDT"]:
                        if canonical in self.discovered_symbols:
                            for tf in ["M1", "M5", "M15", "H1"]:
                                candles = self.get_candles(canonical, tf, count=100)
                                if candles:
                                    c_payload = {
                                        "symbol": canonical,
                                        "timeframe": tf,
                                        "candles": candles
                                    }
                                    self.send_to_backend("/api/v1/bridge/candles", c_payload)

                time.sleep(self.tick_interval)

            except KeyboardInterrupt:
                print("\n[*] Stopping MT5 bridge cleanly...")
                break
            except Exception as e:
                print(f"[!] Exception in bridge loop: {e}")
                time.sleep(2.0)

        if MT5_AVAILABLE:
            mt5.shutdown()
        print("[+] MT5 Bridge shutdown complete.")


# -----------------------------------------------------------------------------
# COMMAND LINE ENTRY POINT
# -----------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="ZYROX AI — Exness MT5 Windows Bridge Client")
    parser.add_argument("--backend-url", default=os.getenv("ZYROX_BACKEND_URL", "https://zyroxaitrading.onrender.com"),
                        help="ZYROX AI Backend URL (e.g. https://zyroxaitrading.onrender.com or http://localhost:8000)")
    parser.add_argument("--token", default=os.getenv("MT5_BRIDGE_TOKEN", "").strip(),
                        help="Shared authentication token matching server MT5_BRIDGE_TOKEN")
    parser.add_argument("--login", type=int, default=None, help="Optional MT5 account number")
    parser.add_argument("--password", default=None, help="Optional MT5 account password")
    parser.add_argument("--server", default=None, help="Optional Exness server name (e.g. Exness-Real25)")
    parser.add_argument("--terminal-path", default=None, help="Optional path to terminal64.exe")
    parser.add_argument("--tick-interval", type=float, default=1.0, help="Tick polling interval in seconds")

    args = parser.parse_args()

    if not args.token:
        parser.error("Set MT5_BRIDGE_TOKEN in the environment or provide --token.")

    client = ExnessMT5BridgeClient(
        backend_url=args.backend_url,
        bridge_token=args.token,
        login=args.login,
        password=args.password,
        server=args.server,
        terminal_path=args.terminal_path,
        tick_interval=args.tick_interval
    )
    client.run()


if __name__ == "__main__":
    main()
