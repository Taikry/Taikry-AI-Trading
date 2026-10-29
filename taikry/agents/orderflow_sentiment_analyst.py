"""
Agent 8: Order Flow, CVD & Liquidity Heatmap Analyst for ZYROX AI Terminal.
===========================================================================
Specializes in:
- Cumulative Volume Delta (CVD) divergence detection
- Order Flow imbalance & absorption (Aggressive buyers/sellers trapped)
- Liquidity Heatmap analysis (Stop-loss clusters above/below key swing points)
- Retail vs Smart Money Sentiment Divergence
"""
import time
import datetime
import logging
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

logger = logging.getLogger("zyrox.agents.orderflow_sentiment")


class OrderFlowSentimentOutput(BaseModel):
    """Structured output for Agent 8: Order Flow & Liquidity Sentiment."""
    agent_id: str = "orderflow_sentiment_analyst"
    agent_name: str = "Agent 8: Order Flow & Liquidity Sentiment Analyst"
    status: str = "COMPLETED"
    bias: str = "NEUTRAL"  # BULLISH, BEARISH, NEUTRAL, TRAPPED_BUYERS, TRAPPED_SELLERS
    confidence: int = 50   # 0 to 100
    setup_eligible: bool = False
    cvd_status: str = "BALANCED"  # BULLISH_DIVERGENCE, BEARISH_DIVERGENCE, ABSORPTION, BALANCED
    cvd_delta: float = 0.0
    liquidity_clusters: Dict[str, Any] = Field(default_factory=dict)
    trapped_retail_side: str = "NONE"  # BUYERS, SELLERS, NONE
    sentiment_ratio: float = 0.5  # 0.0 (Extremely Bearish) to 1.0 (Extremely Bullish)
    smart_money_absorption: bool = False
    evidence: List[str] = Field(default_factory=list)
    rationale_en: str = ""
    rationale_kh: str = ""


