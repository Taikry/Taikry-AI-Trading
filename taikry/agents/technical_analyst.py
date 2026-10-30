"""
AGENT 1 — TECHNICAL ANALYST
Analyzes multi-timeframe trend alignment, candlestick patterns, support/resistance,
EMA 20/50/200, RSI 14, ATR, breakouts, and pullbacks.
"""
from typing import Dict, Any, List
import pandas as pd
from taikry.indicators.technical import compute_technical_indicators, extract_technical_summary

class TechnicalAnalystAgent:
    """Agent 1: Quantitative Technical Specialist."""
    AGENT_ID = "technical_analyst"
    AGENT_NAME = "Agent 1 — Quantitative Technical Analyst"

    def analyze(self, symbol: str, multi_tf_data: Dict[str, pd.DataFrame], setup_timeframe: str = "M15") -> Dict[str, Any]:
        """
        Performs multi-timeframe technical analysis across D1, H4, H1, M15, M5.
        Returns structured JSON.
        """
        tf_summaries = {}
        for tf, df in multi_tf_data.items():
            if df is not None and not df.empty and len(df) >= 20:
                df_ind = compute_technical_indicators(df)
                tf_summaries[tf] = extract_technical_summary(df_ind)

        setup_timeframe = str(setup_timeframe or "M15").upper()
        # Swing setups use H4 for structure with D1/W1 as context. Intraday
        # keeps M15 (M5 fallback) and H1/H4 context.
        primary = tf_summaries.get(setup_timeframe) or tf_summaries.get("M15") or tf_summaries.get("M5") or {}
        h1 = tf_summaries.get("H1", {})
        h4 = tf_summaries.get("H4", {})
        d1 = tf_summaries.get("D1", {})

        if not primary:
            return {
                "agent_id": self.AGENT_ID,
                "agent_name": self.AGENT_NAME,
                "bias": "NO TRADE",
                "confidence": 0,
                "setup_eligible": False,
                "evidence": ["Insufficient technical candle data"],
                "key_price_levels": {},
                "rationale": "Missing candle bars across active timeframes."
            }

        curr_price = primary["current_price"]
        primary_trend = primary["trend"]
        h1_trend = h1.get("trend", "NEUTRAL")
        h4_trend = h4.get("trend", "NEUTRAL")
        rsi = primary["rsi"]
        atr = primary["atr"]

        evidence = []
        bull_score = 0
        bear_score = 0

        # Multi-timeframe trend confluence: weekly/daily context for swing,
        # H4/H1 context for intraday.
        trend_inputs = (
            [("W1", tf_summaries.get("W1", {}).get("trend", "NEUTRAL"), 25),
             ("D1", d1.get("trend", "NEUTRAL"), 25),
             ("H4", primary_trend, 20)]
            if setup_timeframe == "H4" else
            [("H4", h4_trend, 25), ("H1", h1_trend, 25), (setup_timeframe, primary_trend, 20)]
        )
        for tf, trend, weight in trend_inputs:
            if "BULLISH" in trend:
                bull_score += weight
                evidence.append(f"{tf} trend is {trend}")
            elif "BEARISH" in trend:
                bear_score += weight
                evidence.append(f"{tf} trend is {trend}")

        # Momentum RSI evaluation
        if 42 <= rsi <= 65:
            bull_score += 15
            evidence.append(f"RSI 14 at {rsi} demonstrates healthy bullish momentum")
        elif 35 <= rsi <= 58:
            bear_score += 15
            evidence.append(f"RSI 14 at {rsi} confirms steady bearish pressure")
        elif rsi < 30:
            bull_score += 10
            evidence.append(f"RSI at {rsi} is oversold (mean-reversion support)")
        elif rsi > 70:
            bear_score += 10
            evidence.append(f"RSI at {rsi} is overbought (exhaustion resistance)")

        # Candlestick patterns
        patterns = primary.get("candlestick_patterns", [])
        if "BULLISH_PIN_BAR_HAMMER" in patterns or "BULLISH_ENGULFING" in patterns:
            bull_score += 15
            evidence.append(f"Confirmed bullish candlestick pattern: {', '.join(patterns)}")
        elif "BEARISH_SHOOTING_STAR" in patterns or "BEARISH_ENGULFING" in patterns:
            bear_score += 15
            evidence.append(f"Confirmed bearish candlestick pattern: {', '.join(patterns)}")

        # Decision Matrix - Enhanced to actively identify BUY and SELL setups
        if (bull_score >= 40 and bull_score >= bear_score) or (bull_score > bear_score and bull_score >= 30):
            bias = "STRONG BULLISH" if bull_score >= 70 else "BULLISH"
            confidence = max(55, min(95, bull_score))
            setup_eligible = True
            entry = curr_price
            swing_low = primary.get("swing_low")
            structural_sl = float(swing_low) - (0.15 * atr) if swing_low is not None else curr_price - (1.5 * atr)
            structural_risk = curr_price - structural_sl
            max_structure_risk = (6.0 if setup_timeframe == "H4" else 4.0) * atr
            sl = round(structural_sl if 0.5 * atr <= structural_risk <= max_structure_risk else curr_price - (1.5 * atr), 4)
            tp1 = round(curr_price + (2.0 * 1.5 * atr), 4)
            tp2 = round(curr_price + (3.2 * 1.5 * atr), 4)
            invalidation = f"Break below {setup_timeframe} swing support / EMA50 ({primary['ema_50']}) or SL {sl}"
            rationale = f"Confluence of higher-timeframe alignment with active {setup_timeframe} momentum. Score: {bull_score}/100."
        elif (bear_score >= 40 and bear_score > bull_score) or (bear_score > bull_score and bear_score >= 30):
            bias = "STRONG BEARISH" if bear_score >= 70 else "BEARISH"
            confidence = max(55, min(95, bear_score))
            setup_eligible = True
            entry = curr_price
            swing_high = primary.get("swing_high")
            structural_sl = float(swing_high) + (0.15 * atr) if swing_high is not None else curr_price + (1.5 * atr)
            structural_risk = structural_sl - curr_price
            max_structure_risk = (6.0 if setup_timeframe == "H4" else 4.0) * atr
            sl = round(structural_sl if 0.5 * atr <= structural_risk <= max_structure_risk else curr_price + (1.5 * atr), 4)
            tp1 = round(curr_price - (2.0 * 1.5 * atr), 4)
            tp2 = round(curr_price - (3.2 * 1.5 * atr), 4)
            invalidation = f"Break above {setup_timeframe} swing resistance / EMA50 ({primary['ema_50']}) or SL {sl}"
            rationale = f"Confluence of higher-timeframe alignment with downward {setup_timeframe} momentum. Score: {bear_score}/100."
        else:
            # Do not manufacture direction from a small EMA tilt when the score
            # matrix has not found enough evidence for a directional setup.
            bias = "NEUTRAL"
            confidence = 0
            setup_eligible = False
            entry = curr_price
            sl = tp1 = tp2 = None
            invalidation = "No directional setup passed the technical score threshold."
            rationale = f"Technical evidence is mixed or insufficient for direction (bull {bull_score}/100, bear {bear_score}/100)."

        return {
            "agent_id": self.AGENT_ID,
            "agent_name": self.AGENT_NAME,
            "bias": bias,
            "confidence": confidence,
            "setup_eligible": setup_eligible,
            "evidence": evidence,
            "key_price_levels": {
                "current_price": curr_price,
                "suggested_entry": entry,
                "suggested_stop_loss": sl,
                "take_profit_1": tp1,
                "take_profit_2": tp2,
                "swing_high": primary["swing_high"],
                "swing_low": primary["swing_low"],
                "ema_20": primary["ema_20"],
                "ema_50": primary["ema_50"],
                "ema_200": primary["ema_200"],
                "atr": atr,
                "setup_timeframe": setup_timeframe,
            },
            "invalidation_level": invalidation,
            "multi_timeframe_alignment": {
                "D1": d1.get("trend", "N/A"),
                "H4": h4.get("trend", "N/A"),
                "H1": h1.get("trend", "N/A"),
                "M15": tf_summaries.get("M15", {}).get("trend", "N/A"),
                "W1": tf_summaries.get("W1", {}).get("trend", "N/A"),
                "setup_timeframe": setup_timeframe
            },
            "rationale": rationale
        }

technical_analyst_agent = TechnicalAnalystAgent()
