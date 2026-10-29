"""
Multi-Agent AI Orchestration Layer for ZYROX AI Terminal.
Implements the 7-Agent Institutional Deep Analysis Workflow with AnyRouter Inference Integration.

Agents:
1. Orchestrator (workflow coordinator, data freshness pre-checks, telemetry & trace)
2. Market Structure Agent (ICT/SMC, liquidity sweeps, order blocks, FVG, regime)
3. Multi-Timeframe Agent (EMA 20/50/200, RSI, ATR confluence across M5/M15/H1/H4)
4. Macro/News Agent (real sources: economic calendar, news blackout, sentiment)
5. Risk Guardian (deterministic risk arithmetic, configured R:R floor and risk cap, spread check)
6. Independent Critic (devil's advocate, contrarian objections, trapped trader risk, invalidation)
7. Final Synthesis Agent (bilingual English & Natural Khmer thesis, structured execution levels)
"""

import math
import time
import uuid
import datetime
import logging
from typing import Dict, Any, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from pydantic import BaseModel, Field

from taikry.config import (
    MIN_RISK_REWARD_RATIO,
    RISK_PER_TRADE_PERCENT,
    INITIAL_PAPER_BALANCE,
    get_symbol_config,
    LOCAL_TIMEZONE
)
from taikry.ai.anyrouter_client import anyrouter_client, budget_manager
from taikry.indicators.technical import compute_technical_indicators, extract_technical_summary
from taikry.indicators.ict_smc import extract_ict_smc_summary
from taikry.data.validator import is_market_open, check_data_freshness, validate_dataframe
from taikry.data.economic_calendar import economic_calendar_provider
from taikry.data.mt5_receiver import mt5_receiver
from taikry.data.providers import market_data_engine
from taikry.translation.khmer_translator import translate_to_khmer

logger = logging.getLogger("zyrox.agents.orchestration")


# =============================================================================
# TYPED PYDANTIC SCHEMAS FOR AGENT CONTRACTS
# =============================================================================

class MarketStructureOutput(BaseModel):
    """Structured output for Agent 2: Market Structure."""
    agent_id: str = "market_structure"
    agent_name: str = "Market Structure Agent"
    status: str = "UNAVAILABLE"  # COMPLETED, FAILED, SKIPPED
    trend: str = "UNAVAILABLE"  # BULLISH, BEARISH, RANGING
    regime: str = "UNAVAILABLE"  # TRENDING, ACCUMULATION, DISTRIBUTION, CHOPPY
    swing_high: Optional[float] = None
    swing_low: Optional[float] = None
    order_blocks_count: int = 0
    fair_value_gaps_count: int = 0
    recent_sweeps: List[str] = Field(default_factory=list)
    key_levels: Dict[str, float] = Field(default_factory=dict)
    evidence: List[str] = Field(default_factory=list)
    model_used: Optional[str] = None
    latency_ms: float = 0.0
    error: Optional[str] = None


class MultiTimeframeOutput(BaseModel):
    """Structured output for Agent 3: Multi-Timeframe Alignment."""
    agent_id: str = "multi_timeframe"
    agent_name: str = "Multi-Timeframe Agent"
    status: str = "UNAVAILABLE"
    m5_bias: str = "UNAVAILABLE"
    m15_bias: str = "UNAVAILABLE"
    h1_bias: str = "UNAVAILABLE"
    h4_bias: str = "UNAVAILABLE"
    alignment: str = "UNAVAILABLE"  # STRONG ALIGNMENT, MODERATE ALIGNMENT, MIXED
    confluence_score: Optional[int] = None  # 0 to 100 when measured
    dominant_bias: str = "UNAVAILABLE"  # BULLISH, BEARISH, NEUTRAL
    rsi_14: Optional[float] = None
    atr_val: Optional[float] = None
    evidence: List[str] = Field(default_factory=list)
    model_used: Optional[str] = None
    latency_ms: float = 0.0
    error: Optional[str] = None


class MacroNewsOutput(BaseModel):
    """Structured output for Agent 4: Macro & Breaking News."""
    agent_id: str = "macro_news"
    agent_name: str = "Macro/News Agent"
    status: str = "UNAVAILABLE"
    is_connected: bool = False
    is_blackout: bool = False
    calendar_available: bool = False
    dxy_available: bool = False
    blackout_reason: Optional[str] = None
    news_sentiment: str = "UNAVAILABLE"  # BULLISH_FOR_ASSET, BEARISH_FOR_ASSET, NEUTRAL
    dxy_bias: str = "UNAVAILABLE"
    upcoming_events_count: int = 0
    active_sources: List[str] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)
    model_used: Optional[str] = None
    latency_ms: float = 0.0
    error: Optional[str] = None


class RiskGuardianOutput(BaseModel):
    """Structured output for Agent 5: Risk Guardian (100% Deterministic)."""
    agent_id: str = "risk_guardian"
    agent_name: str = "Risk Guardian"
    status: str = "UNAVAILABLE"
    approved: bool = False
    veto_reasons: List[str] = Field(default_factory=list)
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    risk_reward_ratio: Optional[float] = None
    min_required_rr: float = MIN_RISK_REWARD_RATIO
    max_risk_percent: float = RISK_PER_TRADE_PERCENT
    account_equity: Optional[float] = None
    risk_amount_usd: Optional[float] = None
    recommended_lot_size: Optional[float] = None
    spread_points: Optional[float] = None
    spread_price: Optional[float] = None
    latency_ms: float = 0.0


