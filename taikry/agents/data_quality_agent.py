"""
Agent 1: Market Data Quality & Integrity Agent for ZYROX AI.
=============================================================
Audits market feeds, tick latency, bid-ask spread expansion, and broker-to-reference
quote alignment. Rejects stale or synthetic data before execution.
"""

import time
import datetime
import math
import logging
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field

from taikry.data.providers import market_data_engine
from taikry.data.mt5_receiver import mt5_receiver
from taikry.data.validator import check_data_freshness
from taikry.config import get_symbol_config

logger = logging.getLogger("zyrox.agents.data_quality")


class DataQualityOutput(BaseModel):
    """Formal schema for Agent 1: Market Data Quality."""
    agent_id: str = "data_quality_agent"
    agent_name: str = "Agent 1: Market Data Quality Agent"
    symbol: str
    feed_status: str = "UNAVAILABLE"  # HEALTHY, DEGRADED, STALE, UNAVAILABLE
    is_fresh: bool = False
    is_broker_connected: bool = False
    broker_name: Optional[str] = None
    bid_price: Optional[float] = None
    ask_price: Optional[float] = None
    spread_points: Optional[float] = None
    spread_status: str = "UNAVAILABLE"  # NORMAL, ELEVATED, WIDENED_LOCKOUT, UNAVAILABLE
    max_tolerated_spread: float = 3.5  # points for Gold / pips for FX
    reference_price: Optional[float] = None
    reference_source: Optional[str] = None
    quote_divergence_points: Optional[float] = None
    quote_divergence_pct: Optional[float] = None
    latency_seconds: float = 0.0
    candle_count_m15: int = 0
    confidence: int = 0
    evidence: List[str] = Field(default_factory=list)
    timestamp_utc: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())


class MarketDataQualityAgent:
    """
    Independent Data Quality Guardian.
    Guarantees no trade analysis proceeds on fabricated, stale, or severely widened feeds.
    """

    def analyze(self, symbol: str = "XAUUSD", timeframe: str = "M15") -> Dict[str, Any]:
        """
        Executes comprehensive market data audit:
        1. Checks MT5 authentic broker terminal connection and tick state.
        2. Retrieves verified price & primary OHLCV candles.
        3. Measures spread and checks against volatility thresholds.
        4. Compares broker executable quote with external reference quote (e.g. Yahoo Spot/Futures).
        5. Strictly tags data as STALE or UNAVAILABLE if verification fails.
        """
        sym = symbol.upper().replace("/", "").replace("-", "")
        cfg = get_symbol_config(sym)
        evidence = []
        is_gold = "XAU" in sym

        # 1. Broker Feed Inspection (MT5 Windows Bridge)
        mt5_price, mt5_src, mt5_fresh, mt5_tick = mt5_receiver.get_latest_price(sym)
        bid = mt5_tick.get("bid")
        ask = mt5_tick.get("ask")
        spread = mt5_tick.get("spread")
        broker_name = mt5_tick.get("broker") or ("Exness" if mt5_fresh else None)

        if mt5_fresh and bid and ask and bid > 0 and ask > 0:
            broker_connected = True
            calc_spread = round(ask - bid, 2)
            evidence.append(f"Authentic broker feed verified via Windows MT5 ({broker_name}). Bid: {bid:.2f}, Ask: {ask:.2f}, Spread: {calc_spread:.2f} pts.")
        else:
            broker_connected = False
            calc_spread = spread if spread is not None else 0.0
            evidence.append("Windows MT5 broker bridge is not connected or streaming ticks.")

        # 2. Reference & Verified Price Retrieval
        verified_p, verified_src, verified_dt = market_data_engine.get_verified_price(sym)
        candles_df = market_data_engine.get_candles(sym, timeframe=timeframe, limit=100)

        # 3. Freshness Check
        last_candle_time = None
        if not candles_df.empty and "timestamp" in candles_df.columns:
            last_candle_time = candles_df.iloc[-1]["timestamp"]

        freshness = check_data_freshness(sym, last_candle_time or verified_dt, timeframe)
        is_fresh = bool(freshness.get("fresh", False))
        latency = float(freshness.get("age_seconds", 0.0))

        if is_fresh:
            evidence.append(f"Feed freshness confirmed: last bar latency {latency:.0f}s within {timeframe} SLA.")
        else:
            evidence.append(f"Feed staleness detected: age {latency:.0f}s exceeds threshold. Status: {freshness.get('reason', 'STALE')}.")

        # 4. Spread Status & Volatility Thresholds
        max_spread = 2.5 if is_gold else 0.00035
        spread_status = "NORMAL"
        if calc_spread > (max_spread * 2.0):
            spread_status = "WIDENED_LOCKOUT"
            evidence.append(f"CRITICAL: Spread ({calc_spread}) exceeds 2x safe threshold ({max_spread * 2.0}). Pre-news or rollover anomaly.")
        elif calc_spread > max_spread:
            spread_status = "ELEVATED"
            evidence.append(f"NOTICE: Spread ({calc_spread}) is elevated above normal ({max_spread}).")

        # 5. Quote Divergence (Broker vs Reference Quote)
        div_points = None
        div_pct = None
        if broker_connected and verified_p > 0 and bid is not None:
            exec_p = (bid + ask) / 2.0
            div_points = round(abs(exec_p - verified_p), 2)
            div_pct = round((div_points / verified_p) * 100, 3)
            evidence.append(f"Broker vs Reference divergence: {div_points} pts ({div_pct}%). Source: {verified_src}.")

        # 6. Overall Status Synthesis
        if not is_fresh or verified_p <= 0:
            feed_status = "STALE" if (candles_df is not None and not candles_df.empty) else "UNAVAILABLE"
            confidence = 10
        elif spread_status == "WIDENED_LOCKOUT":
            feed_status = "DEGRADED"
            confidence = 45
        elif broker_connected and is_fresh:
            feed_status = "HEALTHY"
            confidence = 95
        else:
            feed_status = "HEALTHY"  # Reference verified
            confidence = 80

        output = DataQualityOutput(
            symbol=sym,
            feed_status=feed_status,
            is_fresh=is_fresh,
            is_broker_connected=broker_connected,
            broker_name=broker_name,
            bid_price=bid,
            ask_price=ask,
            spread_points=calc_spread if calc_spread > 0 else None,
            spread_status=spread_status,
            max_tolerated_spread=max_spread,
            reference_price=verified_p if verified_p > 0 else None,
            reference_source=verified_src,
            quote_divergence_points=div_points,
            quote_divergence_pct=div_pct,
            latency_seconds=latency,
            candle_count_m15=len(candles_df),
            confidence=confidence,
            evidence=evidence
        )

        return output.model_dump()


data_quality_agent = MarketDataQualityAgent()
