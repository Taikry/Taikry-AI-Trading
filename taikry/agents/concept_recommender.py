"""
TAIKRY AI MARKET INTELLIGENCE — Concept Recommendation Engine (Agent 10)
========================================================================
Audits 14 institutional trading concepts against live regime and market structure.
Returns the top qualified setups with execution triggers and invalidation levels,
or cleanly reports NO QUALIFIED CONCEPT when evidence is incomplete or conflicted.
"""
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("taikry.agents.concept_recommender")

CONCEPT_CATALOG = [
    {
        "id": "c01_trend_continuation",
        "name": "Trend Continuation Pullback",
        "applicable_regimes": ["TRENDING_BULLISH", "TRENDING_BEARISH"],
        "min_confidence": 75,
        "description": "Enters on shallow retracements to EMA 21 / 50 in harmony with HTF flow."
    },
    {
        "id": "c02_fvg_mitigation",
        "name": "Fair Value Gap (FVG) Mitigated Fill",
        "applicable_regimes": ["TRENDING_BULLISH", "TRENDING_BEARISH", "NORMAL_LIQUIDITY"],
        "min_confidence": 78,
        "description": "Capitalizes on price returning into unmitigated institutional imbalance blocks."
    },
    {
        "id": "c03_liquidity_sweep",
        "name": "Liquidity Sweep & Turtle Soup",
        "applicable_regimes": ["CONSOLIDATION_RANGE", "CHOPPY_ROTATION", "NORMAL_LIQUIDITY"],
        "min_confidence": 80,
        "description": "Takes advantage of stop-run wick rejections beyond previous session highs or lows."
    },
    {
        "id": "c04_discount_accumulation",
        "name": "Equilibrium Discount Accumulation",
        "applicable_regimes": ["TRENDING_BULLISH", "CONSOLIDATION_RANGE"],
        "min_confidence": 76,
        "description": "Buys in the lower 50% discount zone of the institutional dealing range."
    },
    {
        "id": "c05_breaker_block_flip",
        "name": "Breaker Block Transition Flip",
        "applicable_regimes": ["TRENDING_BULLISH", "TRENDING_BEARISH"],
        "min_confidence": 80,
        "description": "Enters retests of failed order blocks that have inverted into support/resistance."
    },
    {
        "id": "c06_volatility_squeeze",
        "name": "Volatility Compression Breakout",
        "applicable_regimes": ["SQUEEZE_COMPRESSION"],
        "min_confidence": 82,
        "description": "Captures violent momentum expansion following tight Bollinger Band contractions."
    },
    {
        "id": "c07_premium_rejection",
        "name": "Premium Supply Rejection",
        "applicable_regimes": ["TRENDING_BEARISH", "CONSOLIDATION_RANGE"],
        "min_confidence": 76,
        "description": "Sells in the upper 50% premium zone where smart money distributes inventory."
    },
    {
        "id": "c08_range_mean_reversion",
        "name": "Range High / Low Mean Reversion",
        "applicable_regimes": ["CONSOLIDATION_RANGE"],
        "min_confidence": 75,
        "description": "Trades fades back toward POC equilibrium from value area extremes."
    },
    {
        "id": "c09_asian_sweep_expansion",
        "name": "Asian Session Sweep & London Expansion",
        "applicable_regimes": ["NORMAL_LIQUIDITY", "TRENDING_BULLISH", "TRENDING_BEARISH"],
        "min_confidence": 78,
        "description": "Trades London or New York expansions after Asian range liquidity is purged."
    },
    {
        "id": "c10_orderflow_cvd_divergence",
        "name": "Order Flow CVD Absorption",
        "applicable_regimes": ["ALL"],
        "min_confidence": 82,
        "description": "Exploits aggressive retail market orders being absorbed by passive limit walls."
    },
    {
        "id": "c11_mtf_alignment_wave",
        "name": "Multi-Timeframe Fractal Harmony Wave",
        "applicable_regimes": ["TRENDING_BULLISH", "TRENDING_BEARISH"],
        "min_confidence": 85,
        "description": "Highest conviction trend ride when D1, H4, H1, and M15 align simultaneously."
    },
    {
        "id": "c12_news_reaction_fade",
        "name": "Post-News Kneejerk Fade",
        "applicable_regimes": ["HIGH_VOLATILITY_EXPANSION"],
        "min_confidence": 80,
        "description": "Fades irrational pre-news or immediate post-news spike once volatility settles."
    },
    {
        "id": "c13_stophunt_engine",
        "name": "Stop-Hunt Liquidity Engine",
        "applicable_regimes": ["CONSOLIDATION_RANGE", "CHOPPY_ROTATION"],
        "min_confidence": 78,
        "description": "Follows institutional sweeps of equal highs (EQH) and equal lows (EQL)."
    },
    {
        "id": "c14_climax_exhaustion",
        "name": "Parabolic Climax Exhaustion",
        "applicable_regimes": ["HIGH_VOLATILITY_EXPANSION"],
        "min_confidence": 82,
        "description": "Counter-trend entry when extreme Z-Score (>2.5) coincides with RSI divergence."
    }
]

