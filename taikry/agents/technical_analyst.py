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

    def analyze(self, symbol: str, multi_tf_data: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """
        Performs multi-timeframe technical analysis across D1, H4, H1, M15, M5.
        Returns structured JSON.
        """
        tf_summaries = {}
        for tf, df in multi_tf_data.items():
            if not df.empty and len(df) >= 20:
                df_ind = compute_technical_indicators(df)
                tf_summaries[tf] = extract_technical_summary(df_ind)

        # Primary setup timeframe is M15, supported by HTF (H1, H4, D1)
        m15 = tf_summaries.get("M15") or tf_summaries.get("M5") or {}
        h1 = tf_summaries.get("H1", {})
        h4 = tf_summaries.get("H4", {})
        d1 = tf_summaries.get("D1", {})

        if not m15:
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

        curr_price = m15["current_price"]
        m15_trend = m15["trend"]
        h1_trend = h1.get("trend", "NEUTRAL")
        h4_trend = h4.get("trend", "NEUTRAL")
        rsi = m15["rsi"]
        atr = m15["atr"]

        evidence = []
        bull_score = 0
        bear_score = 0

        # Multi-timeframe trend confluence
        if "BULLISH" in h4_trend:
            bull_score += 25
            evidence.append(f"H4 Macro Trend is {h4_trend}")
        elif "BEARISH" in h4_trend:
            bear_score += 25
            evidence.append(f"H4 Macro Trend is {h4_trend}")

        if "BULLISH" in h1_trend:
            bull_score += 25
            evidence.append(f"H1 Intermediate Trend is {h1_trend}")
        elif "BEARISH" in h1_trend:
            bear_score += 25
            evidence.append(f"H1 Intermediate Trend is {h1_trend}")

        if "BULLISH" in m15_trend:
            bull_score += 20
            evidence.append(f"M15 Execution Trend is {m15_trend} (Price > EMA20 > EMA50)")
        elif "BEARISH" in m15_trend:
            bear_score += 20
            evidence.append(f"M15 Execution Trend is {m15_trend} (Price < EMA20 < EMA50)")

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
        patterns = m15.get("candlestick_patterns", [])
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
            sl = round(curr_price - (1.5 * atr), 4)
            tp1 = round(curr_price + (2.0 * 1.5 * atr), 4)
            tp2 = round(curr_price + (3.2 * 1.5 * atr), 4)
            invalidation = f"Drop below M15 support / EMA50 ({m15['ema_50']}) or SL {sl}"
            rationale = f"Confluence of bullish HTF alignment with active M15 momentum. Score: {bull_score}/100."
        elif (bear_score >= 40 and bear_score > bull_score) or (bear_score > bull_score and bear_score >= 30):
            bias = "STRONG BEARISH" if bear_score >= 70 else "BEARISH"
            confidence = max(55, min(95, bear_score))
            setup_eligible = True
            entry = curr_price
            sl = round(curr_price + (1.5 * atr), 4)
            tp1 = round(curr_price - (2.0 * 1.5 * atr), 4)
            tp2 = round(curr_price - (3.2 * 1.5 * atr), 4)
            invalidation = f"Rally above M15 resistance / EMA50 ({m15['ema_50']}) or SL {sl}"
            rationale = f"Confluence of bearish HTF alignment with downward momentum. Score: {bear_score}/100."
        else:
            # Subtle bias resolution based on price vs EMA20
            is_bull_tilt = curr_price >= m15.get("ema_20", curr_price)
            bias = "BULLISH" if is_bull_tilt else "BEARISH"
            confidence = 52
            setup_eligible = True
            entry = curr_price
            if is_bull_tilt:
                sl = round(curr_price - (1.5 * atr), 4)
                tp1 = round(curr_price + (3.0 * atr), 4)
                tp2 = round(curr_price + (4.8 * atr), 4)
                invalidation = f"Drop below M15 support or SL {sl}"
                rationale = f"Intraday bullish mean-reversion setup above short-term EMA. Score: {bull_score}/100."
            else:
                sl = round(curr_price + (1.5 * atr), 4)
                tp1 = round(curr_price - (3.0 * atr), 4)
                tp2 = round(curr_price - (4.8 * atr), 4)
                invalidation = f"Rally above M15 resistance or SL {sl}"
                rationale = f"Intraday bearish pullback setup below short-term EMA. Score: {bear_score}/100."

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
                "swing_high": m15["swing_high"],
                "swing_low": m15["swing_low"],
                "ema_20": m15["ema_20"],
                "ema_50": m15["ema_50"],
                "ema_200": m15["ema_200"],
                "atr": atr
            },
            "invalidation_level": invalidation,
            "multi_timeframe_alignment": {
                "D1": d1.get("trend", "N/A"),
                "H4": h4.get("trend", "N/A"),
                "H1": h1.get("trend", "N/A"),
                "M15": m15.get("trend", "N/A")
            },
            "rationale": rationale
        }

technical_analyst_agent = TechnicalAnalystAgent()
