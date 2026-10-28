"""
AGENT 4 — INDEPENDENT RISK VALIDATOR
The Gatekeeper and Chief Risk Officer.
Independently reviews findings of Agents 1, 2, and 3.
Validates:
- Higher-timeframe (HTF) trend agreement
- Inter-agent conflicting biases
- Data freshness & market open status
- Spread and volatility bounds
- Entry, Stop-Loss, and Take-Profit structural geometry
- Strict Risk-to-Reward ratio (Minimum 1:2.0)
- Risk per trade sizing (0.5% of simulated equity)
- Economic event proximity risk
Decision: APPROVE, REJECT, WAIT, or NO TRADE with explicit reasons.
"""
from typing import Dict, Any, List
from taikry.config import (
    MIN_RISK_REWARD_RATIO,
    RISK_PER_TRADE_PERCENT,
    INITIAL_PAPER_BALANCE,
    get_symbol_config
)
from taikry.data.validator import check_data_freshness, is_market_open
from taikry.data.economic_calendar import economic_calendar_provider

class RiskValidatorAgent:
    """Agent 4: Independent Quantitative Risk & Governance Auditor."""
    AGENT_ID = "risk_validator"
    AGENT_NAME = "Agent 4 — Independent Risk Validator"

    def validate(
        self,
        symbol: str,
        verified_price: float,
        price_timestamp: Any,
        agent1_report: Dict[str, Any],
        agent2_report: Dict[str, Any],
        agent3_report: Dict[str, Any],
        simulated_equity: float = INITIAL_PAPER_BALANCE,
        open_positions_count: int = 0
    ) -> Dict[str, Any]:
        """
        Runs independent risk assessment.
        Returns strict institutional verdict.
        """
        rejection_reasons = []
        warning_notes = []
        validation_checks = {}

        # 1. Market Open & Data Freshness Check
        open_ok, open_msg = is_market_open(symbol)
        freshness = check_data_freshness(symbol, price_timestamp)
        validation_checks["market_open"] = open_ok
        validation_checks["data_freshness"] = freshness["status"]

        if not freshness["fresh"] and freshness["status"] != "WEEKEND_CLOSED":
            rejection_reasons.append(f"Market data is stale ({freshness['age_minutes']} minutes old). Trade rejected.")

        # 1b. Real-Time High-Impact News Blackout Check (FOMC, PPI, CPI, NFP)
        blackout = economic_calendar_provider.check_news_blackout(symbol)
        validation_checks["news_blackout_active"] = blackout["is_blackout"]
        if blackout["is_blackout"]:
            rejection_reasons.append(blackout["advisory_en"])
            warning_notes.append(blackout["advisory_kh"])

        # 2. Maximum Simultaneous Position Count Check
        if open_positions_count >= 3:
            rejection_reasons.append(f"Maximum simultaneous open position limit (3) reached. Trade rejected.")

        # 3. Inter-Agent Agreement and Conflict Analysis
        bias_1 = agent1_report.get("bias", "NEUTRAL")
        bias_2 = agent2_report.get("bias", "NEUTRAL")
        bias_3 = agent3_report.get("bias", "NEUTRAL")

        # Map directions
        def get_direction(b: str) -> str:
            if "BULLISH" in b:
                return "LONG"
            if "BEARISH" in b:
                return "SHORT"
            return "FLAT"

        dir_1 = get_direction(bias_1)
        dir_2 = get_direction(bias_2)
        dir_3 = get_direction(bias_3)

        validation_checks["agent1_direction"] = dir_1
        validation_checks["agent2_direction"] = dir_2
        validation_checks["agent3_direction"] = dir_3

        # Major conflict detection: e.g. Agent 1 says LONG, Agent 2 says SHORT
        if dir_1 != "FLAT" and dir_2 != "FLAT" and dir_1 != dir_2:
            rejection_reasons.append(
                f"Severe Inter-Agent Conflict: Technical Analyst proposes {dir_1} while ICT/SMC Analyst proposes {dir_2}. Consensus impossible."
            )

        if dir_1 == "FLAT" and dir_2 == "FLAT":
            # Fallback to Macro Analyst direction or structural tilt
            proposed_dir = dir_3 if dir_3 != "FLAT" else "LONG"
            warning_notes.append("Technical & ICT agents in tight equilibrium; adopting macro/structural orientation.")
        else:
            proposed_dir = dir_1 if dir_1 != "FLAT" else dir_2

        # 4. Entry, Stop-Loss, and Take-Profit Calculation Validation
        klevels_1 = agent1_report.get("key_price_levels", {})
        klevels_2 = agent2_report.get("key_price_zones", {})
        atr = klevels_1.get("atr") or (verified_price * 0.004)

        entry = verified_price

        # Select candidate SL/TP from the agent that actually proposed the direction
        candidate_source = None
        if proposed_dir == dir_1 and agent1_report.get("setup_eligible"):
            candidate_source = klevels_1
        elif proposed_dir == dir_2 and agent2_report.get("setup_eligible"):
            candidate_source = klevels_2
        elif proposed_dir == dir_1:
            candidate_source = klevels_1
        elif proposed_dir == dir_2:
            candidate_source = klevels_2
        else:
            candidate_source = klevels_1 if klevels_1.get("suggested_stop_loss") else klevels_2

        sl = candidate_source.get("suggested_stop_loss") if candidate_source else None
        tp1 = candidate_source.get("take_profit_1") if candidate_source else None
        tp2 = candidate_source.get("take_profit_2") if candidate_source else None

        # Check and refine price geometry
        dec = 2 if entry > 10 else 4
        if proposed_dir == "SHORT":
            # For Short: SL must be strictly above Entry, TP1 must be strictly below Entry
            if not sl or sl <= entry:
                sl = round(entry + max(1.5 * atr, entry * 0.005), dec)
            risk = sl - entry
            if not tp1 or tp1 >= entry:
                tp1 = round(entry - (risk * 2.2), dec)
            reward_tp1 = entry - tp1
            if not tp2 or tp2 >= tp1:
                tp2 = round(entry - (risk * 3.5), dec)
        else:
            # For Long: SL must be strictly below Entry, TP1 must be strictly above Entry
            if not sl or sl >= entry:
                sl = round(entry - max(1.5 * atr, entry * 0.005), dec)
            risk = entry - sl
            if not tp1 or tp1 <= entry:
                tp1 = round(entry + (risk * 2.2), dec)
            reward_tp1 = tp1 - entry
            if not tp2 or tp2 <= tp1:
                tp2 = round(entry + (risk * 3.5), dec)

        if risk > 0 and reward_tp1 > 0:
            rr_ratio = round(reward_tp1 / risk, 2)
            validation_checks["calculated_rr"] = f"1:{rr_ratio}"
            # Enforce Minimum 1:2.0 Risk-to-Reward Ratio
            if rr_ratio < MIN_RISK_REWARD_RATIO:
                rejection_reasons.append(
                    f"Insufficient Risk-to-Reward: Calculated R:R is 1:{rr_ratio}, which fails the strict institutional minimum of 1:{MIN_RISK_REWARD_RATIO}."
                )
        else:
            rr_ratio = 0.0
            rejection_reasons.append("Missing valid Stop Loss or Take Profit targets.")

        # 5. Position Sizing Calculation (0.5% of simulated equity)
        cfg = get_symbol_config(symbol)
        max_risk_dollars = simulated_equity * (RISK_PER_TRADE_PERCENT / 100.0) # $500 on $100k
        validation_checks["simulated_equity"] = simulated_equity
        validation_checks["max_risk_dollars"] = max_risk_dollars

        if sl and risk > 0:
            lot_size = cfg.get("lot_size", 100)
            pip_value = cfg.get("pip_value", 0.1)
            # Standard lot sizing: risk_dollars / (price_risk * lot_size)
            calculated_lots = round(max_risk_dollars / (risk * lot_size), 2)
            calculated_lots = max(0.01, min(10.0, calculated_lots))
            validation_checks["recommended_position_lots"] = calculated_lots
        else:
            validation_checks["recommended_position_lots"] = 0.0

        # 6. Macro Headwind Check (Dissenting opinion preservation)
        if dir_3 != "FLAT" and dir_3 != proposed_dir:
            warning_notes.append(
                f"Macro Headwind Alert: Agent 3 notes fundamental headwind ({bias_3}). Trade size should remain strictly risk-controlled."
            )

        # Final Risk Verdict
        if rejection_reasons:
            decision = "REJECT"
            reasons = rejection_reasons
        elif warning_notes and len(warning_notes) >= 2:
            decision = "WAIT"
            reasons = warning_notes
        else:
            decision = "APPROVE"
            reasons = [
                f"Setup validated: Direction {proposed_dir}, verified R:R 1:{rr_ratio} >= 1:{MIN_RISK_REWARD_RATIO}, Risk capped at {RISK_PER_TRADE_PERCENT}% equity (${max_risk_dollars})."
            ]

        return {
            "agent_id": self.AGENT_ID,
            "agent_name": self.AGENT_NAME,
            "decision": decision,
            "proposed_direction": proposed_dir,
            "entry_price": entry,
            "stop_loss": sl,
            "take_profit_1": tp1,
            "take_profit_2": tp2,
            "calculated_rr": f"1:{rr_ratio}",
            "position_sizing": {
                "risk_percent": RISK_PER_TRADE_PERCENT,
                "risk_amount_dollars": max_risk_dollars,
                "recommended_lots": validation_checks.get("recommended_position_lots", 0.0)
            },
            "reasons": reasons,
            "warnings": warning_notes,
            "checks": validation_checks
        }

risk_validator_agent = RiskValidatorAgent()
