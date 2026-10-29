"""Compatibility launcher for the verified TAIKRY market monitor.

The former standalone engine generated its own fallback trade levels and sent
alerts without the current data-freshness, calendar, and risk gates. All scans
now go through the production monitor and consensus pipeline.
"""

import argparse
import time
from typing import Any, Dict, Optional

from taikry.config import DEFAULT_TIMEFRAME, MONITORING_INTERVAL_MINUTES, WATCHLIST
from taikry.monitoring.engine import market_monitor_247


def scan_symbol(item: dict, timeframe: str = "M15", force_dispatch: bool = False) -> Optional[Dict[str, Any]]:
    """Scan one configured symbol using the verified consensus pipeline."""
    if force_dispatch:
        print("[INFO] Forced test dispatch is disabled; only approved, validated setups can be sent.")
    symbol = str(item.get("symbol", "")).strip().upper()
    if not symbol:
        return None
    results = market_monitor_247.scan_once(symbols=[symbol])
    return next((result for result in results if result.get("symbol", "").upper() == symbol), None)


def run_pipeline(single_pass: bool = False, force_first_test: bool = False, interval: Optional[int] = None):
    """Run a single safe scan or start the shared verified monitoring loop."""
    from taikry.database.session import init_db

    init_db()
    if force_first_test:
        print("[INFO] Forced test dispatch is disabled; the monitor will only dispatch validated setups.")

    market_monitor_247.interval_seconds = max(
        2,
        int(interval if interval is not None else MONITORING_INTERVAL_MINUTES * 60),
    )
    if single_pass:
        return market_monitor_247.scan_once()

    market_monitor_247.start_background()
    try:
        while market_monitor_247.is_running:
            time.sleep(1)
    except KeyboardInterrupt:
        market_monitor_247.stop()
        print("\nMonitoring stopped.")


def main():
    parser = argparse.ArgumentParser(description="Verified TAIKRY market monitoring compatibility launcher")
    parser.add_argument("--once", action="store_true", help="Run one verified scan across the watchlist")
    parser.add_argument("--test-dispatch", action="store_true", help="Deprecated; cannot bypass signal validation")
    parser.add_argument("--interval", type=int, default=MONITORING_INTERVAL_MINUTES * 60, help="Seconds between scans")
    args = parser.parse_args()
    run_pipeline(single_pass=args.once, force_first_test=args.test_dispatch, interval=args.interval)


if __name__ == "__main__":
    main()
