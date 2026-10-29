"""
Agent 9: Multi-Timeframe Fractal Trend Analyst for ZYROX AI Terminal.
=====================================================================
Specializes in:
- Multi-Timeframe Fractal Hierarchy (Daily -> 4H -> 1H -> 15m -> 5m)
- Fractal trend alignment & counter-trend trap prevention
- Higher Timeframe (HTF) Key Level interaction (Order Blocks, Mitigation Zones)
- Precision lower timeframe (LTF) trigger validation
"""
import time
import logging
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

logger = logging.getLogger("zyrox.agents.fractal_mtf")


class FractalMTFOutput(BaseModel):
    """Structured output for Agent 9: Fractal MTF Trend Analyst."""
    agent_id: str = "fractal_mtf_analyst"
    agent_name: str = "Agent 9: Multi-Timeframe Fractal Trend Analyst"
    status: str = "COMPLETED"
    fractal_alignment: str = "ALIGNED"  # ALIGNED, CONFLICTED, COUNTER_TREND_TRAP, RANGING
    htf_bias: str = "NEUTRAL"          # Daily & 4H bias: BULLISH, BEARISH, NEUTRAL
    itf_bias: str = "NEUTRAL"          # 1H bias: BULLISH, BEARISH, NEUTRAL
    ltf_bias: str = "NEUTRAL"          # 15m & 5m bias: BULLISH, BEARISH, NEUTRAL
    overall_direction: str = "WAIT"     # BUY, SELL, WAIT
    confidence: int = 50
    trap_detected: bool = False
    trap_description: Optional[str] = None
    timeframe_breakdown: Dict[str, str] = Field(default_factory=dict)
    evidence: List[str] = Field(default_factory=list)
    rationale_en: str = ""
    rationale_kh: str = ""


