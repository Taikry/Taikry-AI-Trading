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
from typing import Dict, Any, List, Optional
from taikry.config import get_symbol_config

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
        volatility_state: str = "NORMAL_LIQUIDITY",
        commission_per_unit: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Simulates the execution friction on entry and exit.
        """
        dir_upper = direction.upper()
        # Convert pip-scaled friction into the instrument's quoted price units.
        # For XAUUSD pip_value=0.10 retains the legacy 0.10-0.35 point model.
        symbol_cfg = get_symbol_config(symbol)
        try:
            pip_value = max(0.000001, float(symbol_cfg.get("pip_value", 0.10)))
        except (TypeError, ValueError):
            pip_value = 0.10

        # Slippage estimate based on volatility regime
        if volatility_state == "HIGH_VOLATILITY_EXPANSION":
            est_slippage_points = 3.5 * pip_value
        elif volatility_state == "SQUEEZE_COMPRESSION":
            est_slippage_points = 1.0 * pip_value
        else:
            est_slippage_points = 1.5 * pip_value

        spread_cost = current_spread_points
        if commission_per_unit is None:
            comm_per_unit = COMMISSION_PER_STANDARD_LOT / 100.0  # Default XAUUSD contract: 100 oz/lot
        else:
            try:
                comm_per_unit = max(0.0, float(commission_per_unit))
            except (TypeError, ValueError):
                comm_per_unit = COMMISSION_PER_STANDARD_LOT / 100.0

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

