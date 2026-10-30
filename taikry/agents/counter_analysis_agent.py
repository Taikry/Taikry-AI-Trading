"""
TAIKRY AI MARKET INTELLIGENCE — Counter-Analysis & Devil's Advocate Critic (Agent 12)
=====================================================================================
Acts as an adversarial challenger to stress-test any proposed long/short thesis.
Identifies opposing liquidity traps, invalidation thresholds, and adverse excursion risks.
"""
import logging
from typing import Dict, Any, List

logger = logging.getLogger("taikry.agents.counter_analysis")

class CounterAnalysisAgent:
    """Stress tests consensus theses to identify tail-risk scenarios and false breakouts."""

    def __init__(self):
        self.agent_id = "counter_analysis_agent"
        self.name = "Agent 12: Counter-Analysis & Devil's Advocate Critic"

    def critique(
        self,
        symbol: str,
        proposed_direction: str,
        entry_price: float,
        stop_loss: float,
        take_profit_1: float,
        technical_report: Dict[str, Any],
        smc_report: Dict[str, Any],
        macro_report: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Critically evaluates the proposed direction and finds failure modes.
        """
        direction = proposed_direction.upper()
        if direction not in ("BUY", "LONG", "SELL", "SHORT"):
            return {
                "agent_id": self.agent_id,
                "agent_name": self.name,
                "critique_stance": "NEUTRAL",
                "challenge_points": ["No trade proposed; counter-analysis stands by."],
                "invalidation_price": 0.0,
                "fragility_score": 0
            }

        challenges: List[str] = []
        fragility = 20  # Base fragility points

        if direction in ("BUY", "LONG"):
            opposing_bias = "BEARISH"
            # Challenge Long: Are we buying into premium supply or major resistance?
            if "BEARISH" in str(technical_report.get("bias", "")):
                challenges.append("Adversarial Warning: Higher timeframe momentum is still bearish; buying may be a dead-cat bounce.")
                fragility += 30
            if "BEARISH" in str(macro_report.get("bias", "")) or "BULLISH" in str(macro_report.get("usd_index", {}).get("usd_bias", "")):
                challenges.append("Macro Resistance: US Dollar strength creates persistent downward pressure on Gold.")
                fragility += 25
            if entry_price > stop_loss and (entry_price - stop_loss) > 15.0:
                challenges.append("Stop Distance Risk: Required stop exceeds 15 points, exposing position to wider adverse excursion.")
                fragility += 15

            invalidation = stop_loss - 0.50
        else:
            opposing_bias = "BULLISH"
            # Challenge Short: Are we selling the low of a discount demand pool?
            if "BULLISH" in str(technical_report.get("bias", "")):
                challenges.append("Adversarial Warning: Higher timeframe momentum is bullish; shorting risks getting caught in trend continuation.")
                fragility += 30
            if "BEARISH" in str(macro_report.get("usd_index", {}).get("usd_bias", "")):
                challenges.append("Macro Tail-Risk: DXY weakness fuels persistent bids in Gold.")
                fragility += 25
            if stop_loss > entry_price and (stop_loss - entry_price) > 15.0:
                challenges.append("Stop Distance Risk: Short stop distance exceeds 15 points.")
                fragility += 15

            invalidation = stop_loss + 0.50

        if not challenges:
            challenges.append("Stress-test cleared: Setup conforms with multi-timeframe liquidity and risk parameters.")
            stance = "CHALLENGE_CLEARED"
        else:
            stance = "CRITIQUE_ACTIVE"

        return {
            "agent_id": self.agent_id,
            "agent_name": self.name,
            "critique_stance": stance,
            "fragility_score": min(100, fragility),
            "challenge_points": challenges,
            "hard_invalidation_level": round(invalidation, 2),
            "evidence": challenges,
            "rationale": f"Devil's Advocate assessed {direction} setup: fragility rated at {fragility}/100."
        }

counter_analysis_agent = CounterAnalysisAgent()

