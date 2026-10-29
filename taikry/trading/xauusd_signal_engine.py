"""
TAIKRY SIGNAL AI — XAUUSD-ONLY TELEGRAM SIGNAL ENGINE
=====================================================
Specialized institutional signal engine focusing exclusively on XAUUSD (Gold vs USD).
Features:
1. Strict XAUUSD-only policy (disallows all other crypto, forex, commodities).
2. Dynamic discovery and execution of ALL eligible registered AI agents.
3. Multi-agent consensus synthesis with transparent scoring (80% - 95% gate).
4. Atomic persistent daily quota (2-4 target, hard cap of 4 signals per Cambodia calendar day).
5. Comprehensive risk validation (SL/TP ordering, positive distance, >= 1:2.0 R:R).
6. Idempotent persistent signal generation and state machine transitions.
"""

import time
import uuid
import hashlib
import datetime
import zoneinfo
import logging
import math
from typing import Dict, Any, List, Optional, Tuple
import threading
from taikry.config import (
    DEFAULT_STRATEGY_VERSION, COMMISSION_PER_LOT, MIN_RISK_REWARD_RATIO
)
from taikry.database.session import SessionLocal
from taikry.database.models import XAUUSDTelegramSignalModel, AgentLearningModel
from taikry.data.providers import market_data_engine
from taikry.data.validator import validate_dataframe, is_market_open, check_data_freshness
from taikry.data.mt5_receiver import mt5_receiver
from taikry.agents.registry import agent_registry

logger = logging.getLogger("taikry.trading.xauusd_signal_engine")

# Canonical Symbol and supported provider aliases
ALLOWED_CANONICAL_SYMBOL = "XAUUSD"
XAUUSD_ALIASES = {
    "XAUUSD", "GOLD", "XAU/USD", "XAU_USD", "OANDA:XAUUSD", "FX:XAUUSD", "FOREXCOM:XAUUSD"
}

# Timezone for daily quota and reporting
CAMBODIA_TZ = zoneinfo.ZoneInfo("Asia/Phnom_Penh")

# Default Operational Parameters
DEFAULT_DAILY_LIMIT = 4
DEFAULT_MIN_RR = MIN_RISK_REWARD_RATIO
DEFAULT_MIN_SCORE = 80
DEFAULT_MAX_SCORE = 95
DEFAULT_MAX_ENTRY_DEVIATION_POINTS = 3.5  # Max allowable price drift from entry
DEFAULT_SIGNAL_EXPIRY_HOURS = 6


def normalize_xauusd_symbol(raw_symbol: str) -> Optional[str]:
    """
    Validates and normalizes the symbol strictly to XAUUSD.
    Returns 'XAUUSD' if valid alias, otherwise None.
    """
    if not raw_symbol or not isinstance(raw_symbol, str):
        return None
    cleaned = raw_symbol.strip().upper().replace(" ", "")
    if cleaned in XAUUSD_ALIASES:
        return ALLOWED_CANONICAL_SYMBOL
    return None


