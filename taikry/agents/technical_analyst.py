"""Deterministic, multi-timeframe technical analysis for crypto and FX markets."""
from typing import Dict, Any, List

import numpy as np
import pandas as pd

from taikry.config import get_symbol_config
from taikry.indicators.technical import compute_technical_indicators, extract_technical_summary


class TechnicalAnalystAgent:
    """Technical specialist combining trend, momentum, structure, and volatility."""

    AGENT_ID = "technical_analyst"
    AGENT_NAME = "Agent 1 — Quantitative Technical Analyst"

    @staticmethod
    def _round_price(value: float, decimals: int) -> float:
        return round(float(value), max(0, min(10, int(decimals))))

    @staticmethod
    def _asset_context(symbol: str) -> Dict[str, str]:
        config = get_symbol_config(symbol)
        category = str(config.get("category", "Forex"))
        is_crypto = category.lower() == "crypto" or "USDT" in str(symbol).upper()
        if is_crypto:
            return {
                "asset_class": "CRYPTO",
                "market_hours": "24/7",
                "volume_basis": "EXCHANGE_REPORTED_SINGLE_VENUE",
                "volume_note": "Volume reflects the connected exchange/provider, not the entire crypto market.",
            }
        if category.lower() == "forex":
            return {
                "asset_class": "FOREX",
                "market_hours": "WEEKDAY_SESSIONS",
                "volume_basis": "BROKER_TICK_ACTIVITY_PROXY",
                "volume_note": "FX candle volume is treated as provider/broker activity, not consolidated traded volume.",
            }
        return {
            "asset_class": category.upper(),
            "market_hours": "PROVIDER_DEFINED",
            "volume_basis": "PROVIDER_REPORTED",
            "volume_note": "Volume interpretation depends on the selected data provider.",
        }

    def analyze(self, symbol: str, multi_tf_data: Dict[str, pd.DataFrame], setup_timeframe: str = "M15") -> Dict[str, Any]:
        """Builds a causal snapshot across higher-timeframe context and the setup chart."""
        symbol = str(symbol or "").upper()
        asset = self._asset_context(symbol)
        tf_summaries: Dict[str, Dict[str, Any]] = {}
        for timeframe, candles in (multi_tf_data or {}).items():
            if candles is None or candles.empty or len(candles) < 50:
                continue
            try:
                indicators = compute_technical_indicators(candles)
                summary = extract_technical_summary(indicators)
                if summary:
                    tf_summaries[str(timeframe).upper()] = summary
            except (KeyError, TypeError, ValueError, IndexError):
                # A bad timeframe is omitted; it cannot cast a synthetic vote.
                continue

        setup_timeframe = str(setup_timeframe or "M15").upper()
        primary = tf_summaries.get(setup_timeframe) or tf_summaries.get("M15") or tf_summaries.get("M5") or {}
        if not primary:
            return {
                "agent_id": self.AGENT_ID,
                "agent_name": self.AGENT_NAME,
                "bias": "NO TRADE",
                "confidence": 0,
                "setup_eligible": False,
                "asset_class": asset["asset_class"],
                "evidence": ["Insufficient verified candle history; at least 50 bars are required per timeframe."],
                "key_price_levels": {},
                "rationale": "No eligible timeframe contains enough valid data for technical analysis.",
            }

        price = float(primary["current_price"])
        atr = float(primary["atr"])
        if not np.isfinite(price) or price <= 0 or not np.isfinite(atr) or atr <= 0:
            return {
                "agent_id": self.AGENT_ID,
                "agent_name": self.AGENT_NAME,
                "bias": "NO TRADE",
                "confidence": 0,
                "setup_eligible": False,
                "asset_class": asset["asset_class"],
                "evidence": ["Price or ATR is invalid."],
                "key_price_levels": {},
                "rationale": "Invalid market data prevents setup evaluation.",
            }

        config = get_symbol_config(symbol)
        decimals = int(config.get("decimals", 5 if asset["asset_class"] == "FOREX" else 4))
        entry_price = self._round_price(price, decimals)
        h1 = tf_summaries.get("H1", {})
        h4 = tf_summaries.get("H4", {})
        d1 = tf_summaries.get("D1", {})
        w1 = tf_summaries.get("W1", {})
        evidence: List[str] = []
        warnings: List[str] = []
        bull_score = 0.0
        bear_score = 0.0
        trend_inputs = (
            [("W1", w1, 22), ("D1", d1, 28), ("H4", primary, 20)]
            if setup_timeframe == "H4" else
            [("D1", d1, 16), ("H4", h4, 22), ("H1", h1, 18), (setup_timeframe, primary, 14)]
        )
        for timeframe, summary, weight in trend_inputs:
            trend = str(summary.get("trend", "NEUTRAL")).upper()
            if "BULLISH" in trend:
                contribution = weight + (weight * 0.10 if trend.startswith("STRONG") else 0.0)
                bull_score += contribution
                evidence.append(f"{timeframe} EMA structure is {trend} (+{contribution:.0f}).")
            elif "BEARISH" in trend:
                contribution = weight + (weight * 0.10 if trend.startswith("STRONG") else 0.0)
                bear_score += contribution
                evidence.append(f"{timeframe} EMA structure is {trend} (+{contribution:.0f}).")

        # Momentum uses a neutral RSI band so the old overlapping conditions cannot
        # count the same RSI value as bullish and bearish at once.
        rsi = float(primary["rsi"])
        if 55 <= rsi <= 68:
            bull_score += 8
            evidence.append(f"RSI(14) at {rsi:.1f} supports positive momentum without an extreme reading.")
        elif 32 <= rsi <= 45:
            bear_score += 8
            evidence.append(f"RSI(14) at {rsi:.1f} supports negative momentum without an extreme reading.")
        elif rsi > 75:
            warnings.append(f"RSI is stretched high ({rsi:.1f}); avoid treating overbought alone as a short signal.")
        elif rsi < 25:
            warnings.append(f"RSI is stretched low ({rsi:.1f}); avoid treating oversold alone as a long signal.")
        elif 45 < rsi < 55:
            evidence.append(f"RSI(14) at {rsi:.1f} is neutral; it adds no directional score.")

        macd_hist = float(primary.get("macd_hist", 0.0))
        prev_macd_hist = float(primary.get("macd_hist_prev", macd_hist))
        if macd_hist > 0:
            contribution = 8 if macd_hist >= prev_macd_hist else 5
            bull_score += contribution
            evidence.append(f"MACD histogram is above zero ({'expanding' if contribution == 8 else 'fading'} bullish momentum; +{contribution}).")
        elif macd_hist < 0:
            contribution = 8 if macd_hist <= prev_macd_hist else 5
            bear_score += contribution
            evidence.append(f"MACD histogram is below zero ({'expanding' if contribution == 8 else 'fading'} bearish momentum; +{contribution}).")

        adx = primary.get("adx")
        plus_di = primary.get("plus_di")
        minus_di = primary.get("minus_di")
        if adx is not None and plus_di is not None and minus_di is not None:
            adx, plus_di, minus_di = float(adx), float(plus_di), float(minus_di)
            if adx >= 20 and plus_di > minus_di:
                contribution = 10 if adx >= 25 else 6
                bull_score += contribution
                evidence.append(f"DMI confirms bullish direction (+DI {plus_di:.1f} > −DI {minus_di:.1f}; ADX {adx:.1f}; +{contribution}).")
            elif adx >= 20 and minus_di > plus_di:
                contribution = 10 if adx >= 25 else 6
                bear_score += contribution
                evidence.append(f"DMI confirms bearish direction (−DI {minus_di:.1f} > +DI {plus_di:.1f}; ADX {adx:.1f}; +{contribution}).")
            else:
                evidence.append(f"ADX {adx:.1f} indicates a weak/ranging trend; DMI does not add directional weight.")

        structure = str(primary.get("market_structure", "INSUFFICIENT_CONFIRMED_SWINGS"))
        if structure == "BULLISH_HH_HL":
            bull_score += 8
            evidence.append("Confirmed swing structure is making higher highs and higher lows (+8).")
        elif structure == "BEARISH_LH_LL":
            bear_score += 8
            evidence.append("Confirmed swing structure is making lower highs and lower lows (+8).")

        relative_volume = primary.get("relative_volume_20")
        candle_direction = str(primary.get("latest_candle_direction", "NEUTRAL"))
        if relative_volume is not None and float(relative_volume) >= 1.25:
            if candle_direction == "BULLISH":
                bull_score += 4
                evidence.append(f"Current {asset['volume_basis'].lower().replace('_', ' ')} is {float(relative_volume):.2f}× its prior-bar median and confirms the bullish candle (+4).")
            elif candle_direction == "BEARISH":
                bear_score += 4
                evidence.append(f"Current {asset['volume_basis'].lower().replace('_', ' ')} is {float(relative_volume):.2f}× its prior-bar median and confirms the bearish candle (+4).")

        vwap = primary.get("vwap")
        if vwap is not None and np.isfinite(float(vwap)):
            if price > float(vwap):
                bull_score += 3
                evidence.append(f"Price is above session VWAP ({asset['volume_basis'].lower().replace('_', ' ')} based; +3).")
            elif price < float(vwap):
                bear_score += 3
                evidence.append(f"Price is below session VWAP ({asset['volume_basis'].lower().replace('_', ' ')} based; +3).")

        patterns = primary.get("candlestick_patterns", [])
        bullish_patterns = {"BULLISH_PIN_BAR_HAMMER", "BULLISH_ENGULFING"}
        bearish_patterns = {"BEARISH_SHOOTING_STAR", "BEARISH_ENGULFING"}
        if bullish_patterns.intersection(patterns):
            bull_score += 6
            evidence.append(f"Latest candle shows bullish rejection/engulfing pattern (+6): {', '.join(sorted(bullish_patterns.intersection(patterns)))}.")
        if bearish_patterns.intersection(patterns):
            bear_score += 6
            evidence.append(f"Latest candle shows bearish rejection/engulfing pattern (+6): {', '.join(sorted(bearish_patterns.intersection(patterns)))}.")

        # A very large ATR regime can produce poor fills; it is surfaced as risk context
        # instead of being misread as bullish or bearish momentum.
        atr_pct = float(primary.get("atr_pct", (atr / price) * 100.0))
        atr_rank = primary.get("atr_percentile_100")
        volatility_regime = "NORMAL"
        if atr_rank is not None:
            rank = float(atr_rank)
            volatility_regime = "HIGH" if rank >= 0.80 else ("LOW" if rank <= 0.20 else "NORMAL")
            if volatility_regime == "HIGH":
                warnings.append("ATR is in the upper historical volatility band; use smaller exposure and wait for spread/liquidity checks.")

        bull_score = min(100.0, bull_score)
        bear_score = min(100.0, bear_score)
        score_gap = abs(bull_score - bear_score)
        minimum_score = 48.0
        if bull_score >= minimum_score and bull_score - bear_score >= 12:
            direction = "LONG"
            bias = "STRONG BULLISH" if bull_score >= 72 else "BULLISH"
            winning_score = bull_score
        elif bear_score >= minimum_score and bear_score - bull_score >= 12:
            direction = "SHORT"
            bias = "STRONG BEARISH" if bear_score >= 72 else "BEARISH"
            winning_score = bear_score
        else:
            direction = "NONE"
            bias = "NEUTRAL"
            winning_score = max(bull_score, bear_score)
            warnings.append(f"Directional evidence is mixed or below threshold (long {bull_score:.0f}, short {bear_score:.0f}).")

        setup_eligible = direction in {"LONG", "SHORT"}
        confidence = int(round(min(95.0, max(0.0, winning_score)))) if setup_eligible else 0
        swing_high = float(primary["swing_high"])
        swing_low = float(primary["swing_low"])
        atr_buffer = max(atr * 0.15, 10 ** (-decimals))
        base_stop_atr = 1.55 if asset["asset_class"] == "CRYPTO" else 1.35
        max_structure_atr = 6.0 if setup_timeframe == "H4" else 4.0
        if direction == "LONG":
            structural_sl = swing_low - atr_buffer
            structural_risk = entry_price - structural_sl
            if not (base_stop_atr * atr <= structural_risk <= max_structure_atr * atr):
                structural_sl = entry_price - (base_stop_atr * atr)
            sl = self._round_price(structural_sl, decimals)
            risk = entry_price - sl
            tp1 = self._round_price(entry_price + (2.0 * risk), decimals)
            tp2 = self._round_price(entry_price + (3.0 * risk), decimals)
            invalidation = f"Long thesis invalidates below the confirmed {setup_timeframe} swing low or the stated stop-loss."
        elif direction == "SHORT":
            structural_sl = swing_high + atr_buffer
            structural_risk = structural_sl - entry_price
            if not (base_stop_atr * atr <= structural_risk <= max_structure_atr * atr):
                structural_sl = entry_price + (base_stop_atr * atr)
            sl = self._round_price(structural_sl, decimals)
            risk = sl - entry_price
            tp1 = self._round_price(entry_price - (2.0 * risk), decimals)
            tp2 = self._round_price(entry_price - (3.0 * risk), decimals)
            invalidation = f"Short thesis invalidates above the confirmed {setup_timeframe} swing high or the stated stop-loss."
        else:
            sl = tp1 = tp2 = None
            risk = 0.0
            invalidation = "No directional setup passed the technical confluence threshold."

        distance_to_ema_atr = (price - float(primary["ema_20"])) / atr
        entry_trigger = "NEAR_EMA20_PULLBACK" if abs(distance_to_ema_atr) <= 0.6 else "EXTENDED_FROM_EMA20"
        if direction == "LONG" and price > swing_high and relative_volume is not None and float(relative_volume) >= 1.25:
            entry_trigger = "BREAKOUT_WITH_ACTIVITY_CONFIRMATION"
        elif direction == "SHORT" and price < swing_low and relative_volume is not None and float(relative_volume) >= 1.25:
            entry_trigger = "BREAKDOWN_WITH_ACTIVITY_CONFIRMATION"
        if entry_trigger == "EXTENDED_FROM_EMA20":
            warnings.append("Price is extended from EMA20; wait for a pullback or a confirmed retest instead of chasing.")

        return {
            "agent_id": self.AGENT_ID,
            "agent_name": self.AGENT_NAME,
            "bias": bias,
            "direction": direction,
            "confidence": confidence,
            "setup_eligible": setup_eligible,
            "asset_class": asset["asset_class"],
            "evidence": evidence,
            "warnings": warnings,
            "technical_scores": {
                "long": int(round(bull_score)),
                "short": int(round(bear_score)),
                "score_gap": int(round(score_gap)),
                "minimum_score": int(minimum_score),
            },
            "technical_context": {
                "market_hours": asset["market_hours"],
                "volume_basis": asset["volume_basis"],
                "volume_note": asset["volume_note"],
                "trend_strength": primary.get("trend_strength", "UNKNOWN"),
                "volatility_regime": volatility_regime,
                "atr_percent": round(atr_pct, 5),
                "adx": primary.get("adx"),
                "plus_di": primary.get("plus_di"),
                "minus_di": primary.get("minus_di"),
                "relative_volume_20": relative_volume,
                "market_structure": primary.get("market_structure"),
                "entry_trigger": entry_trigger,
            },
            "key_price_levels": {
                "current_price": entry_price,
                "suggested_entry": entry_price,
                "suggested_stop_loss": sl,
                "take_profit_1": tp1,
                "take_profit_2": tp2,
                "risk_distance": self._round_price(risk, decimals) if risk else None,
                "risk_reward_tp1": "1:2.00" if setup_eligible else None,
                "risk_reward_tp2": "1:3.00" if setup_eligible else None,
                "swing_high": self._round_price(swing_high, decimals),
                "swing_low": self._round_price(swing_low, decimals),
                "ema_20": self._round_price(primary["ema_20"], decimals),
                "ema_50": self._round_price(primary["ema_50"], decimals),
                "ema_200": self._round_price(primary["ema_200"], decimals) if primary.get("ema_200") is not None else None,
                "rsi": rsi,
                "atr": self._round_price(atr, decimals),
                "setup_timeframe": setup_timeframe,
                "entry_trigger": entry_trigger,
            },
            "invalidation_level": invalidation,
            "multi_timeframe_alignment": {
                "W1": w1.get("trend", "N/A"),
                "D1": d1.get("trend", "N/A"),
                "H4": h4.get("trend", "N/A"),
                "H1": h1.get("trend", "N/A"),
                "M15": tf_summaries.get("M15", {}).get("trend", "N/A"),
                "M5": tf_summaries.get("M5", {}).get("trend", "N/A"),
                "setup_timeframe": setup_timeframe,
            },
            "rationale": (
                f"{asset['asset_class']} technical confluence: long {bull_score:.0f}/100, short {bear_score:.0f}/100; "
                f"{primary.get('trend_strength', 'trend strength unavailable').lower()} regime on {setup_timeframe}. "
                f"ATR-adjusted stop with 2R/3R targets; entry trigger context: {entry_trigger}."
            ),
        }


technical_analyst_agent = TechnicalAnalystAgent()