class CriticOutput(BaseModel):
    """Structured output for Agent 6: Independent Critic (Devil's Advocate)."""
    agent_id: str = "independent_critic"
    agent_name: str = "Independent Critic"
    status: str = "UNAVAILABLE"
    approved: bool = False
    counter_trend_risk: str = "LOW"  # LOW, MEDIUM, HIGH
    trapped_traders_risk: str = "LOW"
    objections: List[str] = Field(default_factory=list)
    opposing_evidence: List[str] = Field(default_factory=list)
    invalidation_triggers: List[str] = Field(default_factory=list)
    critic_score: Optional[int] = None  # 0 (severe objection) to 100 (clean setup)
    model_used: Optional[str] = None
    latency_ms: float = 0.0
    error: Optional[str] = None


class FinalSynthesisOutput(BaseModel):
    """Structured output for Agent 7: Final Synthesis & Translation."""
    agent_id: str = "final_synthesis"
    agent_name: str = "Final Synthesis Agent"
    action: str = "WAIT"  # BUY, SELL, WAIT, REJECT
    confidence: int = 0  # 0 to 100
    thesis_en: str = ""
    thesis_kh: str = ""
    invalidation_level: Optional[float] = None
    take_profit_target: Optional[float] = None
    policy_verdict: str = "Awaiting institutional confluence"
    model_used: Optional[str] = None
    latency_ms: float = 0.0


class WorkflowTrace(BaseModel):
    """Full observable telemetry trace of the multi-agent deep analysis workflow."""
    request_id: str
    symbol: str
    timestamp_utc: str
    overall_status: str  # COMPLETED, WAIT_STALE_DATA, MARKET_CLOSED, FAILED
    execution_time_ms: float
    freshness_validated: bool
    data_provenance: Dict[str, Any]
    models_used: Dict[str, str]
    step_latencies: Dict[str, float]
    estimated_cost_usd: float
    market_structure: MarketStructureOutput
    multi_timeframe: MultiTimeframeOutput
    macro_news: MacroNewsOutput
    risk_guardian: RiskGuardianOutput
    critic: CriticOutput
    final_synthesis: FinalSynthesisOutput
    orderflow_sentiment: Optional[Dict[str, Any]] = None
    fractal_mtf: Optional[Dict[str, Any]] = None


# =============================================================================
# AGENT 2 — MARKET STRUCTURE AGENT
# =============================================================================

class MarketStructureAgent:
    """Specialist extracting ICT/SMC order flow, liquidity, and market regime."""
    AGENT_ID = "market_structure"

    def analyze(self, symbol: str, df_m15: pd.DataFrame, verified_price: float) -> MarketStructureOutput:
        t0 = time.time()
        if df_m15 is None or df_m15.empty or len(df_m15) < 20:
            return MarketStructureOutput(
                status="FAILED",
                error="Insufficient candles for SMC structure extraction (minimum 20 required).",
                latency_ms=round((time.time() - t0) * 1000, 2)
            )

        try:
            smc = extract_ict_smc_summary(df_m15)
            sweeps = smc.get("liquidity_sweeps", [])
            fvgs = smc.get("unmitigated_fvgs", [])
            obs = smc.get("recent_order_blocks", [])
            bos = smc.get("structure_break")
            choch = smc.get("change_of_character")

            # Determine structural trend
            trend = "RANGING"
            if choch == "BULLISH" or (bos == "BULLISH" and sweeps):
                trend = "BULLISH"
            elif choch == "BEARISH" or (bos == "BEARISH" and sweeps):
                trend = "BEARISH"
            elif bos == "BULLISH":
                trend = "BULLISH"
            elif bos == "BEARISH":
                trend = "BEARISH"

            highs = df_m15["high"].tail(20)
            lows = df_m15["low"].tail(20)
            swing_high = float(highs.max())
            swing_low = float(lows.min())

            evidence = []
            if sweeps:
                sweep_notes = [f"{s.get('type', 'Sweep')} at {s.get('level', 0.0)}" for s in sweeps[:2]]
                evidence.extend(sweep_notes)
            if bos:
                evidence.append(f"Break of Structure (BOS): {bos}")
            if choch:
                evidence.append(f"Change of Character (CHOCH): {choch}")
            if obs:
                evidence.append(f"Active Order Blocks: {len(obs)} detected")

            regime = "TRENDING" if (trend in ("BULLISH", "BEARISH") and len(sweeps) > 0) else "CHOPPY"
            key_levels = {
                "swing_high": swing_high,
                "swing_low": swing_low,
                "midpoint": round((swing_high + swing_low) / 2.0, 3)
            }

            model_used = None
            # Optional: AnyRouter Reasoning Enrichment if configured
            if anyrouter_client.is_configured():
                reasoning_model = anyrouter_client.resolve_model_for_role("reasoning")
                if reasoning_model:
                    try:
                        messages = [
                            {"role": "system", "content": "You are a quantitative market structure analyst specializing in ICT and SMC price action."},
                            {"role": "user", "content": f"Analyze {symbol} price {verified_price}: Trend {trend}, Regime {regime}, BOS {bos}, Sweeps {len(sweeps)}, FVGs {len(fvgs)}. Give 1 concise institutional takeaway."}
                        ]
                        comp = anyrouter_client.generate_chat_completion(messages, model=reasoning_model, max_tokens=100)
                        if comp.get("content"):
                            evidence.append(f"AI SMC Note: {comp['content'].strip()[:140]}")
                            model_used = comp.get("model_used", reasoning_model)
                    except Exception as llm_e:
                        logger.debug(f"AnyRouter reasoning enrichment skipped: {llm_e}")

            latency = round((time.time() - t0) * 1000, 2)
            return MarketStructureOutput(
                status="COMPLETED",
                trend=trend,
                regime=regime,
                swing_high=swing_high,
                swing_low=swing_low,
                order_blocks_count=len(obs),
                fair_value_gaps_count=len(fvgs),
                recent_sweeps=[f"{s.get('type', 'Sweep')}" for s in sweeps[:3]],
                key_levels=key_levels,
                evidence=evidence,
                model_used=model_used,
                latency_ms=latency
            )
        except Exception as e:
            return MarketStructureOutput(
                status="FAILED",
                error=str(e),
                latency_ms=round((time.time() - t0) * 1000, 2)
            )


