"""
Institutional Multi-Timeframe Analysis Engine for XAUUSD & Major Financial Assets
==================================================================================
Implements institutional hierarchical market structure analysis across 5 timeframes:
1. D1  — Major Trend, 200 EMA, Daily Bias, Macro Dealing Range
2. H4  — High-Timeframe Market Structure, Order Blocks, Liquidity Pools
3. H1  — Intermediate Trend, BOS / CHoCH, Fair Value Gaps (FVG)
4. M15 — Tactical Setup Confirmation, Liquidity Sweeps, Structural Shift
5. M5  — Precision Execution Trigger, Tight Invalidation Level

Session Context:
- Asian Range (00:00 - 08:00 UTC): Liquidity accumulation
- London Open (08:00 - 16:00 UTC): Liquidity sweep & trend initiation
- New York Open (13:00 - 21:00 UTC): Institutional expansion & macro reaction
- London/NY Overlap (13:00 - 16:00 UTC): Maximum liquidity & volatility window

Strictly Non-Repainting and Causal.
"""

import datetime
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np

from taikry.indicators.chart_engine import XAUUSDChartEngine
from taikry.data.providers import market_data_engine
from taikry.data.validator import check_data_freshness, is_market_open
from taikry.config import MIN_RISK_REWARD_RATIO