def get_cambodia_date_str(utc_dt: Optional[datetime.datetime] = None) -> str:
    """Returns local Cambodia calendar date string 'YYYY-MM-DD'."""
    dt = utc_dt or datetime.datetime.now(datetime.timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    cambodia_dt = dt.astimezone(CAMBODIA_TZ)
    return cambodia_dt.strftime("%Y-%m-%d")


def _make_json_safe(obj: Any) -> Any:
    """Recursively serializes timestamps, numpy objects, and datetimes to JSON-safe primitives."""
    if isinstance(obj, dict):
        return {str(k): _make_json_safe(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple, set)):
        return [_make_json_safe(x) for x in obj]
    elif hasattr(obj, "isoformat"):
        return obj.isoformat()
    elif hasattr(obj, "item"):
        return obj.item()
    return obj


class XAUUSDSignalEngine:
    """
    Master XAUUSD-Only Signal & Consensus Engine.
    Coordinates all registered agents, enforces daily quota, and validates trade parameters.
    """

    def __init__(self):
        self.daily_limit = DEFAULT_DAILY_LIMIT
        self.min_rr = DEFAULT_MIN_RR
        self.min_score = DEFAULT_MIN_SCORE
        self.max_score = DEFAULT_MAX_SCORE
        self.max_entry_dev = DEFAULT_MAX_ENTRY_DEVIATION_POINTS
        self.expiry_hours = DEFAULT_SIGNAL_EXPIRY_HOURS
        self.min_agent_coverage_ratio = 0.60  # At least 60% of eligible agents must participate
        self._generation_lock = threading.Lock()

    # -------------------------------------------------------------------------
    # 1. ATOMIC DAILY QUOTA & DEDUPLICATION CHECKS
    # -------------------------------------------------------------------------

    def get_daily_quota_status(self, target_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Counts sent and pending delivery reservations for the Cambodia calendar day.
        """
        date_str = target_date or get_cambodia_date_str()
        db = SessionLocal()
        try:
            # Count actual deliveries separately from reservations to avoid
            # oversubscribing the daily limit while Telegram sends are pending.
            sent_count = db.query(XAUUSDTelegramSignalModel).filter(
                XAUUSDTelegramSignalModel.cambodia_date == date_str,
                XAUUSDTelegramSignalModel.telegram_delivery_status == "SENT"
            ).count()
            used_count = db.query(XAUUSDTelegramSignalModel).filter(
                XAUUSDTelegramSignalModel.cambodia_date == date_str,
                XAUUSDTelegramSignalModel.telegram_delivery_status.in_(["PENDING", "SENDING", "SENT", "DELIVERY_UNKNOWN"])
            ).count()

            remaining = max(0, self.daily_limit - used_count)
            is_limit_reached = used_count >= self.daily_limit

            target_status = "0/4 — Awaiting High Quality Setups"
            if used_count == 1:
                target_status = "1/4 — Signal Reserved or Sent"
            elif used_count in [2, 3]:
                target_status = f"{used_count}/4 — Reserved or Sent"
            elif used_count >= 4:
                target_status = "4/4 — Daily Hard Cap Reached (Protected)"

            return {
                "cambodia_date": date_str,
                "signals_sent_today": sent_count,
                "signals_reserved_or_sent_today": used_count,
                "daily_hard_limit": self.daily_limit,
                "remaining_quota": remaining,
                "is_limit_reached": is_limit_reached,
                "target_status": target_status
            }
        finally:
            db.close()

    def check_duplicate_signal(self, direction: str, entry_price: float, stop_loss: float) -> Tuple[bool, Optional[str]]:
        """
        Checks persistent database for recent identical or active conflicting signals.
        Prevents resending an existing setup.
        """
        db = SessionLocal()
        try:
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            recent_window = now_utc - datetime.timedelta(hours=4)

            # Check for active or recently sent signals in same direction with similar entry (+/- 1.5 pts)
            existing = db.query(XAUUSDTelegramSignalModel).filter(
                XAUUSDTelegramSignalModel.canonical_symbol == ALLOWED_CANONICAL_SYMBOL,
                XAUUSDTelegramSignalModel.direction == direction,
                XAUUSDTelegramSignalModel.telegram_delivery_status.in_(["PENDING", "SENDING", "SENT", "DELIVERY_UNKNOWN"]),
                XAUUSDTelegramSignalModel.signal_status.in_(["SENT", "OPEN", "VALIDATED", "WAITING_CONFIRMATION"]),
                XAUUSDTelegramSignalModel.created_at >= recent_window
            ).all()

            for sig in existing:
                if abs(sig.entry_price - entry_price) <= 2.0 and abs(sig.stop_loss - stop_loss) <= 2.5:
                    return True, f"Duplicate setup: Matching active {direction} signal already sent ({sig.signal_id})"

            return False, None
        finally:
            db.close()

    # -------------------------------------------------------------------------
    # 2. DYNAMIC DISCOVERY & EXECUTION OF ALL ELIGIBLE REGISTERED AGENTS
    # -------------------------------------------------------------------------

    def discover_eligible_agents(self) -> List[Any]:
        """
        Discovers all registered agents applicable to XAUUSD dynamically from AgentRegistry.
        Never hardcodes agent names or fixed counts.
        """
        eligible_adapters = []
        for adapter in agent_registry._agents.values():
            meta = adapter.metadata
            # Agent must be enabled and healthy
            if not meta.enabled or meta.health_status == "DISABLED":
                continue

            # Must support XAUUSD or ALL instruments
            instruments = [i.upper() for i in meta.supported_instruments]
            if "XAUUSD" in instruments or "ALL" in instruments or "FOREX" in instruments:
                eligible_adapters.append(adapter)

        return eligible_adapters

    def execute_all_agents(
        self,
        symbol: str,
        multi_tf_data: Dict[str, Any],
        verified_price: float
    ) -> Dict[str, Any]:
        """
        Runs every eligible agent on the exact same market snapshot,
        records latency, models, evidence, and errors.
        """
        eligible = self.discover_eligible_agents()
        results: Dict[str, Any] = {}

        for adapter in eligible:
            meta = adapter.metadata
            agent_id = meta.agent_id
            start_t = time.perf_counter()

            try:
                # Tailor arguments based on agent specialization
                if agent_id == "technical_analyst":
                    out = adapter.execute(symbol, multi_tf_data)
                elif agent_id == "ict_smc_analyst":
                    out = adapter.execute(symbol, multi_tf_data)
                elif agent_id == "macro_analyst":
                    out = adapter.execute(symbol)
                elif agent_id == "risk_validator":
                    # Evaluated subsequently during consensus synthesis
                    continue
                elif agent_id in ["consensus_engine", "debate_engine"]:
                    # Coordination engines, not raw signal contributors
                    continue
                else:
                    # Generic invocation for dynamically added plugin agents
                    out = adapter.execute(symbol=symbol, multi_tf_data=multi_tf_data, verified_price=verified_price)

                latency_ms = (time.perf_counter() - start_t) * 1000.0
                results[agent_id] = {
                    "agent_id": agent_id,
                    "name": meta.name,
                    "specialization": meta.specialization,
                    "model_provider": meta.model_provider,
                    "model_identifier": meta.model_identifier,
                    "bias": out.get("bias", "NEUTRAL").upper(),
                    "confidence": out.get("confidence", 50),
                    "setup_eligible": out.get("setup_eligible", False),
                    "evidence": out.get("evidence", []),
                    "key_levels": out.get("key_price_levels") or out.get("key_price_zones") or {},
                    "key_price_levels": out.get("key_price_levels") or {},
                    "key_price_zones": out.get("key_price_zones") or {},
                    "rationale": out.get("rationale", ""),
                    "status": "SUCCESS",
                    "latency_ms": round(latency_ms, 1),
                    "error": None
                }
            except Exception as e:
                latency_ms = (time.perf_counter() - start_t) * 1000.0
                logger.warning(f"Error executing agent {agent_id}: {e}")
                results[agent_id] = {
                    "agent_id": agent_id,
                    "name": meta.name,
                    "specialization": meta.specialization,
                    "model_provider": meta.model_provider,
                    "model_identifier": meta.model_identifier,
                    "bias": "NEUTRAL",
                    "confidence": 0,
                    "setup_eligible": False,
                    "evidence": [f"Execution error: {str(e)}"],
                    "key_levels": {},
                    "rationale": "Execution failed, treated as neutral.",
                    "status": "ERROR",
                    "latency_ms": round(latency_ms, 1),
                    "error": str(e)
                }

        return results

    # -------------------------------------------------------------------------
    # 3. CONSENSUS SYNTHESIS & SCORING
    # -------------------------------------------------------------------------

    def synthesize_consensus(
        self,
        symbol: str,
        verified_price: float,
        agent_outputs: Dict[str, Any],
        multi_tf_data: Dict[str, Any],
        price_timestamp: Optional[datetime.datetime] = None,
        spread_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Synthesizes individual agent outputs into an institutional consensus decision.
        Returns: {decision: BUY|SELL|WAIT|NO TRADE, score, entry, sl, tp1, tp2, tp3, ...}
        """
        # 1. Coverage Check
        total_eligible = len(agent_outputs)
        if total_eligible == 0:
            return {
                "decision": "NO TRADE",
                "score": 0,
                "rejection_reason": "No eligible agents available for XAUUSD analysis."
            }

        successful_agents = []
        for agent_id, output in agent_outputs.items():
            if not isinstance(output, dict) or output.get("status") != "SUCCESS":
                continue
            try:
                confidence = float(output.get("confidence"))
            except (TypeError, ValueError):
                continue
            if not math.isfinite(confidence) or not 0 <= confidence <= 100 or not isinstance(output.get("bias"), str):
                continue
            successful_agents.append((agent_id, output))
        coverage = len(successful_agents) / float(total_eligible)
        if coverage < self.min_agent_coverage_ratio:
            return {
                "decision": "NO TRADE",
                "score": 0,
                "rejection_reason": f"Insufficient agent coverage ({len(successful_agents)}/{total_eligible} = {coverage:.0%}, required >= {self.min_agent_coverage_ratio:.0%})"
            }

        # 2. Count Directional Bias
        buy_weight = 0.0
        sell_weight = 0.0
        neutral_weight = 0.0
        total_participant_weight = 0.0
        all_evidence: List[str] = []

        # Load dynamic agent weights from learning model if available
        agent_weights = self._load_agent_weights()

        for a_id, out in successful_agents:
            try:
                w = float(agent_weights.get(a_id, 1.0))
            except (TypeError, ValueError):
                w = 1.0
            if not math.isfinite(w) or w <= 0:
                w = 1.0
            total_participant_weight += w
            bias = out["bias"].upper()
            conf = float(out["confidence"]) / 100.0

            if "BULLISH" in bias or "BUY" in bias:
                buy_weight += (w * conf)
            elif "BEARISH" in bias or "SELL" in bias:
                sell_weight += (w * conf)
            else:
                neutral_weight += w

            agent_name = str(out.get("name") or out.get("agent_name") or a_id)[:20]
            for ev in out.get("evidence", []):
                all_evidence.append(f"[{agent_name}] {ev}")

        # Check for material conflict
        if buy_weight > 0.2 and sell_weight > 0.2:
            max_w = max(buy_weight, sell_weight)
            min_w = min(buy_weight, sell_weight)
            if min_w >= 0.35 * max_w:
                return {
                    "decision": "WAIT",
                    "score": 50,
                    "rejection_reason": f"Material conflict between agents: Bullish weight {buy_weight:.1f} vs Bearish weight {sell_weight:.1f}",
                    "evidence": all_evidence
                }

        if buy_weight >= 1.0 and (sell_weight == 0 or buy_weight > sell_weight * 1.8):
            proposed_direction = "BUY"
        elif sell_weight >= 1.0 and (buy_weight == 0 or sell_weight > buy_weight * 1.8):
            proposed_direction = "SELL"
        else:
            return {
                "decision": "WAIT",
                "score": 60,
                "rejection_reason": f"No definitive quorum reached (Bull: {buy_weight:.1f}, Bear: {sell_weight:.1f})",
                "evidence": all_evidence
            }

        # 3. Calculate Entry, SL, and Multi-Target TPs
        # Extract ATR for dynamic volatility buffer
        atr = self._extract_atr(agent_outputs, verified_price)
        if not math.isfinite(atr) or atr <= 0:
            return {
                "decision": "NO TRADE",
                "score": 0,
                "rejection_reason": "A measured ATR is required to calculate trade levels."
            }

        tp1_rr = max(2.1, self.min_rr)
        tp2_rr = max(3.3, tp1_rr + 1.2)
        tp3_rr = max(4.8, tp2_rr + 1.5)

        if proposed_direction == "BUY":
            entry = verified_price
            sl = round(entry - (1.6 * atr), 2)
            risk_dist = entry - sl
            tp1 = round(entry + (risk_dist * tp1_rr), 2)
            tp2 = round(entry + (risk_dist * tp2_rr), 2)
            tp3 = round(entry + (risk_dist * tp3_rr), 2)
        else:
            entry = verified_price
            sl = round(entry + (1.6 * atr), 2)
            risk_dist = sl - entry
            tp1 = round(entry - (risk_dist * tp1_rr), 2)
            tp2 = round(entry - (risk_dist * tp2_rr), 2)
            tp3 = round(entry - (risk_dist * tp3_rr), 2)

        rr1 = round(abs(tp1 - entry) / max(0.01, risk_dist), 2)
        rr2 = round(abs(tp2 - entry) / max(0.01, risk_dist), 2)
        rr3 = round(abs(tp3 - entry) / max(0.01, risk_dist), 2)

        # 4. Strict Risk Validation (Agent 4 / Risk Arbiter). Missing reports,
        # a missing validator, and every non-APPROVE verdict must block the setup.
        required_reports = ("technical_analyst", "ict_smc_analyst", "macro_analyst")
        if any(
            not isinstance(agent_outputs.get(agent_id), dict)
            or agent_outputs[agent_id].get("status") != "SUCCESS"
            for agent_id in required_reports
        ):
            return {
                "decision": "NO TRADE",
                "score": 0,
                "rejection_reason": "A required technical, structure, or macro report is unavailable; risk review cannot be completed."
            }

        risk_adapter = agent_registry.get_adapter("risk_validator")
        if risk_adapter is None:
            return {
                "decision": "NO TRADE",
                "score": 0,
                "rejection_reason": "Risk validator is unavailable; setup rejected."
            }

        risk_res = risk_adapter.execute(
            symbol=symbol,
            verified_price=verified_price,
            price_timestamp=price_timestamp,
            agent1_report=agent_outputs["technical_analyst"],
            agent2_report=agent_outputs["ict_smc_analyst"],
            agent3_report=agent_outputs["macro_analyst"],
            spread_price=spread_price,
            candidate_levels={"stop_loss": sl, "take_profit_1": tp1, "take_profit_2": tp2}
        )
        if not isinstance(risk_res, dict):
            reasons = ["Risk validator returned an invalid result."]
        elif risk_res.get("decision") != "APPROVE":
            reasons = risk_res.get("reasons") or risk_res.get("evidence") or [risk_res.get("decision", "Risk validation unavailable")]
        else:
            reasons = []
        if reasons:
            return {
                "decision": "NO TRADE",
                "score": 0,
                "rejection_reason": f"Risk Arbiter veto: {'; '.join(str(reason) for reason in reasons)}"
            }

        # Measure directional support against all participating agents. Do not
        # add an artificial floor; the configured quality gate handles it.
        raw_score = 100.0 * max(buy_weight, sell_weight) / total_participant_weight if total_participant_weight else 0.0
        score = max(0, min(self.max_score, int(round(raw_score))))
        if score < self.min_score:
            return {
                "decision": "WAIT",
                "score": score,
                "rejection_reason": f"Measured directional support {score}/100 is below the configured minimum {self.min_score}/100.",
                "evidence": all_evidence
            }

        return {
            "decision": proposed_direction,
            "score": score,
            "entry_price": entry,
            "stop_loss": sl,
            "take_profit_1": tp1,
            "take_profit_2": tp2,
            "take_profit_3": tp3,
            "risk_reward_1": rr1,
            "risk_reward_2": rr2,
            "risk_reward_3": rr3,
            "supporting_evidence": all_evidence[:6],
            "agent_opinions": agent_outputs,
            "eligible_count": total_eligible,
            "participating_count": len(successful_agents)
        }

    # -------------------------------------------------------------------------
    # 4. END-TO-END XAUUSD SIGNAL GENERATION & PERSISTENCE
    # -------------------------------------------------------------------------

    def generate_xauusd_signal(self, raw_symbol: str = "XAUUSD") -> Dict[str, Any]:
        """Serialize signal generation within this application process."""
        if not self._generation_lock.acquire(blocking=False):
            return {
                "success": False,
                "error": "A signal generation request is already in progress.",
                "status": "GENERATION_IN_PROGRESS"
            }
        try:
            return self._generate_xauusd_signal_locked(raw_symbol)
        finally:
            self._generation_lock.release()

    def _generate_xauusd_signal_locked(self, raw_symbol: str = "XAUUSD") -> Dict[str, Any]:
        """
        Main pipeline entry point.
        Enforces strict XAUUSD-only validation, runs all eligible agents, checks quota,
        validates levels, and persists approved signal to database.
        """
        # Step 1: Strict XAUUSD-Only Enforcement
        canonical_symbol = normalize_xauusd_symbol(raw_symbol)
        if not canonical_symbol:
            logger.warning(f"Rejected non-XAUUSD signal request: {raw_symbol}")
            return {
                "success": False,
                "error": f"Instrument '{raw_symbol}' rejected. Telegram Signal Engine accepts XAUUSD only.",
                "canonical_symbol": None,
                "status": "REJECTED_NON_XAUUSD"
            }

        # Step 2: Market Open & Calendar Hours
        market_ok, reason = is_market_open(canonical_symbol)
        if not market_ok:
            return {
                "success": False,
                "error": f"Market closed: {reason}",
                "canonical_symbol": canonical_symbol,
                "status": "MARKET_CLOSED"
            }

        # Step 3: Fetch Market Data Snapshot
        timeframes = ["D1", "H4", "H1", "M15", "M5"]
        multi_tf_data = market_data_engine.get_multi_timeframe_candles(canonical_symbol, timeframes)
        synthetic_timeframes = [
            tf for tf, frame in multi_tf_data.items()
            if frame is None or frame.empty or ("source" in frame.columns and frame["source"].astype(str).str.upper().str.contains("DEMO|SYNTHETIC").any())
        ]
        if synthetic_timeframes:
            return {
                "success": False,
                "error": "Synthetic fallback candles cannot be used to generate trade signals.",
                "canonical_symbol": canonical_symbol,
                "status": "BLOCKED_SYNTHETIC_MARKET_DATA",
                "synthetic_timeframes": synthetic_timeframes
            }
        primary_df = multi_tf_data.get("M15")
        if primary_df is None or primary_df.empty:
            primary_df = multi_tf_data.get("M5")

        val = validate_dataframe(primary_df, min_bars=15)
        if not val.get("valid"):
            return {
                "success": False,
                "error": f"Data validation failed: {val.get('reason')}",
                "canonical_symbol": canonical_symbol,
                "status": "INVALID_MARKET_DATA"
            }

        verified_price, price_source, price_ts = market_data_engine.get_verified_price(canonical_symbol)
        if not verified_price or verified_price <= 0:
            return {
                "success": False,
                "error": "Failed to obtain real-time verified price for XAUUSD.",
                "canonical_symbol": canonical_symbol,
                "status": "MISSING_VERIFIED_PRICE"
            }
        if any(marker in str(price_source).upper() for marker in ("DEMO", "SYNTHETIC", "UNAVAILABLE")):
            return {
                "success": False,
                "error": "Synthetic fallback prices cannot be used to generate trade signals.",
                "canonical_symbol": canonical_symbol,
                "status": "BLOCKED_SYNTHETIC_MARKET_DATA"
            }
        m15_freshness = check_data_freshness(canonical_symbol, primary_df.iloc[-1].get("timestamp"), "M15")
        if not m15_freshness.get("fresh"):
            return {
                "success": False,
                "error": "The latest M15 market data is stale; signal generation is blocked.",
                "canonical_symbol": canonical_symbol,
                "status": "BLOCKED_STALE_MARKET_DATA",
                "data_freshness": m15_freshness
            }
        verified_price = round(float(verified_price), 2)

        # Step 3b: Stale/Disconnected Feed Guardrail: Never use a price from a stale or disconnected feed
        bridge_status = mt5_receiver.get_status()
        b_status = bridge_status.get("status", "DISCONNECTED")
        if b_status == "STALE":
            return {
                "success": False,
                "error": "Market feed from Exness MT5 is currently STALE (>30s without update). Actionable signals blocked to preserve capital.",
                "canonical_symbol": canonical_symbol,
                "status": "BLOCKED_STALE_BROKER_FEED"
            }

        if b_status != "CONNECTED":
            return {
                "success": False,
                "error": "A fresh Exness MT5 market feed is required for verified bid/ask spread and actionable signal validation.",
                "canonical_symbol": canonical_symbol,
                "status": "BLOCKED_DISCONNECTED_BROKER_FEED"
            }

        # Step 3c: A verified bid/ask spread is required for risk validation.
        mt5_p, mt5_src, mt5_fresh, mt5_tick = mt5_receiver.get_latest_price(canonical_symbol)
        try:
            bid = float(mt5_tick.get("bid")) if mt5_tick else 0.0
            ask = float(mt5_tick.get("ask")) if mt5_tick else 0.0
            spread_points = float(mt5_tick.get("spread")) if mt5_tick else 0.0
        except (TypeError, ValueError):
            bid = ask = spread_points = 0.0
        if (
            not mt5_fresh
            or not math.isfinite(bid)
            or not math.isfinite(ask)
            or bid <= 0
            or ask <= bid
            or not math.isfinite(spread_points)
            or spread_points <= 0
        ):
            return {
                "success": False,
                "error": "A fresh broker bid/ask spread is required for XAUUSD risk validation.",
                "canonical_symbol": canonical_symbol,
                "status": "BLOCKED_MISSING_VERIFIED_SPREAD"
            }
        spread_price = ask - bid
        spread_points = round(spread_points, 1)
        # 1 standard gold lot = 100 oz; $7 round-turn commission is $0.07/oz.
        estimated_costs = round(spread_price + (COMMISSION_PER_LOT / 100.0), 2)

        # Step 4: Atomic Daily Quota Check (Cambodia Calendar Day)
        cambodia_date = get_cambodia_date_str()
        quota_status = self.get_daily_quota_status(cambodia_date)
        if quota_status["is_limit_reached"]:
            return {
                "success": False,
                "error": f"Daily Telegram quota reached ({quota_status['signals_sent_today']}/{self.daily_limit}). Trade generation blocked until next Cambodia calendar day.",
                "canonical_symbol": canonical_symbol,
                "status": "BLOCKED_DAILY_QUOTA_REACHED",
                "quota_status": quota_status
            }

        # Step 5: Execute All Eligible Registered AI Agents
        agent_outputs = self.execute_all_agents(canonical_symbol, multi_tf_data, verified_price)

        # Step 6: Consensus Synthesis
        consensus = self.synthesize_consensus(
            canonical_symbol,
            verified_price,
            agent_outputs,
            multi_tf_data,
            price_timestamp=price_ts,
            spread_price=spread_price
        )
        decision = consensus.get("decision")

        if decision not in ["BUY", "SELL"]:
            return {
                "success": False,
                "decision": decision,
                "rejection_reason": consensus.get("rejection_reason", "Market conditions unsuitable for trade entry."),
                "canonical_symbol": canonical_symbol,
                "status": f"REJECTED_{decision}"
            }

        # Step 7: Price & Level Ordering Validation
        entry = consensus["entry_price"]
        sl = consensus["stop_loss"]
        tp1 = consensus["take_profit_1"]
        tp2 = consensus["take_profit_2"]
        tp3 = consensus["take_profit_3"]

        if decision == "BUY":
            if not (sl < entry < tp1 < tp2 < tp3):
                return {
                    "success": False,
                    "error": f"Invalid BUY price ordering: SL({sl}) < Entry({entry}) < TP1({tp1}) < TP2({tp2}) < TP3({tp3}) violated.",
                    "status": "INVALID_PRICE_ORDERING"
                }
        else:  # SELL
            if not (sl > entry > tp1 > tp2 > tp3):
                return {
                    "success": False,
                    "error": f"Invalid SELL price ordering: SL({sl}) > Entry({entry}) > TP1({tp1}) > TP2({tp2}) > TP3({tp3}) violated.",
                    "status": "INVALID_PRICE_ORDERING"
                }

        # Minimum Reward-to-Risk Validation
        if consensus["risk_reward_1"] < self.min_rr:
            return {
                "success": False,
                "error": f"Minimum R:R floor violated: TP1 R:R is 1:{consensus['risk_reward_1']}, required >= 1:{self.min_rr}",
                "status": "INSUFFICIENT_RR"
            }

        # Step 8: Deduplication Check
        is_dup, dup_msg = self.check_duplicate_signal(decision, entry, sl)
        if is_dup:
            return {
                "success": False,
                "error": dup_msg,
                "status": "DUPLICATE_SIGNAL_SUPPRESSED"
            }

        # Step 9: Assemble Persistent Signal Record
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        sig_id = f"SIG-XAUUSD-{now_utc.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        idempotency_raw = f"{cambodia_date}_{decision}_{entry:.2f}_{sl:.2f}_{tp1:.2f}"
        idempotency_key = hashlib.sha256(idempotency_raw.encode("utf-8")).hexdigest()

        summary_text = (
            f"Multi-Agent Institutional Quorum: {decision} XAUUSD @ {entry:.2f} "
            f"(Score {consensus['score']}%, SL {sl:.2f}, TP1 {tp1:.2f}, R:R 1:{consensus['risk_reward_1']})"
        )

        invalidation_en = (
            f"Signal invalidated if price reaches SL {sl:.2f} before entry fill, "
            f"or if market drifts > {self.max_entry_dev} pts from entry level."
        )
        invalidation_kh = (
            f"សញ្ញាត្រូវបានចាត់ទុកជាមោឃៈ ប្រសិនបើតម្លៃធ្លាក់ចុះដល់ SL {sl:.2f} មុនពេលចូលជួញដូរ "
            f"ឬតម្លៃឃ្លាតឆ្ងាយលើសពី {self.max_entry_dev} ចំណុចពីចំណុចចូល។"
        )

        audit_entry = {
            "from_state": None,
            "to_state": "VALIDATED",
            "timestamp": now_utc.isoformat(),
            "trigger_cause": "All-agent consensus approval & multi-level risk validation",
            "price": entry
        }

        # Step 10: Persist to Database
        db = SessionLocal()
        try:
            signal_model = XAUUSDTelegramSignalModel(
                signal_id=sig_id,
                canonical_symbol=canonical_symbol,
                direction=decision,
                timeframes_analyzed=timeframes,
                entry_price=entry,
                entry_zone_low=round(entry - 0.75, 2),
                entry_zone_high=round(entry + 0.75, 2),
                stop_loss=sl,
                take_profit_1=tp1,
                take_profit_2=tp2,
                take_profit_3=tp3,
                risk_reward_1=consensus["risk_reward_1"],
                risk_reward_2=consensus["risk_reward_2"],
                risk_reward_3=consensus["risk_reward_3"],
                ai_confluence_score=consensus["score"],
                strategy_version=DEFAULT_STRATEGY_VERSION,
                broker_source=price_source,
                setup_score_label="Setup Score (out of 100, not win probability)",
                calibrated_probability=None,
                spread_points=spread_points,
                estimated_trading_costs=estimated_costs,
                execution_mode="SHADOW_PAPER",
                consensus_summary=summary_text,
                agent_opinions=_make_json_safe(agent_outputs),
                eligible_agents_count=consensus["eligible_count"],
                participating_agents_count=consensus["participating_count"],
                supporting_evidence=consensus["supporting_evidence"],
                invalidation_conditions_en=invalidation_en,
                invalidation_conditions_kh=invalidation_kh,
                signal_status="VALIDATED",
                telegram_delivery_status="PENDING",
                idempotency_key=idempotency_key,
                cambodia_date=cambodia_date,
                outcome="PENDING",
                outcome_policy_version="TP1_CONSERVATIVE_V1",
                audit_history=[audit_entry],
                created_at=now_utc,
                updated_at=now_utc,
                expires_at=now_utc + datetime.timedelta(hours=self.expiry_hours)
            )
            db.add(signal_model)
            db.commit()
            db.refresh(signal_model)

            return {
                "success": True,
                "signal_id": sig_id,
                "canonical_symbol": canonical_symbol,
                "broker": price_source,
                "direction": decision,
                "entry_price": entry,
                "stop_loss": sl,
                "take_profit_1": tp1,
                "take_profit_2": tp2,
                "take_profit_3": tp3,
                "risk_reward_1": consensus["risk_reward_1"],
                "risk_reward_2": consensus["risk_reward_2"],
                "risk_reward_3": consensus["risk_reward_3"],
                "ai_score": consensus["score"],
                "setup_score": consensus["score"],
                "score_explanation": f"Measured directional support score {consensus['score']}/100 based on participating agents' weighted direction and confidence; not a statistical win probability.",
                "calibrated_probability": None,
                "spread_points": spread_points,
                "estimated_trading_costs": estimated_costs,
                "execution_mode": "SHADOW_PAPER",
                "strategy": "ZYROX Institutional Multi-Agent Consensus",
                "strategy_version": DEFAULT_STRATEGY_VERSION,
                "consensus_summary": summary_text,
                "supporting_evidence": consensus["supporting_evidence"],
                "cambodia_date": cambodia_date,
                "idempotency_key": idempotency_key,
                "expires_at": signal_model.expires_at.isoformat() if signal_model.expires_at else None,
                "status": "VALIDATED"
            }
        finally:
            db.close()

    # -------------------------------------------------------------------------
    # HELPER METHODS
    # -------------------------------------------------------------------------

    def _extract_atr(self, agent_outputs: Dict[str, Any], verified_price: float) -> float:
        """Extracts measured ATR from the technical analyst; returns zero when unavailable."""
        tech = agent_outputs.get("technical_analyst", {})
        levels = tech.get("key_levels", {})
        atr_val = levels.get("atr")
        try:
            atr = float(atr_val)
        except (TypeError, ValueError):
            return 0.0
        if not math.isfinite(atr) or atr <= 0.5:
            return 0.0
        return round(atr, 2)

    def _load_agent_weights(self) -> Dict[str, float]:
        """Loads historical accuracy weights from database, normalized around 1.0."""
        db = SessionLocal()
        try:
            records = db.query(AgentLearningModel).filter(
                AgentLearningModel.symbol.in_(["XAUUSD", "ALL"])
            ).all()
            if not records:
                return {}
            raw_map = {r.agent_id: float(r.current_weight) for r in records}
            avg_w = sum(raw_map.values()) / max(1, len(raw_map))
            if avg_w > 0:
                return {k: max(0.6, min(1.6, v / avg_w)) for k, v in raw_map.items()}
            return {k: 1.0 for k in raw_map}
        except Exception:
            return {}
        finally:
            db.close()


# Singleton Instance
xauusd_signal_engine = XAUUSDSignalEngine()