# =============================================================================
# AGENT 3 — MULTI-TIMEFRAME AGENT
# =============================================================================

class MultiTimeframeAgent:
    """Specialist calculating multi-timeframe confluence across M5, M15, H1, H4."""
    AGENT_ID = "multi_timeframe"

    def analyze(self, symbol: str, multi_tf_data: Dict[str, pd.DataFrame]) -> MultiTimeframeOutput:
        t0 = time.time()
        tf_biases = {}
        rsi_val = None
        atr_val = 0.0
        unavailable = []

        for tf in ["M5", "M15", "H1", "H4"]:
            df = multi_tf_data.get(tf)
            if df is not None and not df.empty and len(df) >= 50:
                ind = compute_technical_indicators(df)
                summary = extract_technical_summary(ind)
                if not summary:
                    unavailable.append(tf)
                    tf_biases[tf] = "UNAVAILABLE"
                    continue
                tf_biases[tf] = summary["trend"]
                if tf == "M15":
                    rsi_val = float(summary["rsi"])
                    atr_val = float(summary["atr"])
            else:
                unavailable.append(tf)
                tf_biases[tf] = "UNAVAILABLE"

        if unavailable or rsi_val is None or atr_val <= 0:
            reason = f"Verified multi-timeframe metrics unavailable: {', '.join(unavailable) or 'M15 RSI/ATR'}"
            return MultiTimeframeOutput(
                status="DATA_UNAVAILABLE",
                m5_bias=tf_biases.get("M5", "UNAVAILABLE"),
                m15_bias=tf_biases.get("M15", "UNAVAILABLE"),
                h1_bias=tf_biases.get("H1", "UNAVAILABLE"),
                h4_bias=tf_biases.get("H4", "UNAVAILABLE"),
                alignment="UNAVAILABLE",
                confluence_score=0,
                dominant_bias="UNAVAILABLE",
                rsi_14=None,
                atr_val=0.0,
                evidence=[reason],
                error=reason,
                latency_ms=round((time.time() - t0) * 1000, 2),
            )

        m5_b = tf_biases.get("M5", "NEUTRAL")
        m15_b = tf_biases.get("M15", "NEUTRAL")
        h1_b = tf_biases.get("H1", "NEUTRAL")
        h4_b = tf_biases.get("H4", "NEUTRAL")

        # Confluence calculation
        bull_votes = sum(1 for b in [m5_b, m15_b, h1_b, h4_b] if "BULLISH" in b)
        bear_votes = sum(1 for b in [m5_b, m15_b, h1_b, h4_b] if "BEARISH" in b)

        confluence_score = 50
        dominant = "NEUTRAL"
        alignment = "MIXED"

        if bull_votes >= 3:
            confluence_score = 85 if bull_votes == 4 else 75
            dominant = "BULLISH"
            alignment = "STRONG ALIGNMENT" if bull_votes == 4 else "MODERATE ALIGNMENT"
        elif bear_votes >= 3:
            confluence_score = 85 if bear_votes == 4 else 75
            dominant = "BEARISH"
            alignment = "STRONG ALIGNMENT" if bear_votes == 4 else "MODERATE ALIGNMENT"
        elif bull_votes == 2 and bear_votes == 0:
            confluence_score = 65
            dominant = "BULLISH"
            alignment = "MODERATE ALIGNMENT"
        elif bear_votes == 2 and bull_votes == 0:
            confluence_score = 65
            dominant = "BEARISH"
            alignment = "MODERATE ALIGNMENT"

        evidence = [
            f"M5: {m5_b}, M15: {m15_b}, H1: {h1_b}, H4: {h4_b}",
            f"RSI(14): {round(rsi_val, 2)}, ATR: {round(atr_val, 4)}"
        ]

        latency = round((time.time() - t0) * 1000, 2)
        return MultiTimeframeOutput(
            status="COMPLETED",
            m5_bias=m5_b,
            m15_bias=m15_b,
            h1_bias=h1_b,
            h4_bias=h4_b,
            alignment=alignment,
            confluence_score=confluence_score,
            dominant_bias=dominant,
            rsi_14=round(rsi_val, 2),
            atr_val=round(atr_val, 4),
            evidence=evidence,
            latency_ms=latency
        )


# =============================================================================
# AGENT 4 — MACRO/NEWS AGENT
# =============================================================================