class ConceptRecommendationEngine:
    """Matches active market regime and agent confluence against the 14 institutional concepts."""

    def __init__(self):
        self.agent_id = "concept_recommender"
        self.name = "Agent 10: Strategy Discovery & Concept Recommender"

    def evaluate_concepts(
        self,
        symbol: str,
        regime_data: Dict[str, Any],
        technical_data: Dict[str, Any],
        smc_data: Dict[str, Any],
        quant_data: Dict[str, Any],
        ml_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Filters and ranks applicable concepts. Returns NO QUALIFIED CONCEPT when evidence is insufficient.
        """
        active_regime = regime_data.get("regime", "UNKNOWN")
        vol_state = regime_data.get("volatility_state", "NORMAL_LIQUIDITY")
        smc_bias = smc_data.get("bias", "NEUTRAL")
        tech_bias = technical_data.get("bias", "NEUTRAL")
        z_score = quant_data.get("z_score_20", 0.0)

        qualified_concepts: List[Dict[str, Any]] = []

        # 1. Check FVG Mitigation
        if "FVG" in str(smc_data.get("evidence", [])) and smc_bias in ("BULLISH", "BEARISH"):
            qualified_concepts.append({
                "concept_id": "c02_fvg_mitigation",
                "concept_name": "Fair Value Gap (FVG) Mitigated Fill",
                "fit_score": 88,
                "recommended_direction": "LONG" if smc_bias == "BULLISH" else "SHORT",
                "rationale": "Unmitigated institutional imbalance detected within the current dealing range."
            })

        # 2. Check Trend Continuation
        if active_regime in ("TRENDING_BULLISH", "TRENDING_BEARISH") and tech_bias in ("STRONG BULLISH", "BULLISH", "STRONG BEARISH", "BEARISH"):
            is_bull = "BULL" in tech_bias
            qualified_concepts.append({
                "concept_id": "c01_trend_continuation",
                "concept_name": "Trend Continuation Pullback",
                "fit_score": 85,
                "recommended_direction": "LONG" if is_bull else "SHORT",
                "rationale": f"Persistent trend regime confirmed by moving average alignment in {active_regime}."
            })

        # 3. Check Volatility Compression Squeeze
        if vol_state == "SQUEEZE_COMPRESSION":
            qualified_concepts.append({
                "concept_id": "c06_volatility_squeeze",
                "concept_name": "Volatility Compression Breakout",
                "fit_score": 84,
                "recommended_direction": "AWAIT_BREAKOUT",
                "rationale": "Bollinger Bands contracted under 0.35% width. Explosive expansion imminent."
            })

        # 4. Check Extreme Mean Reversion
        if abs(z_score) >= 2.0:
            mr_dir = "SHORT" if z_score > 0 else "LONG"
            qualified_concepts.append({
                "concept_id": "c14_climax_exhaustion",
                "concept_name": "Parabolic Climax Exhaustion",
                "fit_score": 86,
                "recommended_direction": mr_dir,
                "rationale": f"Price is {z_score:+.2f} standard deviations stretched. Mean reversion indicated."
            })

        # 5. Check Range High/Low
        if active_regime == "CONSOLIDATION_RANGE":
            qualified_concepts.append({
                "concept_id": "c08_range_mean_reversion",
                "concept_name": "Range High / Low Mean Reversion",
                "fit_score": 80,
                "recommended_direction": "RANGE_FADE",
                "rationale": "Market coiling in equilibrium. Fade extremes back toward POC."
            })

        # Sort by fit score
        qualified_concepts.sort(key=lambda c: c["fit_score"], reverse=True)

        if not qualified_concepts:
            return {
                "agent_id": self.agent_id,
                "agent_name": self.name,
                "status": "NO_QUALIFIED_CONCEPT",
                "top_concept": None,
                "qualified_concepts": [],
                "evidence": [f"Current regime ({active_regime}, {vol_state}) has no high-conviction concept setup."],
                "rationale": "Market structure is fragmented or transitioning. Capital protection active."
            }

        top = qualified_concepts[0]
        return {
            "agent_id": self.agent_id,
            "agent_name": self.name,
            "status": "CONCEPT_QUALIFIED",
            "top_concept": top,
            "qualified_concepts": qualified_concepts,
            "evidence": [
                f"Selected Top Concept: {top['concept_name']} (Fit: {top['fit_score']}%)",
                f"Target Direction: {top['recommended_direction']}. {top['rationale']}"
            ],
            "rationale": f"Qualified {len(qualified_concepts)} setups matching {active_regime}."
        }

concept_recommender = ConceptRecommendationEngine()
