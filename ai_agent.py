"""Compatibility interface backed by TAIKRY's verified consensus engine.

Legacy code in this module generated rule-based trade levels and macro claims
without checking a live feed. This adapter delegates analysis to the current
pipeline, which validates market data, calendar availability, and risk first.
"""

from typing import Any, Dict, Optional

SYSTEM_PROMPT = "Use only verified live market analysis. If data, calendar risk, geometry, or configured risk checks fail, return HOLD with no actionable levels."

def generate_signal(
    symbol_info: dict,
    timeframe: str,
    metrics: dict,
    preferred_provider: Optional[str] = None,
) -> Dict[str, Any]:
    """Return verified consensus output; caller-supplied metrics are not trusted."""
    symbol = str((symbol_info or {}).get("symbol", "")).strip().upper()
    if not symbol:
        return _locked_result("Missing symbol; verified analysis was not run.")

    try:
        from taikry.agents.consensus_engine import ai_consensus_engine

        result = ai_consensus_engine.analyze_symbol(
            symbol,
            preferred_llm=preferred_provider or "quant",
            force_refresh=True,
        )
    except Exception as exc:
        return _locked_result(f"Verified consensus analysis failed: {type(exc).__name__}.")

    approved = (
        result.get("setup_status") == "APPROVE"
        and result.get("proposed_direction") in {"LONG", "SHORT", "BUY", "SELL"}
        and 80 <= (result.get("ai_score") or result.get("confidence_score") or 0) <= 95
        and result.get("entry_price") is not None
        and result.get("stop_loss") is not None
        and result.get("take_profit_1") is not None
    )
    if not approved:
        return {
            **result,
            "action": "HOLD",
            "status": result.get("setup_status", "NO TRADE"),
            "entry_price": None,
            "stop_loss": None,
            "take_profit_1": None,
            "take_profit_2": None,
            "risk_reward_ratio": "N/A",
        }

    direction = result.get("proposed_direction")
    return {
        **result,
        "action": "BUY" if direction in {"LONG", "BUY"} else "SELL",
        "status": "APPROVED",
        "confidence": result.get("ai_score", result.get("confidence_score")),
        "rationale": result.get("smart_analysis", {}).get("synthesis_summary_en", ""),
        "rationale_kh": result.get("smart_analysis", {}).get("synthesis_summary_kh", ""),
    }


def _locked_result(reason: str) -> Dict[str, Any]:
    return {
        "action": "HOLD",
        "status": "NO TRADE",
        "confidence": None,
        "entry_price": None,
        "stop_loss": None,
        "take_profit_1": None,
        "take_profit_2": None,
        "risk_reward_ratio": "N/A",
        "rationale": reason,
        "rationale_kh": "ទិន្នន័យទីផ្សារមិនអាចផ្ទៀងផ្ទាត់បានទេ ដូច្នេះមិនបង្កើតសញ្ញាជួញដូរឡើយ។",
        "smart_analysis": {
            "synthesis_summary_en": reason,
            "synthesis_summary_kh": "ទិន្នន័យទីផ្សារមិនអាចផ្ទៀងផ្ទាត់បានទេ ដូច្នេះមិនបង្កើតសញ្ញាជួញដូរឡើយ។",
            "technical_causes": [],
            "smc_causes": [],
            "macro_causes": ["Macro data was not verified."],
            "risk_causes": [reason],
            "checklist": {
                "multi_agent_consensus": False,
                "institutional_liquidity_clear": False,
                "macro_dxy_aligned": False,
                "risk_reward_viable": False,
            },
        },
    }


def run_live_multi_agent_analysis(symbol: str = "XAUUSD", timeframe: str = "M15") -> dict:
    """Compatibility helper that runs the verified consensus analysis."""
    from taikry.agents.consensus_engine import ai_consensus_engine

    return ai_consensus_engine.analyze_symbol(symbol, force_refresh=True)


def _normalize_llm_output(data: dict, metrics: dict) -> dict:
    """Compatibility adapter; rechecks outputs through the verified server pipeline."""
    if not data:
        return _locked_result("No verified analysis result was provided.")
    symbol = str(data.get("symbol") or "").strip().upper()
    if not symbol:
        return _locked_result("Output does not contain a verified symbol.")
    from taikry.agents.consensus_engine import ai_consensus_engine

    return ai_consensus_engine.analyze_symbol(symbol, force_refresh=True)


def analyze_with_gemini(symbol_info: dict, timeframe: str, metrics: dict) -> dict:
    return generate_signal(symbol_info, timeframe, metrics, preferred_provider="gemini")


def analyze_with_claude(symbol_info: dict, timeframe: str, metrics: dict) -> dict:
    return generate_signal(symbol_info, timeframe, metrics, preferred_provider="claude")


def analyze_with_openai(symbol_info: dict, timeframe: str, metrics: dict) -> dict:
    return generate_signal(symbol_info, timeframe, metrics, preferred_provider="openai")


def analyze_with_deepseek(symbol_info: dict, timeframe: str, metrics: dict) -> dict:
    return generate_signal(symbol_info, timeframe, metrics, preferred_provider="deepseek")


def analyze_with_manus(symbol_info: dict, timeframe: str, metrics: dict) -> dict:
    return generate_signal(symbol_info, timeframe, metrics, preferred_provider="manus")


def analyze_with_rule_engine(symbol_info: dict, timeframe: str, metrics: dict) -> dict:
    return generate_signal(symbol_info, timeframe, metrics, preferred_provider="quant")


def get_supported_ai_agents() -> dict:
    """Return the registered analysis agents and connected LLM status."""
    from taikry.agents.registry import agent_registry
    from taikry.ai.llm_client import get_llm_status

    return {
        "institutional_agents": [
            agent.get("agent_id", "unknown") for agent in agent_registry.list_agents()
        ],
        "frontier_llms": get_llm_status(),
        "supported_providers": ["configured consensus providers"],
    }