class MultiTimeframeEngine:
    """
    Synthesizes market structure across D1, H4, H1, M15, and M5 timeframes
    to generate high-confluence institutional setups.
    """

    TIMEFRAMES = ["D1", "H4", "H1", "M15", "M5"]

    def __init__(self):
        self.chart_engine = XAUUSDChartEngine()

    def get_current_trading_session(self, current_dt_utc: Optional[datetime.datetime] = None) -> Dict[str, Any]:
        """Identifies active trading session and high-volume overlap window."""
        dt = current_dt_utc or datetime.datetime.now(datetime.timezone.utc)
        hour = dt.hour

        active_sessions = []
        is_london = 8 <= hour < 16
        is_ny = 13 <= hour < 21
        is_asian = 0 <= hour < 8
        is_overlap = 13 <= hour < 16

        if is_asian:
            active_sessions.append("ASIA")
        if is_london:
            active_sessions.append("LONDON")
        if is_ny:
            active_sessions.append("NEW_YORK")

        current_session = " / ".join(active_sessions) if active_sessions else "OFF_HOURS"

        return {
            "current_session": current_session,
            "is_overlap_window": is_overlap,
            "is_london_active": is_london,
            "is_ny_active": is_ny,
            "is_asian_active": is_asian,
            "volatility_regime": "PEAK_INSTITUTIONAL" if is_overlap else ("HIGH" if (is_london or is_ny) else "NORMAL"),
            "hour_utc": hour
        }

    def analyze_asset_hierarchy(self, symbol: str = "XAUUSD") -> Dict[str, Any]:
        """
        Executes end-to-end multi-timeframe analysis across D1, H4, H1, M15, and M5.
        """
        sym = symbol.upper()
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        session_info = self.get_current_trading_session(now_utc)
        market_open, open_desc = is_market_open(sym, check_time=now_utc)

        tf_results = {}
        bullish_votes = 0
        bearish_votes = 0
        neutral_votes = 0

        verified_price, price_source, price_timestamp = market_data_engine.get_verified_price(sym)
        daily_high = 0.0
        daily_low = 0.0

        def unavailable(reason: str, freshness: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
            return {
                "symbol": sym,
                "status": "DATA_UNAVAILABLE",
                "data_error": reason,
                "data_freshness": freshness,
                "price_source": price_source,
                "verified_price": None,
                "overall_bias": "NO TRADE",
                "overall_direction": "HOLD",
                "confluence_score": None,
                "market_open": market_open,
                "market_status_desc": open_desc,
                "session_context": session_info,
                "trade_setup": {"action": "HOLD", "entry_price": None, "stop_loss": None, "take_profit_1": None, "take_profit_2": None, "risk_reward_ratio": "N/A"},
                "timeframe_details": {},
                "summary_en": reason,
                "summary_kh": f"{reason} ទិន្នន័យមិនអាចប្រើសម្រាប់ការវិភាគបានទេ។",
                "timestamp_utc": now_utc.isoformat()
            }

        price_freshness = check_data_freshness(sym, price_timestamp, "M15")
        if verified_price <= 0 or "SYNTHETIC" in str(price_source).upper() or not price_freshness.get("fresh"):
            return unavailable("Verified live market price is unavailable or stale.", price_freshness)

        for tf in self.TIMEFRAMES:
            limit = 250 if tf == "D1" else (180 if tf == "H4" else 120)
            df = market_data_engine.get_candles(sym, timeframe=tf, limit=limit)
            minimum_bars = 200 if tf == "D1" else 50
            if df is None or df.empty or len(df) < minimum_bars:
                return unavailable(f"Verified {tf} candle data is unavailable or insufficient.")
            if "source" in df.columns and df["source"].astype(str).str.upper().str.contains("SYNTHETIC|DEMO").any():
                return unavailable(f"Synthetic {tf} candles cannot be used for market analysis.")
            if tf == "M15":
                candle_freshness = check_data_freshness(sym, df.iloc[-1].get("timestamp"), tf)
                if not candle_freshness.get("fresh"):
                    return unavailable("Latest M15 candle is stale.", candle_freshness)

            # Compute causal indicators
            df_ind = self.chart_engine.compute_technical_indicators(df)
            last_row = df_ind.iloc[-1]
            close = float(last_row["close"])

            ema20 = float(last_row.get("ema_20", close))
            ema50 = float(last_row.get("ema_50", close))
            ema200_raw = last_row.get("ema_200")
            ema200 = float(ema200_raw) if pd.notna(ema200_raw) else None
            rsi_raw = last_row.get("rsi_14")
            atr_raw = last_row.get("atr_14")
            if pd.isna(rsi_raw) or pd.isna(atr_raw) or not np.isfinite(float(atr_raw)) or float(atr_raw) <= 0:
                return unavailable(f"Verified indicator history is insufficient for {tf}.")
            rsi = float(rsi_raw)

            # Detect structural swing points and BOS/CHoCH
            swings = self.chart_engine.detect_causal_swings(df_ind, left=2, right=2)
            breaks = self.chart_engine.detect_causal_bos_and_choch(df_ind, swings)
            bos_list = [b for b in breaks if b.get("category") == "BOS"]
            choch_list = [b for b in breaks if b.get("category") == "CHOCH"]
            fvg_list = self.chart_engine.detect_causal_fair_value_gaps(df_ind)
            ob_list = self.chart_engine.detect_causal_order_blocks(df_ind)
            sweep_list = self.chart_engine.detect_causal_liquidity_sweeps(df_ind, swings)

            # Determine timeframe bias
            if tf == "D1":
                daily_high = float(df_ind["high"].max())
                daily_low = float(df_ind["low"].min())
                # D1 Bias based on 200 EMA and structure
                if ema200 is not None and close > ema200 and close > ema50:
                    bias = "BULLISH"
                    bullish_votes += 2  # D1 carries double weight
                elif ema200 is not None and close < ema200 and close < ema50:
                    bias = "BEARISH"
                    bearish_votes += 2
                else:
                    bias = "NEUTRAL"
                    neutral_votes += 1

            elif tf == "H4":
                if close > ema50 and (not bos_list or bos_list[-1]["direction"] == "BULLISH"):
                    bias = "BULLISH"
                    bullish_votes += 2  # H4 carries double weight
                elif close < ema50 and (not bos_list or bos_list[-1]["direction"] == "BEARISH"):
                    bias = "BEARISH"
                    bearish_votes += 2
                else:
                    bias = "NEUTRAL"
                    neutral_votes += 1

            elif tf == "H1":
                if close > ema20 and (not choch_list or choch_list[-1]["direction"] == "BULLISH"):
                    bias = "BULLISH"
                    bullish_votes += 1
                elif close < ema20 and (not choch_list or choch_list[-1]["direction"] == "BEARISH"):
                    bias = "BEARISH"
                    bearish_votes += 1
                else:
                    bias = "NEUTRAL"
                    neutral_votes += 1

            elif tf == "M15":
                if close > ema20 and rsi >= 48.0:
                    bias = "BULLISH"
                    bullish_votes += 1
                elif close < ema20 and rsi <= 52.0:
                    bias = "BEARISH"
                    bearish_votes += 1
                else:
                    bias = "NEUTRAL"
                    neutral_votes += 1

            else: # M5 Trigger
                if bullish_votes > bearish_votes and close > ema20:
                    bias = "BULLISH"
                    bullish_votes += 1
                elif bearish_votes > bullish_votes and close < ema20:
                    bias = "BEARISH"
                    bearish_votes += 1
                else:
                    bias = "NEUTRAL"
                    neutral_votes += 1

            tf_results[tf] = {
                "timeframe": tf,
                "bias": bias,
                "close": close,
                "ema_20": ema20,
                "ema_50": ema50,
                "ema_200": ema200,
                "rsi_14": rsi,
                "atr_14": float(last_row.get("atr_14")) if pd.notna(last_row.get("atr_14")) else None,
                "active_fvgs_count": len([f for f in fvg_list if not f.get("mitigated", False)]),
                "order_blocks_count": len(ob_list),
                "liquidity_sweeps_count": len(sweep_list),
                "latest_bos": bos_list[-1] if bos_list else None,
                "latest_choch": choch_list[-1] if choch_list else None
            }

        # Calculate institutional dealing range and equilibrium
        if daily_high > daily_low and daily_low > 0:
            range_span = daily_high - daily_low
            eq_price = round(daily_low + (range_span * 0.5), 2)
            fib_discount_ote = round(daily_low + (range_span * 0.618), 2)
            fib_premium_ote = round(daily_high - (range_span * 0.618), 2)
            pricing_tier = "PREMIUM (EXPENSIVE)" if verified_price > eq_price else "DISCOUNT (CHEAP)"
        else:
            eq_price = verified_price
            fib_discount_ote = verified_price * 0.99
            fib_premium_ote = verified_price * 1.01
            pricing_tier = "EQUILIBRIUM"

        # Confluence Synthesis
        total_weight = 7.0 # D1(2) + H4(2) + H1(1) + M15(1) + M5(1)
        if bullish_votes > bearish_votes:
            overall_direction = "BUY"
            overall_bias = "BULLISH"
            confluence_score = int(round((bullish_votes / total_weight) * 100))
        elif bearish_votes > bullish_votes:
            overall_direction = "SELL"
            overall_bias = "BEARISH"
            confluence_score = int(round((bearish_votes / total_weight) * 100))
        else:
            overall_direction = "HOLD"
            overall_bias = "NEUTRAL"
            confluence_score = 50

        # Bound confluence score cleanly
        confluence_score = max(0, min(95, confluence_score))

        # Precision Entry & Risk Levels
        atr_m15 = tf_results.get("M15", {}).get("atr_14")
        dec = 2 if "XAU" in sym or "XAG" in sym or verified_price > 10 else 4
        if not atr_m15 or not np.isfinite(atr_m15) or atr_m15 <= 0:
            overall_direction = "HOLD"
            overall_bias = "NEUTRAL"
            entry_price = stop_loss = take_profit_1 = take_profit_2 = None
            risk_reward_str = "N/A"
        elif overall_direction == "BUY":
            entry_price = round(verified_price, dec)
            stop_loss = round(verified_price - (1.6 * atr_m15), dec)
            risk = entry_price - stop_loss
            take_profit_1 = round(entry_price + (risk * max(MIN_RISK_REWARD_RATIO, 2.3)), dec)
            take_profit_2 = round(entry_price + (risk * max(MIN_RISK_REWARD_RATIO * 1.5, 3.8)), dec)
            risk_reward_str = f"1:{abs(take_profit_1 - entry_price) / risk:.2f}" if risk else "N/A"
        elif overall_direction == "SELL":
            entry_price = round(verified_price, dec)
            stop_loss = round(verified_price + (1.6 * atr_m15), dec)
            risk = stop_loss - entry_price
            take_profit_1 = round(entry_price - (risk * max(MIN_RISK_REWARD_RATIO, 2.3)), dec)
            take_profit_2 = round(entry_price - (risk * max(MIN_RISK_REWARD_RATIO * 1.5, 3.8)), dec)
            risk_reward_str = f"1:{abs(take_profit_1 - entry_price) / risk:.2f}" if risk else "N/A"
        else:
            entry_price = verified_price
            stop_loss = take_profit_1 = take_profit_2 = None
            risk_reward_str = "N/A"

        # Bilingual Synthesis
        summary_en = (
            f"Institutional {sym} Multi-Timeframe Alignment: D1={tf_results['D1']['bias']}, "
            f"H4={tf_results['H4']['bias']}, H1={tf_results['H1']['bias']}, M15={tf_results['M15']['bias']}, M5={tf_results['M5']['bias']}. "
            f"Dealing Range: {pricing_tier} (Equilibrium: {eq_price}). Active Session: {session_info['current_session']}. "
            f"Overall Confluence: {confluence_score}% {overall_bias}."
        )

        direction_kh = "ទិញ (BUY ENTRY)" if overall_direction == "BUY" else ("លក់ (SELL ENTRY)" if overall_direction == "SELL" else "រង់ចាំ (HOLD)")
        summary_kh = (
            f"ការវិភាគរចនាសម្ព័ន្ធពេលវេលាច្រើន {sym}៖ D1={tf_results['D1']['bias']}, "
            f"H4={tf_results['H4']['bias']}, H1={tf_results['H1']['bias']}, M15={tf_results['M15']['bias']}, M5={tf_results['M5']['bias']}។ "
            f"តំបន់តម្លៃ៖ {pricing_tier} (លំនឹង៖ {eq_price})។ វគ្គជួញដូរ៖ {session_info['current_session']}។ "
            f"កម្លាំងរួម៖ {confluence_score}% {direction_kh}។"
        )

        return {
            "symbol": sym,
            "verified_price": verified_price,
            "overall_bias": overall_bias,
            "overall_direction": overall_direction,
            "confluence_score": confluence_score,
            "market_open": market_open,
            "market_status_desc": open_desc,
            "session_context": session_info,
            "dealing_range": {
                "daily_high": daily_high,
                "daily_low": daily_low,
                "equilibrium_price": eq_price,
                "pricing_tier": pricing_tier,
                "ote_discount": fib_discount_ote,
                "ote_premium": fib_premium_ote
            },
            "trade_setup": {
                "action": overall_direction,
                "entry_price": entry_price,
                "stop_loss": stop_loss,
                "take_profit_1": take_profit_1,
                "take_profit_2": take_profit_2,
                "risk_reward_ratio": risk_reward_str
            },
            "timeframe_details": tf_results,
            "summary_en": summary_en,
            "summary_kh": summary_kh,
            "timestamp_utc": now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
        }


multi_timeframe_engine = MultiTimeframeEngine()
