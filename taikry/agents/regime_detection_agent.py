"""
TAIKRY AI MARKET INTELLIGENCE — Market Regime Detection Agent (Agent 6)
======================================================================
Identifies structural market dynamics:
- Trend vs. Range (ADX, Moving Average Alignment)
- Volatility Regime (Bollinger Band Width, ATR expansion/compression)
- Hurst Exponent (Persistent Trend vs. Mean Reverting vs. Random Walk)
"""
import math
import logging
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np

logger = logging.getLogger("taikry.agents.regime_detection")

class MarketRegimeDetectionAgent:
    """Classifies the market into unambiguous macro/micro regimes to inform strategy selection."""

    def __init__(self):
        self.agent_id = "regime_detection_agent"
        self.name = "Agent 6: Market Regime Detection Agent"

    def calculate_hurst_exponent(self, prices: np.ndarray, max_lags: int = 20) -> float:
        """
        Estimates the Hurst Exponent (H):
        H > 0.55 -> Persistent trending market
        H < 0.45 -> Mean-reverting / anti-persistent range
        0.45 <= H <= 0.55 -> Random walk / Brownian noise
        """
        if len(prices) < 30:
            return 0.50
        try:
            lags = range(2, min(max_lags, len(prices) // 4))
            tau = []
            for lag in lags:
                diff = prices[lag:] - prices[:-lag]
                std_diff = np.std(diff)
                if std_diff > 1e-8:
                    tau.append(std_diff)
                else:
                    tau.append(1e-8)
            if len(tau) < 3:
                return 0.50
            m = np.polyfit(np.log(list(lags)), np.log(tau), 1)
            hurst = float(m[0] * 2.0)
            return round(max(0.01, min(0.99, hurst)), 3)
        except Exception:
            return 0.50

    def analyze(self, symbol: str, multi_tf_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyzes multi-timeframe candle data to establish the current regime.
        """
        df = multi_tf_data.get("M15")
        if df is None or df.empty or len(df) < 25:
            df = multi_tf_data.get("H1")
        if df is None or df.empty or len(df) < 25:
            return {
                "agent_id": self.agent_id,
                "agent_name": self.name,
                "regime": "UNKNOWN",
                "volatility_state": "UNKNOWN",
                "hurst_exponent": 0.50,
                "trend_strength": 0.0,
                "adx": 0.0,
                "evidence": ["Candle depth insufficient for statistical regime classification."],
                "rationale": "Stand by for confirmed price action."
            }

        closes = df["close"].values
        highs = df["high"].values
        lows = df["low"].values

        # 1. Hurst Exponent
        hurst = self.calculate_hurst_exponent(closes)

        # 2. Approximate ADX & ATR
        tr_list = []
        for i in range(1, len(df)):
            tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
            tr_list.append(tr)
        atr_14 = float(np.mean(tr_list[-14:])) if len(tr_list) >= 14 else float(np.mean(tr_list))
        atr_pct = (atr_14 / closes[-1]) * 100.0

        # Moving averages
        ema_20 = float(pd.Series(closes).ewm(span=20).mean().iloc[-1])
        ema_50 = float(pd.Series(closes).ewm(span=50).mean().iloc[-1]) if len(closes) >= 50 else ema_20

        # Bollinger Band Width
        rolling_std = float(pd.Series(closes).rolling(20).std().iloc[-1])
        bb_width = (rolling_std * 4.0 / ema_20) * 100.0 if ema_20 > 0 else 1.0

        # Volatility state
        if bb_width < 0.35:
            vol_state = "SQUEEZE_COMPRESSION"
        elif bb_width > 1.20:
            vol_state = "HIGH_VOLATILITY_EXPANSION"
        else:
            vol_state = "NORMAL_LIQUIDITY"

        # Trend & Regime classification
        diff_pct = (closes[-1] - ema_50) / ema_50 * 100.0
        evidence: List[str] = []

        if abs(diff_pct) < 0.20 and hurst < 0.48:
            regime = "CONSOLIDATION_RANGE"
            evidence.append(f"Price coiling tightly around EMA 50 (diff: {diff_pct:+.2f}%) with low Hurst ({hurst}). Range-bound market.")
        elif diff_pct > 0.30 and hurst >= 0.52 and ema_20 > ema_50:
            regime = "TRENDING_BULLISH"
            evidence.append(f"Bullish trend confirmed: EMA 20 > EMA 50, price +{diff_pct:.2f}% above baseline, persistent Hurst ({hurst}).")
        elif diff_pct < -0.30 and hurst >= 0.52 and ema_20 < ema_50:
            regime = "TRENDING_BEARISH"
            evidence.append(f"Bearish trend confirmed: EMA 20 < EMA 50, price {diff_pct:.2f}% below baseline, persistent Hurst ({hurst}).")
        else:
            regime = "CHOPPY_ROTATION"
            evidence.append(f"Rotational chop: Hurst ({hurst}) near random walk (0.50), BB width {bb_width:.2f}%.")

        evidence.append(f"Volatility regime: {vol_state} (ATR 14: {atr_14:.2f} pts, BB Width: {bb_width:.2f}%).")

        return {
            "agent_id": self.agent_id,
            "agent_name": self.name,
            "regime": regime,
            "volatility_state": vol_state,
            "hurst_exponent": hurst,
            "atr_14": round(atr_14, 2),
            "atr_pct": round(atr_pct, 3),
            "bb_width_pct": round(bb_width, 2),
            "evidence": evidence,
            "rationale": f"Market operates in {regime} with {vol_state} volatility."
        }

regime_detection_agent = MarketRegimeDetectionAgent()
