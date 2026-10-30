"""
TAIKRY AI MARKET INTELLIGENCE — Execution Simulation Agent (Agent 16)
=====================================================================
Calculates real-world execution friction:
- Spread cost modeling (bid/ask gap)
- Round-turn commission ($7.00 per standard lot = $0.07 per oz on Gold)
- Dynamic slippage estimates based on volatility and spread expansion
- Net effective R:R and break-even slippage tolerance
"""
import logging
from typing import Dict, Any, List

logger = logging.getLogger("taikry.agents.execution_simulation")

COMMISSION_PER_STANDARD_LOT = 7.00  # $7 per 100 oz = $0.07/oz

class ExecutionSimulationAgent:
    """Accurately calculates execution friction, slippage, and effective risk-reward."""

    def __init__(self):
        self.agent_id = "execution_simulation_agent"
        self.name = "Agent 16: Execution Simulation Agent"

    def simulate_execution(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        take_profit_1: float,
        current_spread_points: float = 0.25,
        volatility_state: str = "NORMAL_LIQUIDITY"
    ) -> Dict[str, Any]:
        """
        Simulates the execution friction on entry and exit.
        """
        dir_upper = direction.upper()
        # Slippage estimate based on volatility regime
        if volatility_state == "HIGH_VOLATILITY_EXPANSION":
            est_slippage_points = 0.35
        elif volatility_state == "SQUEEZE_COMPRESSION":
            est_slippage_points = 0.10
        else:
            est_slippage_points = 0.15

        spread_cost = current_spread_points
        comm_per_unit = COMMISSION_PER_STANDARD_LOT / 100.0  # $0.07 on Gold

        total_friction_points = spread_cost + est_slippage_points + comm_per_unit

        # Calculate effective fill price
        if dir_upper in ("BUY", "LONG"):
            effective_entry = entry_price + (spread_cost / 2.0) + est_slippage_points
            gross_reward = take_profit_1 - entry_price
            gross_risk = entry_price - stop_loss
        else:
            effective_entry = entry_price - (spread_cost / 2.0) - est_slippage_points
            gross_reward = entry_price - take_profit_1
            gross_risk = stop_loss - entry_price

        net_reward = max(0.01, gross_reward - total_friction_points)
        net_risk = gross_risk + total_friction_points
        net_rr = round(net_reward / net_risk, 2) if net_risk > 0 else 0.0

        evidence: List[str] = [
            f"Nominal Entry: {entry_price:.2f} -> Net Effective Fill: {effective_entry:.2f} (friction: {total_friction_points:.2f} pts).",
            f"Spread Cost: {spread_cost:.2f} pts | Commission: ${comm_per_unit:.2f}/oz | Est. Slippage: {est_slippage_points:.2f} pts.",
            f"Gross R:R: {gross_reward/gross_risk:.2f}:1 -> Net Post-Friction R:R: {net_rr:.2f}:1."
        ]

        is_viable = net_rr >= 1.80  # Net R:R must remain >= 1:1.8 after all friction

        return {
            "agent_id": self.agent_id,
            "agent_name": self.name,
            "nominal_entry": entry_price,
            "effective_fill_price": round(effective_entry, 2),
            "estimated_slippage_points": est_slippage_points,
            "spread_points": spread_cost,
            "commission_per_unit": comm_per_unit,
            "total_friction_points": round(total_friction_points, 2),
            "net_risk_reward": net_rr,
            "is_execution_viable": is_viable,
            "evidence": evidence,
            "rationale": f"Effective fill calculated at {effective_entry:.2f}; net post-friction R:R is {net_rr:.2f}."
        }

execution_simulation_agent = ExecutionSimulationAgent()