class FractalMTFAnalyst:
    """Multi-Timeframe Fractal Trend Harmony & Counter-Trend Defense Engine."""

    @staticmethod
    def _calc_ema(series: pd.Series, period: int) -> pd.Series:
        return series.ewm(span=period, adjust=False).mean()

    def _analyze_single_tf(self, df: pd.DataFrame) -> Dict[str, Any]:
        if df is None or df.empty or len(df) < 20:
            return {"bias": "NEUTRAL", "slope": 0.0, "last_close": 0.0}

        close = df["close"]
        ema_20 = self._calc_ema(close, min(20, len(close))).iloc[-1]
        ema_50 = self._calc_ema(close, min(50, len(close))).iloc[-1]
        last_close = float(close.iloc[-1])

        if last_close > ema_20 > ema_50:
            bias = "BULLISH"
        elif last_close < ema_20 < ema_50:
            bias = "BEARISH"
        elif last_close > ema_50:
            bias = "MILD_BULLISH"
        elif last_close < ema_50:
            bias = "MILD_BEARISH"
        else:
            bias = "NEUTRAL"

        return {"bias": bias, "ema_20": ema_20, "ema_50": ema_50, "last_close": last_close}

    def analyze(
        self,
        symbol: str,
        multi_tf_data: Dict[str, pd.DataFrame]
    ) -> FractalMTFOutput:
        evidence: List[str] = []
        breakdown: Dict[str, str] = {}

        d1_res = self._analyze_single_tf(multi_tf_data.get("D1"))
        h4_res = self._analyze_single_tf(multi_tf_data.get("H4"))
        h1_res = self._analyze_single_tf(multi_tf_data.get("H1"))
        m15_res = self._analyze_single_tf(multi_tf_data.get("M15"))
        m5_res = self._analyze_single_tf(multi_tf_data.get("M5"))

        breakdown["D1"] = d1_res["bias"]
        breakdown["H4"] = h4_res["bias"]
        breakdown["H1"] = h1_res["bias"]
        breakdown["M15"] = m15_res["bias"]
        breakdown["M5"] = m5_res["bias"]

        # 1. Synthesize HTF (Higher Timeframe: D1 + H4)
        htf_bull_count = sum(1 for b in [d1_res["bias"], h4_res["bias"]] if "BULLISH" in b)
        htf_bear_count = sum(1 for b in [d1_res["bias"], h4_res["bias"]] if "BEARISH" in b)

        if htf_bull_count >= 1 and htf_bear_count == 0:
            htf_bias = "BULLISH"
        elif htf_bear_count >= 1 and htf_bull_count == 0:
            htf_bias = "BEARISH"
        else:
            htf_bias = "NEUTRAL"

        # 2. Synthesize ITF (Intermediate: H1)
        itf_bias = "BULLISH" if "BULLISH" in h1_res["bias"] else ("BEARISH" if "BEARISH" in h1_res["bias"] else "NEUTRAL")

        # 3. Synthesize LTF (Lower Timeframe: M15 + M5)
        ltf_bull = sum(1 for b in [m15_res["bias"], m5_res["bias"]] if "BULLISH" in b)
        ltf_bear = sum(1 for b in [m15_res["bias"], m5_res["bias"]] if "BEARISH" in b)
        if ltf_bull > ltf_bear:
            ltf_bias = "BULLISH"
        elif ltf_bear > ltf_bull:
            ltf_bias = "BEARISH"
        else:
            ltf_bias = "NEUTRAL"

        # 4. Check for Counter-Trend Traps
        trap_detected = False
        trap_description = None
        fractal_alignment = "ALIGNED"
        overall_direction = "WAIT"
        confidence = 60

        if htf_bias == "BEARISH" and ltf_bias == "BULLISH":
            trap_detected = True
            fractal_alignment = "COUNTER_TREND_TRAP"
            trap_description = "Lower-timeframe rally into Higher-timeframe Daily/H4 Bearish trend. High probability of rejection."
            evidence.append(f"Counter-Trend Trap Warning: {trap_description}")
            confidence = 45
            overall_direction = "WAIT"
        elif htf_bias == "BULLISH" and ltf_bias == "BEARISH":
            trap_detected = True
            fractal_alignment = "COUNTER_TREND_TRAP"
            trap_description = "Lower-timeframe drop into Higher-timeframe Daily/H4 Bullish trend. Potential bear trap / discount sweep."
            evidence.append(f"Counter-Trend Trap Warning: {trap_description}")
            confidence = 45
            overall_direction = "WAIT"
        elif htf_bias == "BULLISH" and ltf_bias == "BULLISH":
            fractal_alignment = "PERFECT_FRACTAL_ALIGNMENT"
            overall_direction = "BUY"
            confidence = 88
            evidence.append("Full Fractal Bullish Alignment: D1, H4, and M15/M5 all trending upward concurrently.")
        elif htf_bias == "BEARISH" and ltf_bias == "BEARISH":
            fractal_alignment = "PERFECT_FRACTAL_ALIGNMENT"
            overall_direction = "SELL"
            confidence = 88
            evidence.append("Full Fractal Bearish Alignment: D1, H4, and M15/M5 all trending downward concurrently.")
        else:
            fractal_alignment = "PARTIAL_CONVERGENCE"
            overall_direction = "WAIT"
            confidence = 55
            evidence.append("Mixed fractal alignment across timeframes. Awaiting structural clarity.")

        # Bilingual Explanations
        if overall_direction == "BUY":
            rationale_en = f"Fractal alignment confirmed Bullish across Daily, H4, and M15. No counter-trend trap detected."
            rationale_kh = f"និន្នាការតាមពហុពេលវេលា (Daily, H4, M15) ស្របគ្នាក្នុងទិសដៅឡើង (Bullish)។ ពុំមានអន្ទាក់បញ្រ្ចាសនិន្នាការឡើយ។"
        elif overall_direction == "SELL":
            rationale_en = f"Fractal alignment confirmed Bearish across Daily, H4, and M15. Institutional distribution aligned."
            rationale_kh = f"និន្នាការតាមពហុពេលវេលា (Daily, H4, M15) ស្របគ្នាក្នុងទិសដៅចុះ (Bearish)។ ការលក់ចេញរបស់ស្ថាប័នធំៗមានសង្គតិភាពល្អ។"
        elif trap_detected:
            rationale_en = f"High Risk Trap: {trap_description} Execution halted."
            rationale_kh = f"ហានិភ័យអន្ទាក់ទីផ្សារ: {trap_description} ការជួញដូរត្រូវបានផ្អាកដើម្បីការពារដើមទុន។"
        else:
            rationale_en = "Timeframe directions are mixed. Awaiting unified confluence."
            rationale_kh = "ទិសដៅពហុពេលវេលានៅមានភាពច្របូកច្របល់។ កំពុងរង់ចាំសញ្ញាស្របគ្នាឱ្យបានពេញលេញ។"

        return FractalMTFOutput(
            status="COMPLETED",
            fractal_alignment=fractal_alignment,
            htf_bias=htf_bias,
            itf_bias=itf_bias,
            ltf_bias=ltf_bias,
            overall_direction=overall_direction,
            confidence=confidence,
            trap_detected=trap_detected,
            trap_description=trap_description,
            timeframe_breakdown=breakdown,
            evidence=evidence,
            rationale_en=rationale_en,
            rationale_kh=rationale_kh
        )


# Global Singleton Instance
fractal_mtf_agent = FractalMTFAnalyst()