class MacroNewsAgent:
    """Specialist connecting to real economic calendars and news feeds."""
    AGENT_ID = "macro_news"

    def analyze(self, symbol: str) -> MacroNewsOutput:
        t0 = time.time()
        
        # Check Real-Time Blackout
        blackout_info = economic_calendar_provider.check_news_blackout(symbol)
        is_blackout = blackout_info.get("is_blackout", False)
        blackout_reason = blackout_info.get("event_title") if is_blackout else None
        calendar_available = blackout_info.get("status") != "UNAVAILABLE"

        # Upcoming High-Impact Events & Live News
        events = economic_calendar_provider.get_upcoming_high_impact_events()
        news = economic_calendar_provider.get_live_macro_news()
        dxy_context = economic_calendar_provider.get_usd_strength_context()
        dxy_available = dxy_context.get("status") == "AVAILABLE"
        is_conn = bool(calendar_available or events or news or dxy_available)
        active_sources = []
        if calendar_available or events:
            active_sources.append("FairEconomy")
        if news:
            active_sources.append("RSS News")
        if dxy_available:
            active_sources.append("Yahoo Finance DXY")

        evidence = []
        if is_blackout:
            evidence.append(f"CRITICAL NEWS BLACKOUT: {blackout_reason}")
        elif not calendar_available:
            evidence.append("Economic calendar is unavailable; event risk could not be verified.")
        if events:
            for ev in events[:2]:
                title = ev.get("title") or ev.get("event", "High Impact Event")
                time_until = ev.get("minutes_until", ev.get("time_until_minutes", 0))
                evidence.append(f"Upcoming {title} (in {time_until}m)")
        elif calendar_available:
            evidence.append("No imminent high-impact macro blackouts detected.")

        if news:
            evidence.append(f"Recent Macro Catalyst: {news[0].get('title', '')[:80]}")

        latency = round((time.time() - t0) * 1000, 2)
        return MacroNewsOutput(
            status="COMPLETED" if is_conn else "UNAVAILABLE",
            is_connected=is_conn,
            is_blackout=is_blackout,
            calendar_available=calendar_available,
            dxy_available=dxy_available,
            blackout_reason=blackout_reason,
            news_sentiment="NEUTRAL",
            dxy_bias=dxy_context.get("usd_bias", "UNAVAILABLE"),
            upcoming_events_count=len(events),
            active_sources=active_sources,
            evidence=evidence,
            latency_ms=latency
        )


# =============================================================================
# AGENT 5 — RISK GUARDIAN (100% DETERMINISTIC ARITHMETIC)
# =============================================================================

class RiskGuardian:
    """
    Chief Risk Officer.
    CRITICAL: Never delegates arithmetic, sizing, R:R, or final approval to an LLM.
    Strictly deterministic execution rules:
    - Configured minimum Risk-to-Reward ratio
    - Configured maximum risk as a percentage of equity
    - Sizing: equity * (risk percentage / 100) / stop distance
    - Spread tolerance: spread <= 20% of stop distance
    - Geometric validity: SL below entry for BUY, SL above entry for SELL
    """
    AGENT_ID = "risk_guardian"

    def evaluate_risk(
        self,
        symbol: str,
        direction: str,  # "BUY" or "SELL"
        current_price: float,
        structure_output: MarketStructureOutput,
        mtf_output: MultiTimeframeOutput,
        macro_output: MacroNewsOutput,
        account_equity: float = INITIAL_PAPER_BALANCE,
        spread_points: Optional[float] = None,
        spread_price: Optional[float] = None
    ) -> RiskGuardianOutput:
        t0 = time.time()
        veto_reasons = []

        # 1. Macro Blackout Check
        if not macro_output.calendar_available:
            veto_reasons.append("Economic calendar is unavailable; event risk cannot be verified.")
        elif macro_output.is_blackout:
            veto_reasons.append(f"High-impact news blackout active: {macro_output.blackout_reason}")

        # 2. Derive Stop Loss & Take Profit Levels using deterministic structure & ATR
        try:
            current_price = float(current_price)
        except (TypeError, ValueError):
            current_price = 0.0
        try:
            atr = float(mtf_output.atr_val)
        except (TypeError, ValueError):
            atr = 0.0
        try:
            account_equity = float(account_equity)
        except (TypeError, ValueError):
            account_equity = 0.0
        if not math.isfinite(current_price) or current_price <= 0:
            veto_reasons.append("Verified market price is unavailable or invalid.")
        if not math.isfinite(account_equity) or account_equity <= 0:
            veto_reasons.append("Account equity is unavailable or invalid; sizing cannot be verified.")
        if not math.isfinite(atr) or atr <= 0:
            veto_reasons.append("Measured ATR is unavailable; stop distance cannot be verified.")
            atr = 0.0
        cfg = get_symbol_config(symbol)
        min_sl_dist = atr * 1.2
        try:
            swing_high = float(structure_output.swing_high or 0.0)
            swing_low = float(structure_output.swing_low or 0.0)
        except (TypeError, ValueError):
            swing_high = swing_low = 0.0
        if not math.isfinite(swing_high):
            swing_high = 0.0
        if not math.isfinite(swing_low):
            swing_low = 0.0

        if direction == "BUY":
            # SL placed below recent swing low or ATR buffer
            sl_candidate = swing_low - (atr * 0.2) if swing_low > 0 else (current_price - min_sl_dist)
            # Ensure minimum SL distance
            if (current_price - sl_candidate) < min_sl_dist:
                sl_candidate = current_price - min_sl_dist
            stop_loss = round(sl_candidate, 3)
            risk_dist = current_price - stop_loss

            # Structural TP target is the overhead swing high liquidity pool if present
            if swing_high > current_price:
                take_profit = round(swing_high, 3)
            else:
                take_profit = round(current_price + (risk_dist * MIN_RISK_REWARD_RATIO), 3)

            rr_ratio = round((take_profit - current_price) / max(0.0001, risk_dist), 2)

            if stop_loss >= current_price:
                veto_reasons.append(f"Invalid geometry: BUY Stop Loss ({stop_loss}) >= Current Price ({current_price})")

        elif direction == "SELL":
            # SL placed above recent swing high or ATR buffer
            sl_candidate = swing_high + (atr * 0.2) if swing_high > 0 else (current_price + min_sl_dist)
            if (sl_candidate - current_price) < min_sl_dist:
                sl_candidate = current_price + min_sl_dist
            stop_loss = round(sl_candidate, 3)
            risk_dist = stop_loss - current_price

            # Structural TP target is the underneath swing low liquidity pool if present
            if swing_low > 0 and swing_low < current_price:
                take_profit = round(swing_low, 3)
            else:
                take_profit = round(current_price - (risk_dist * MIN_RISK_REWARD_RATIO), 3)

            rr_ratio = round((current_price - take_profit) / max(0.0001, risk_dist), 2)

            if stop_loss <= current_price:
                veto_reasons.append(f"Invalid geometry: SELL Stop Loss ({stop_loss}) <= Current Price ({current_price})")
        else:
            # Neutral / Flat
            stop_loss = current_price
            take_profit = current_price
            rr_ratio = 0.0
            risk_dist = 0.0
            veto_reasons.append("Direction is neutral or undefined.")

        # 3. Minimum R:R Gating (configured floor)
        if direction in ("BUY", "SELL") and rr_ratio < MIN_RISK_REWARD_RATIO:
            veto_reasons.append(f"Calculated R:R {rr_ratio}:1 fails institutional minimum {MIN_RISK_REWARD_RATIO}:1.")

        # 4. Spread Tolerance Check. Points are for display; compare the raw
        # bid/ask difference in quote-price units with the stop distance.
        try:
            spread_price = float(spread_price)
        except (TypeError, ValueError):
            spread_price = 0.0
        if not math.isfinite(spread_price) or spread_price <= 0:
            veto_reasons.append("Verified bid/ask spread is unavailable; execution cost cannot be checked.")
        elif risk_dist > 0 and (spread_price / risk_dist) > 0.20:
            veto_reasons.append(f"Spread cost ({spread_price}) exceeds 20% of stop distance ({round(risk_dist, 3)}).")
        try:
            spread_points = float(spread_points) if spread_points is not None else None
        except (TypeError, ValueError):
            spread_points = None
        if spread_points is not None and (not math.isfinite(spread_points) or spread_points <= 0):
            spread_points = None

        # 5. Position Sizing (configured maximum risk)
        risk_amount_usd = round(account_equity * (RISK_PER_TRADE_PERCENT / 100.0), 2)
        lot_size = 0.01
        if risk_dist > 0:
            contract_size = float(cfg.get("lot_size", 100 if "XAU" in symbol else 100000))
            if not math.isfinite(contract_size) or contract_size <= 0:
                veto_reasons.append("Instrument contract size is unavailable; position sizing cannot be verified.")
                contract_size = 1.0
            # standard lot sizing formula
            calculated_lots = risk_amount_usd / (risk_dist * contract_size)
            if calculated_lots < 0.01:
                veto_reasons.append("Minimum supported position size would exceed the configured risk limit.")
            else:
                lot_size = min(5.0, math.floor(calculated_lots * 100) / 100.0)

        approved = len(veto_reasons) == 0 and direction in ("BUY", "SELL")

        latency = round((time.time() - t0) * 1000, 2)
        return RiskGuardianOutput(
            status="COMPLETED",
            approved=approved,
            veto_reasons=veto_reasons,
            entry_price=round(current_price, 3),
            stop_loss=round(stop_loss, 3),
            take_profit=round(take_profit, 3),
            risk_reward_ratio=rr_ratio,
            min_required_rr=MIN_RISK_REWARD_RATIO,
            max_risk_percent=RISK_PER_TRADE_PERCENT,
            account_equity=account_equity,
            risk_amount_usd=risk_amount_usd,
            recommended_lot_size=lot_size,
            spread_points=spread_points,
            spread_price=spread_price if math.isfinite(spread_price) and spread_price > 0 else None,
            latency_ms=latency
        )