class OrderFlowSentimentAnalyst:
    """Institutional Order Flow and Market Microstructure Intelligence Engine."""

    def analyze(
        self,
        symbol: str,
        df_m15: Optional[pd.DataFrame] = None,
        verified_price: float = 0.0
    ) -> OrderFlowSentimentOutput:
        t0 = time.time()
        evidence: List[str] = []

        if df_m15 is None or df_m15.empty or len(df_m15) < 10:
            return OrderFlowSentimentOutput(
                status="UNAVAILABLE",
                bias="NEUTRAL",
                confidence=0,
                setup_eligible=False,
                evidence=["Insufficient order flow bar data for microstructure calculations."],
                rationale_en="Order flow data unavailable.",
                rationale_kh="ទិន្នន័យ Order Flow ពុំទាន់គ្រប់គ្រាន់សម្រាប់ការវិភាគ។"
            )

        df = df_m15.copy()
        for col in ["open", "high", "low", "close", "volume"]:
            if col not in df.columns:
                df[col] = 0.0

        close = df["close"].values
        high = df["high"].values
        low = df["low"].values
        open_p = df["open"].values
        vol = df["volume"].values

        # 1. Approximate Volume Delta (Intra-bar buying vs selling pressure)
        # Using Close location value (CLV) = ((Close - Low) - (High - Close)) / (High - Low)
        hl_range = high - low
        hl_safe = np.where(hl_range == 0, 1e-6, hl_range)
        clv = ((close - low) - (high - close)) / hl_safe
        volume_deltas = clv * vol
        cumulative_delta = float(np.sum(volume_deltas[-14:]))
        recent_delta = float(volume_deltas[-1])

        # 2. CVD Divergence Detection
        # Price making higher high but CVD making lower high -> Bearish Exhaustion / Absorption
        price_trend = close[-1] - close[-5]
        cvd_divergence = "BALANCED"
        smart_money_absorption = False
        bias = "NEUTRAL"
        confidence = 65

        if price_trend > 0 and cumulative_delta < 0:
            cvd_divergence = "BEARISH_DIVERGENCE"
            smart_money_absorption = True
            bias = "BEARISH"
            confidence = 82
            evidence.append("Bearish CVD Divergence: Price climbing but net volume delta is negative (Smart money absorbing retail bids).")
        elif price_trend < 0 and cumulative_delta > 0:
            cvd_divergence = "BULLISH_DIVERGENCE"
            smart_money_absorption = True
            bias = "BULLISH"
            confidence = 82
            evidence.append("Bullish CVD Divergence: Price declining but net volume delta is positive (Institutional accumulation into sell stops).")
        elif cumulative_delta > 0 and recent_delta > 0:
            cvd_divergence = "BULLISH_EXPANSION"
            bias = "BULLISH"
            confidence = 76
            evidence.append("Positive Volume Delta: Sustained institutional buying momentum.")
        elif cumulative_delta < 0 and recent_delta < 0:
            cvd_divergence = "BEARISH_EXPANSION"
            bias = "BEARISH"
            confidence = 76
            evidence.append("Negative Volume Delta: Persistent institutional selling pressure.")

        # 3. Liquidity Stop Clusters (Swing Highs/Lows liquidity pools)
        recent_swing_high = float(np.max(high[-20:]))
        recent_swing_low = float(np.min(low[-20:]))
        current_p = verified_price if verified_price > 0 else float(close[-1])

        dist_to_high = abs(current_p - recent_swing_high)
        dist_to_low = abs(current_p - recent_swing_low)

        trapped_side = "NONE"
        if dist_to_high < (current_p * 0.0015):
            evidence.append(f"Price approaching buy-side liquidity pool at {recent_swing_high:.2f} (Potential sweep zone).")
            if bias == "BEARISH":
                trapped_side = "BUYERS"
        elif dist_to_low < (current_p * 0.0015):
            evidence.append(f"Price approaching sell-side liquidity pool at {recent_swing_low:.2f} (Potential sweep zone).")
            if bias == "BULLISH":
                trapped_side = "SELLERS"

        # Sentiment Ratio (0.0 to 1.0)
        sentiment_ratio = round(max(0.1, min(0.9, 0.5 + (clv[-1] * 0.3))), 2)

        setup_eligible = confidence >= 75 and bias in ["BULLISH", "BEARISH"]

        # Dual-Language Rationale
        if bias == "BULLISH":
            rationale_en = f"Bullish order flow dominant. Cumulative delta {cumulative_delta:+.1f} confirms institutional accumulation with liquidity sweep below {recent_swing_low:.2f}."
            rationale_kh = f"លំហូរ Order Flow មាននិន្នាការឡើងខ្លាំង។ កម្លាំង Volume Delta {cumulative_delta:+.1f} បង្ហាញពីការប្រមូលទិញរបស់ស្ថាប័នធំៗបន្ទាប់ពីសម្អាត Liquidity ក្រោម {recent_swing_low:.2f}។"
        elif bias == "BEARISH":
            rationale_en = f"Bearish order flow dominant. Cumulative delta {cumulative_delta:+.1f} indicates aggressive absorption and distribution near {recent_swing_high:.2f}."
            rationale_kh = f"លំហូរ Order Flow មាននិន្នាការចុះខ្លាំង។ កម្លាំង Volume Delta {cumulative_delta:+.1f} បង្ហាញពីការស្រូបយក Liquidity និងលក់ចេញរបស់ស្ថាប័នធំៗក្បែរ {recent_swing_high:.2f}។"
        else:
            rationale_en = "Order flow delta is balanced without institutional absorption divergence."
            rationale_kh = "លំហូរ Order Flow មានលំនឹងធម្មតា ដោយពុំទាន់មានសញ្ញាស្រូបយក Liquidity ជាក់លាក់នៅឡើយ។"

        return OrderFlowSentimentOutput(
            status="COMPLETED",
            bias=bias,
            confidence=confidence,
            setup_eligible=setup_eligible,
            cvd_status=cvd_divergence,
            cvd_delta=round(cumulative_delta, 2),
            liquidity_clusters={
                "buy_side_pool": round(recent_swing_high, 2),
                "sell_side_pool": round(recent_swing_low, 2),
                "distance_to_high_pts": round(dist_to_high, 2),
                "distance_to_low_pts": round(dist_to_low, 2)
            },
            trapped_retail_side=trapped_side,
            sentiment_ratio=sentiment_ratio,
            smart_money_absorption=smart_money_absorption,
            evidence=evidence,
            rationale_en=rationale_en,
            rationale_kh=rationale_kh
        )


# Global Singleton Instance
orderflow_sentiment_agent = OrderFlowSentimentAnalyst()