# =============================================================================
# AGENT 6 — INDEPENDENT CRITIC (DEVIL'S ADVOCATE)
# =============================================================================

class IndependentCritic:
    """Specialist assigned to challenge the thesis, find objections, and uncover contrarian traps."""
    AGENT_ID = "independent_critic"

    def evaluate(
        self,
        symbol: str,
        proposed_action: str,
        current_price: float,
        structure: MarketStructureOutput,
        mtf: MultiTimeframeOutput,
        risk: RiskGuardianOutput
    ) -> CriticOutput:
        t0 = time.time()
        objections = []
        opposing_evidence = []
        invalidation_triggers = []
        counter_risk = "LOW"
        trapped_risk = "LOW"
        critic_score = 85
        model_used = None

        if proposed_action == "BUY":
            # Check RSI overbought trap
            rsi = mtf.rsi_14
            atr = mtf.atr_val or 0.0
            if rsi is not None and rsi > 70.0:
                objections.append(f"M15 RSI is overbought ({mtf.rsi_14}); risk of immediate pullback into FVG.")
                counter_risk = "MEDIUM"
                critic_score -= 20
            # Check proximity to swing high resistance
            if structure.swing_high is not None and structure.swing_high > 0 and (structure.swing_high - current_price) < (atr * 0.5):
                objections.append(f"Buying directly into major swing high resistance ({structure.swing_high}).")
                trapped_risk = "HIGH"
                critic_score -= 25
            opposing_evidence.append("Retail buyers frequently trapped at range extremes before liquidity sweeps.")
            invalidation_triggers.append(f"Hourly candle close below {risk.stop_loss} instantly voids setup.")

        elif proposed_action == "SELL":
            # Check RSI oversold trap
            rsi = mtf.rsi_14
            atr = mtf.atr_val or 0.0
            if rsi is not None and rsi < 30.0:
                objections.append(f"M15 RSI is oversold ({mtf.rsi_14}); vulnerable to aggressive short-covering squeeze.")
                counter_risk = "MEDIUM"
                critic_score -= 20
            # Check proximity to swing low support
            if structure.swing_low is not None and structure.swing_low > 0 and (current_price - structure.swing_low) < (atr * 0.5):
                objections.append(f"Selling directly into major swing low liquidity pool ({structure.swing_low}).")
                trapped_risk = "HIGH"
                critic_score -= 25
            opposing_evidence.append("Institutional smart money often engineer fake breakdowns at major support.")
            invalidation_triggers.append(f"Hourly candle close above {risk.stop_loss} instantly voids setup.")

        # AnyRouter Critic Prompt if configured
        if anyrouter_client.is_configured() and proposed_action in ("BUY", "SELL"):
            critic_model = anyrouter_client.resolve_model_for_role("critic")
            if critic_model:
                try:
                    messages = [
                        {"role": "system", "content": "You are a ruthless risk critic & institutional devil's advocate. Your job is to challenge the trade thesis and find vulnerabilities."},
                        {"role": "user", "content": f"Symbol: {symbol}, Proposed Trade: {proposed_action} at {current_price}. SL: {risk.stop_loss}, TP: {risk.take_profit}. RSI: {mtf.rsi_14}, HTF: {mtf.h4_bias}. State 1 major pitfall or trap."}
                    ]
                    comp = anyrouter_client.generate_chat_completion(messages, model=critic_model, max_tokens=120)
                    if comp.get("content"):
                        objections.append(f"LLM Critic Note: {comp['content'].strip()[:140]}")
                        model_used = comp.get("model_used", critic_model)
                except Exception as ex:
                    logger.debug(f"Critic LLM evaluation bypassed: {ex}")

        # Critic approves if objections are not fatal (score >= 50)
        approved = critic_score >= 50
        latency = round((time.time() - t0) * 1000, 2)
        return CriticOutput(
            status="COMPLETED",
            approved=approved,
            counter_trend_risk=counter_risk,
            trapped_traders_risk=trapped_risk,
            objections=objections,
            opposing_evidence=opposing_evidence,
            invalidation_triggers=invalidation_triggers,
            critic_score=max(0, critic_score),
            model_used=model_used,
            latency_ms=latency
        )


# =============================================================================
# AGENT 7 — FINAL SYNTHESIS AGENT (BILINGUAL)
# =============================================================================

class FinalSynthesisAgent:
    """Specialist generating final synthesis thesis in English and natural Khmer."""
    AGENT_ID = "final_synthesis"

    def synthesize(
        self,
        symbol: str,
        current_price: float,
        structure: MarketStructureOutput,
        mtf: MultiTimeframeOutput,
        macro: MacroNewsOutput,
        risk: RiskGuardianOutput,
        critic: CriticOutput
    ) -> FinalSynthesisOutput:
        t0 = time.time()

        # Decision Policy Enforcement
        action = "WAIT"
        confidence = 0
        policy_verdict = "Awaiting institutional confluence"

        # Check preconditions for BUY
        if (
            structure.trend == "BULLISH"
            and mtf.dominant_bias == "BULLISH"
            and risk.approved
            and critic.approved
            and not macro.is_blackout
        ):
            action = "BUY"
            confidence = int(min(92, (mtf.confluence_score * 0.5) + (critic.critic_score * 0.5)))
            policy_verdict = "Full multi-timeframe & structural confluence verified. Risk parameters approved."

        # Check preconditions for SELL
        elif (
            structure.trend == "BEARISH"
            and mtf.dominant_bias == "BEARISH"
            and risk.approved
            and critic.approved
            and not macro.is_blackout
        ):
            action = "SELL"
            confidence = int(min(92, (mtf.confluence_score * 0.5) + (critic.critic_score * 0.5)))
            policy_verdict = "Full bearish institutional alignment verified. Risk parameters approved."

        elif macro.is_blackout or not risk.approved:
            action = "REJECT"
            confidence = 0
            policy_verdict = f"Risk Guardian veto triggered: {'; '.join(risk.veto_reasons)}"

        else:
            action = "WAIT"
            confidence = 0
            policy_verdict = "Market lacks full structural alignment or liquidity sweep confirmation."

        # English Thesis
        geometry_entry = risk.entry_price if risk.entry_price is not None else "N/A"
        geometry_sl = risk.stop_loss if risk.stop_loss is not None else "N/A"
        geometry_tp = risk.take_profit if risk.take_profit is not None else "N/A"
        geometry_rr = risk.risk_reward_ratio if risk.risk_reward_ratio is not None else "N/A"
        mtf_score = mtf.confluence_score if mtf.confluence_score is not None else "N/A"
        critic_score = critic.critic_score if critic.critic_score is not None else "N/A"
        thesis_en = (
            f"ZYROX AI Institutional Verdict for {symbol} at {current_price}: Action is {action} (Confidence: {confidence}%).\n"
            f"Market Structure: {structure.trend} ({structure.regime}). Multi-timeframe confluence: {mtf.alignment} (Score: {mtf_score}/100).\n"
            f"Execution Geometry: Entry {geometry_entry}, SL {geometry_sl}, TP {geometry_tp} (R:R {geometry_rr}:1, Configured risk limit: {risk.max_risk_percent}%).\n"
            f"Critic Assessment: Score {critic_score}/100 with {len(critic.objections)} recorded reservations."
        )

        # Natural Khmer Institutional Thesis
        thesis_kh = (
            f"របាយការណ៍វិភាគ ZYROX AI សម្រាប់ {symbol} ក្នុងតម្លៃ {current_price}៖ ការសម្រេចចិត្តគឺ {action} (កម្រិតទំនុកចិត្ត៖ {confidence}%)\n"
            f"រចនាសម្ព័ន្ធទីផ្សារ៖ {structure.trend} ({structure.regime})។ ការស្របគ្នានៃ Timeframe៖ {mtf.alignment} (ពិន្ទុ {mtf_score}/100)។\n"
            f"កម្រិតជួញដូរ៖ ចំណុចចូល {geometry_entry}, Stop Loss {geometry_sl}, Take Profit {geometry_tp} (R:R {geometry_rr}:1, កម្រិតហានិភ័យកំណត់ {risk.max_risk_percent}%)។\n"
            f"ការវាយតម្លៃរបស់ Critic៖ ពិន្ទុ {critic_score}/100 ជាមួយនឹងការកត់សម្គាល់ {len(critic.objections)} ចំណុច។"
        )

        latency = round((time.time() - t0) * 1000, 2)
        return FinalSynthesisOutput(
            action=action,
            confidence=confidence,
            thesis_en=thesis_en,
            thesis_kh=thesis_kh,
            invalidation_level=risk.stop_loss if action in ("BUY", "SELL") else None,
            take_profit_target=risk.take_profit if action in ("BUY", "SELL") else None,
            policy_verdict=policy_verdict,
            latency_ms=latency
        )


# =============================================================================
# AGENT 1 — ORCHESTRATOR & DEEP ANALYSIS WORKFLOW COORDINATOR
# =============================================================================

class Orchestrator:
    """
    Central Controller for the 7-Agent Institutional Deep Analysis Workflow.
    Enforces Step G rules:
    - Pre-flight market data validation before LLM invocation (stale data -> fast WAIT).
    - Concurrent specialist tasks.
    - Schema validation.
    - Deterministic risk checks.
    - Independent critic evaluation.
    - Request ID, latency tracking, budget tracking, and full trace exposure.
    """

    def __init__(self):
        self.market_structure_agent = MarketStructureAgent()
        self.multi_timeframe_agent = MultiTimeframeAgent()
        self.macro_news_agent = MacroNewsAgent()
        self.risk_guardian = RiskGuardian()
        self.critic_agent = IndependentCritic()
        self.synthesis_agent = FinalSynthesisAgent()
        from taikry.agents.orderflow_sentiment_analyst import orderflow_sentiment_agent
        from taikry.agents.fractal_mtf_analyst import fractal_mtf_agent
        self.orderflow_agent = orderflow_sentiment_agent
        self.fractal_mtf_agent = fractal_mtf_agent

    def run_deep_analysis(
        self,
        symbol: str = "XAUUSD",
        account_equity: float = INITIAL_PAPER_BALANCE,
        force_fresh: bool = False
    ) -> WorkflowTrace:
        t_start = time.time()
        request_id = str(uuid.uuid4())
        now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        step_latencies: Dict[str, float] = {}
        models_used: Dict[str, str] = {}

        # ---------------------------------------------------------------------
        # STEP 1: PRE-FLIGHT MARKET DATA VALIDATION (Enforces Zero-Cost on Stale Feed)
        # ---------------------------------------------------------------------
        t_data_0 = time.time()
        verified_price, provider_name, price_timestamp = market_data_engine.get_verified_price(symbol)
        timeframes = ["M5", "M15", "H1", "H4"]
        multi_tf_data = market_data_engine.get_multi_timeframe_candles(symbol, timeframes)
        step_latencies["market_data_fetch"] = round((time.time() - t_data_0) * 1000, 2)

        data_provenance = {
            "symbol": symbol,
            "verified_price": verified_price,
            "provider": provider_name,
            "price_timestamp": price_timestamp.isoformat() if isinstance(price_timestamp, datetime.datetime) else str(price_timestamp)
        }

        # Check market open
        market_open, open_msg = is_market_open(symbol)
        freshness = check_data_freshness(symbol, price_timestamp)

        # Do not run actionable analysis against closed, stale, synthetic, or missing feeds.
        invalid_source = any(marker in str(provider_name).upper() for marker in ("SYNTHETIC", "DEMO", "UNAVAILABLE"))
        if (
            not market_open
            or not freshness.get("fresh", False)
            or verified_price <= 0
            or invalid_source
        ):
            if not market_open:
                preflight_reason = f"Market is closed ({open_msg})."
                preflight_status = "WAIT_MARKET_CLOSED"
            elif verified_price <= 0 or invalid_source:
                preflight_reason = "A verified live market price is unavailable."
                preflight_status = "WAIT_DATA_UNAVAILABLE"
            else:
                preflight_reason = f"Market data is stale ({freshness.get('age_minutes', 'unknown')} minutes old)."
                preflight_status = "WAIT_STALE_DATA"
            # Fast WAIT return to save tokens and avoid false analysis on stale data
            total_duration = round((time.time() - t_start) * 1000, 2)
            stale_structure = MarketStructureOutput(status="SKIPPED", error=preflight_reason)
            stale_mtf = MultiTimeframeOutput(status="SKIPPED", error=preflight_reason)
            stale_macro = MacroNewsOutput(status="SKIPPED", error=preflight_reason)
            stale_risk = RiskGuardianOutput(
                status="SKIPPED",
                approved=False,
                veto_reasons=[preflight_reason],
                entry_price=verified_price
            )
            stale_critic = CriticOutput(status="SKIPPED", approved=False, objections=[preflight_reason])
            stale_synthesis = FinalSynthesisOutput(
                action="WAIT",
                confidence=0,
                policy_verdict=f"{preflight_reason} Inference halted.",
                thesis_en=f"Analysis halted for {symbol}. {preflight_reason}",
                thesis_kh=f"ការវិភាគសម្រាប់ {symbol} ត្រូវបានផ្អាក។ {preflight_reason}"
            )

            return WorkflowTrace(
                request_id=request_id,
                symbol=symbol,
                timestamp_utc=now_utc,
                overall_status=preflight_status,
                execution_time_ms=total_duration,
                freshness_validated=False,
                data_provenance=data_provenance,
                models_used={},
                step_latencies=step_latencies,
                estimated_cost_usd=round(budget_manager.estimated_total_spend_usd, 4),
                market_structure=stale_structure,
                multi_timeframe=stale_mtf,
                macro_news=stale_macro,
                risk_guardian=stale_risk,
                critic=stale_critic,
                final_synthesis=stale_synthesis
            )

        df_m15 = multi_tf_data.get("M15") if multi_tf_data.get("M15") is not None else multi_tf_data.get("M5")

        # ---------------------------------------------------------------------
        # STEP 2: CONCURRENT SPECIALIST AGENTS DISPATCH (5 Agents Parallel)
        # ---------------------------------------------------------------------
        t_specialists_0 = time.time()
        structure_out: Optional[MarketStructureOutput] = None
        mtf_out: Optional[MultiTimeframeOutput] = None
        macro_out: Optional[MacroNewsOutput] = None
        orderflow_out = None
        fractal_out = None

        with ThreadPoolExecutor(max_workers=5) as executor:
            fut_struct = executor.submit(self.market_structure_agent.analyze, symbol, df_m15, verified_price)
            fut_mtf = executor.submit(self.multi_timeframe_agent.analyze, symbol, multi_tf_data)
            fut_macro = executor.submit(self.macro_news_agent.analyze, symbol)
            fut_orderflow = executor.submit(self.orderflow_agent.analyze, symbol, df_m15, verified_price)
            fut_fractal = executor.submit(self.fractal_mtf_agent.analyze, symbol, multi_tf_data)

            structure_out = fut_struct.result()
            mtf_out = fut_mtf.result()
            macro_out = fut_macro.result()
            orderflow_out = fut_orderflow.result()
            fractal_out = fut_fractal.result()

        step_latencies["specialists_concurrent"] = round((time.time() - t_specialists_0) * 1000, 2)

        if structure_out.model_used:
            models_used["market_structure"] = structure_out.model_used

        # ---------------------------------------------------------------------
        # STEP 3: PROPOSED DIRECTION & DETERMINISTIC RISK GUARDIAN
        # ---------------------------------------------------------------------
        t_risk_0 = time.time()
        proposed_direction = "WAIT"
        if structure_out.trend == "BULLISH" and mtf_out.dominant_bias == "BULLISH":
            proposed_direction = "BUY"
        elif structure_out.trend == "BEARISH" and mtf_out.dominant_bias == "BEARISH":
            proposed_direction = "SELL"

        _, _, spread_fresh, spread_tick = mt5_receiver.get_latest_price(symbol)
        spread_points = None
        spread_price = None
        if spread_fresh:
            try:
                bid = float(spread_tick.get("bid"))
                ask = float(spread_tick.get("ask"))
                spread_points = float(spread_tick.get("spread"))
                if math.isfinite(bid) and math.isfinite(ask) and ask > bid and math.isfinite(spread_points) and spread_points > 0:
                    spread_price = ask - bid
                else:
                    spread_points = None
            except (TypeError, ValueError):
                spread_points = None
                spread_price = None

        risk_out = self.risk_guardian.evaluate_risk(
            symbol=symbol,
            direction=proposed_direction,
            current_price=verified_price,
            structure_output=structure_out,
            mtf_output=mtf_out,
            macro_output=macro_out,
            account_equity=account_equity,
            spread_points=spread_points,
            spread_price=spread_price
        )
        step_latencies["risk_guardian_deterministic"] = round((time.time() - t_risk_0) * 1000, 2)

        # ---------------------------------------------------------------------
        # STEP 4: INDEPENDENT CRITIC (DEVIL'S ADVOCATE)
        # ---------------------------------------------------------------------
        t_critic_0 = time.time()
        critic_out = self.critic_agent.evaluate(
            symbol=symbol,
            proposed_action=proposed_direction,
            current_price=verified_price,
            structure=structure_out,
            mtf=mtf_out,
            risk=risk_out
        )
        step_latencies["independent_critic"] = round((time.time() - t_critic_0) * 1000, 2)
        if critic_out.model_used:
            models_used["critic"] = critic_out.model_used

        # ---------------------------------------------------------------------
        # STEP 5: FINAL SYNTHESIS & BILINGUAL PRODUCTION
        # ---------------------------------------------------------------------
        t_synth_0 = time.time()
        final_synth = self.synthesis_agent.synthesize(
            symbol=symbol,
            current_price=verified_price,
            structure=structure_out,
            mtf=mtf_out,
            macro=macro_out,
            risk=risk_out,
            critic=critic_out
        )
        step_latencies["final_synthesis"] = round((time.time() - t_synth_0) * 1000, 2)

        total_exec_time = round((time.time() - t_start) * 1000, 2)

        return WorkflowTrace(
            request_id=request_id,
            symbol=symbol,
            timestamp_utc=now_utc,
            overall_status="COMPLETED",
            execution_time_ms=total_exec_time,
            freshness_validated=True,
            data_provenance=data_provenance,
            models_used=models_used,
            step_latencies=step_latencies,
            estimated_cost_usd=round(budget_manager.estimated_total_spend_usd, 4),
            market_structure=structure_out,
            multi_timeframe=mtf_out,
            macro_news=macro_out,
            risk_guardian=risk_out,
            critic=critic_out,
            final_synthesis=final_synth,
            orderflow_sentiment=orderflow_out.model_dump() if hasattr(orderflow_out, "model_dump") else orderflow_out,
            fractal_mtf=fractal_out.model_dump() if hasattr(fractal_out, "model_dump") else fractal_out
        )


# Global Singleton Instance
multi_agent_orchestrator = Orchestrator()
