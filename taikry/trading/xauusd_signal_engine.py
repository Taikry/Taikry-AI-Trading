"""
TAIKRY SIGNAL AI — XAUUSD-ONLY TELEGRAM SIGNAL ENGINE
=====================================================
Specialized institutional signal engine focusing exclusively on XAUUSD (Gold vs USD).
Features:
1. Strict XAUUSD-only policy (disallows all other crypto, forex, commodities).
2. Dynamic discovery and role-aware execution of eligible registered agents.
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
from typing import Dict, Any, List, Optional, Tuple, Callable
import threading
from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from taikry.config import (
    DEFAULT_STRATEGY_VERSION, COMMISSION_PER_LOT, MIN_RISK_REWARD_RATIO,
    get_symbol_config, MAX_DAILY_XAUUSD_SIGNALS,
)
from taikry.database.session import SessionLocal
from taikry.database.models import XAUUSDTelegramSignalModel, AgentLearningModel, XAUUSDDailyQuotaReservation
from taikry.data.providers import market_data_engine
from taikry.data.validator import validate_dataframe, is_market_open, check_data_freshness
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

# These agents produce independent directional opinions for the XAUUSD quorum.
# Other registered agents are still part of the scan, but run in their proper
# stage (data quality, candidate review, risk arbitration, or outcome training).
SIGNAL_VOTER_IDS = frozenset({
    "technical_analyst",
    "ict_smc_analyst",
    "macro_analyst",
    "orderflow_sentiment_analyst",
    "fractal_mtf_analyst",
    "regime_detection_agent",
    "quantitative_research_agent",
    "ml_forecast_agent",
})

DEFERRED_SIGNAL_AGENT_REASONS = {
    "consensus_engine": "The XAUUSD signal engine itself owns consensus for this scan; a second engine would refetch data and duplicate votes.",
    "debate_engine": "Debate reports are generated on demand and refetch their own market snapshot.",
    "self_trainer": "Training runs only after signal outcomes are resolved, never during signal generation.",
}


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


def calculate_trade_levels(
    direction: str,
    entry: float,
    atr: float,
    technical_levels: Optional[Dict[str, Any]] = None,
    smc_zones: Optional[Dict[str, Any]] = None,
    min_rr: float = DEFAULT_MIN_RR,
    trade_style: str = "INTRADAY",
) -> Dict[str, float]:
    """Build measured levels from a chart swing, ATR and viable structure targets."""
    direction = str(direction or "").upper()
    trade_style = str(trade_style or "INTRADAY").upper()
    technical_levels = technical_levels if isinstance(technical_levels, dict) else {}
    smc_zones = smc_zones if isinstance(smc_zones, dict) else {}
    entry = float(entry)
    atr = float(atr)
    if direction not in {"BUY", "SELL"} or not math.isfinite(entry) or not math.isfinite(atr) or entry <= 0 or atr <= 0:
        raise ValueError("A valid direction, entry, and measured ATR are required.")

    is_buy = direction == "BUY"
    pivot_key = "swing_low" if is_buy else "swing_high"
    structure_key = "dealing_range_high" if is_buy else "dealing_range_low"
    base_risk = 1.6 * atr
    max_structure_risk = (6.0 if trade_style == "SWING" else 4.0) * atr
    try:
        pivot = float(technical_levels.get(pivot_key))
        structural_stop = pivot - (0.15 * atr) if is_buy else pivot + (0.15 * atr)
        structural_risk = entry - structural_stop if is_buy else structural_stop - entry
    except (TypeError, ValueError):
        structural_stop = 0.0
        structural_risk = 0.0
    if math.isfinite(structural_risk) and (0.5 * atr) <= structural_risk <= max_structure_risk:
        stop = structural_stop
    else:
        stop = entry - base_risk if is_buy else entry + base_risk
    stop = round(stop, 2)
    risk = entry - stop if is_buy else stop - entry

    # The nearest structural target is used only when it still meets the
    # configured reward/risk floor. ATR multiples remain the fallback.
    min_rr = max(float(min_rr), 2.0)
    target_candidates = [technical_levels.get("take_profit_1"), smc_zones.get(structure_key)]
    viable_distances = []
    for raw_target in target_candidates:
        try:
            target = float(raw_target)
        except (TypeError, ValueError):
            continue
        distance = target - entry if is_buy else entry - target
        if math.isfinite(distance) and distance >= risk * min_rr:
            viable_distances.append(distance)
    first_distance = min(viable_distances) if viable_distances else risk * min_rr
    tp1_rr = first_distance / risk
    tp2_rr = max(3.3, tp1_rr + 1.0)
    tp3_rr = max(4.8, tp2_rr + 1.5)
    sign = 1.0 if is_buy else -1.0
    tp1 = round(entry + sign * first_distance, 2)
    actual_rr = abs(tp1 - entry) / risk
    if actual_rr < min_rr:
        tp1 = round(entry + sign * risk * (min_rr + 0.02), 2)
        first_distance = abs(tp1 - entry)
    tp1_rr = first_distance / risk
    return {
        "stop_loss": round(stop, 2),
        "take_profit_1": tp1,
        "take_profit_2": round(entry + sign * risk * tp2_rr, 2),
        "take_profit_3": round(entry + sign * risk * tp3_rr, 2),
        "risk_distance": risk,
        "risk_reward_1": round(tp1_rr, 2),
        "risk_reward_2": round(tp2_rr, 2),
        "risk_reward_3": round(tp3_rr, 2),
    }


class XAUUSDSignalEngine:
    """
    Master XAUUSD-Only Signal & Consensus Engine.
    Coordinates all registered agents, enforces daily quota, and validates trade parameters.
    """

    def __init__(self):
        self.daily_limit = min(DEFAULT_DAILY_LIMIT, max(1, int(MAX_DAILY_XAUUSD_SIGNALS)))
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
            quota_record = db.query(XAUUSDDailyQuotaReservation).filter(
                XAUUSDDailyQuotaReservation.cambodia_date == date_str
            ).first()
            used_count = quota_record.reserved_count if quota_record else db.query(XAUUSDTelegramSignalModel).filter(
                XAUUSDTelegramSignalModel.cambodia_date == date_str,
                XAUUSDTelegramSignalModel.telegram_delivery_status.in_(["PENDING", "SENDING", "SENT", "DELIVERY_UNKNOWN"])
            ).count()

            remaining = max(0, self.daily_limit - used_count)
            is_limit_reached = used_count >= self.daily_limit

            target_status = f"0/{self.daily_limit} — Awaiting High Quality Setups"
            if used_count > 0 and used_count < self.daily_limit:
                target_status = f"{used_count}/{self.daily_limit} — Reserved or Sent"
            elif used_count >= self.daily_limit:
                target_status = f"{self.daily_limit}/{self.daily_limit} — Daily Hard Cap Reached (Protected)"

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

    def _reserve_daily_quota_slot(self, db, date_str: str) -> bool:
        """Atomically reserve one XAUUSD slot in PostgreSQL/SQLite before signal insert."""
        used_states = ["PENDING", "SENDING", "SENT", "DELIVERY_UNKNOWN"]
        existing_count = db.query(XAUUSDTelegramSignalModel).filter(
            XAUUSDTelegramSignalModel.cambodia_date == date_str,
            XAUUSDTelegramSignalModel.telegram_delivery_status.in_(used_states),
        ).count()
        now = datetime.datetime.utcnow()
        dialect = db.bind.dialect.name
        values = {"cambodia_date": date_str, "reserved_count": existing_count, "updated_at": now}
        if dialect == "postgresql":
            stmt = postgresql_insert(XAUUSDDailyQuotaReservation).values(**values).on_conflict_do_nothing(
                index_elements=[XAUUSDDailyQuotaReservation.cambodia_date]
            )
        elif dialect == "sqlite":
            stmt = sqlite_insert(XAUUSDDailyQuotaReservation).values(**values).on_conflict_do_nothing(
                index_elements=[XAUUSDDailyQuotaReservation.cambodia_date]
            )
        else:
            raise RuntimeError(f"Atomic XAUUSD quota reservation is unsupported for database dialect: {dialect}")
        db.execute(stmt)
        reserved = db.query(XAUUSDDailyQuotaReservation).filter(
            XAUUSDDailyQuotaReservation.cambodia_date == date_str,
            XAUUSDDailyQuotaReservation.reserved_count < self.daily_limit,
        ).update({
            "reserved_count": XAUUSDDailyQuotaReservation.reserved_count + 1,
            "updated_at": now,
        }, synchronize_session=False)
        return reserved == 1

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
    # 2. DYNAMIC DISCOVERY & ROLE-AWARE EXECUTION OF REGISTERED AGENTS
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
        verified_price: float,
        price_timestamp: Optional[datetime.datetime] = None,
        price_source: Optional[str] = None,
        trade_style: str = "INTRADAY",
    ) -> Dict[str, Any]:
        """
        Runs signal analysts on one market snapshot, records specialist agents
        for their proper later stage, and tracks latency, evidence, and errors.
        """
        eligible = self.discover_eligible_agents()
        results: Dict[str, Any] = {}
        setup_timeframe = "H4" if str(trade_style).upper() == "SWING" else "M15"
        m15 = multi_tf_data.get("M15")
        if m15 is None or getattr(m15, "empty", False):
            m15 = multi_tf_data.get("M5")

        for adapter in eligible:
            meta = adapter.metadata
            agent_id = meta.agent_id
            start_t = time.perf_counter()

            if agent_id in DEFERRED_SIGNAL_AGENT_REASONS:
                results[agent_id] = self._agent_status_record(
                    adapter,
                    status="DEFERRED",
                    reason=DEFERRED_SIGNAL_AGENT_REASONS[agent_id],
                )
                continue
            if agent_id in {"risk_validator", "counter_analysis_agent", "portfolio_analysis_agent", "execution_simulation_agent"}:
                # These require candidate levels or are the final risk arbiter.
                results[agent_id] = self._agent_status_record(
                    adapter,
                    status="PENDING_CANDIDATE",
                    reason="Runs after a candidate trade plan has been calculated.",
                )
                continue

            try:
                # Explicit argument routing prevents signature mismatches and
                # keeps each specialist on the same candle snapshot where possible.
                if agent_id == "data_quality_agent":
                    out = adapter.execute(
                        symbol=symbol,
                        timeframe=setup_timeframe,
                        market_snapshot={
                            "multi_tf_data": multi_tf_data,
                            "verified_price": verified_price,
                            "price_timestamp": price_timestamp,
                            "price_source": price_source,
                        },
                    )
                elif agent_id in {"technical_analyst", "ict_smc_analyst", "fractal_mtf_analyst", "regime_detection_agent", "quantitative_research_agent", "ml_forecast_agent"}:
                    if trade_style == "SWING" and agent_id in {"technical_analyst", "ict_smc_analyst"}:
                        out = adapter.execute(symbol=symbol, multi_tf_data=multi_tf_data, setup_timeframe=setup_timeframe)
                    else:
                        out = adapter.execute(symbol=symbol, multi_tf_data=multi_tf_data)
                elif agent_id == "macro_analyst":
                    out = adapter.execute(symbol=symbol)
                elif agent_id == "orderflow_sentiment_analyst":
                    out = adapter.execute(symbol=symbol, df_m15=m15, verified_price=verified_price)
                elif agent_id == "concept_recommender":
                    # Concepts need the regime and quantitative/model reports first.
                    out = adapter.execute(
                        symbol=symbol,
                        regime_data=results.get("regime_detection_agent", {}),
                        technical_data=results.get("technical_analyst", {}),
                        smc_data=results.get("ict_smc_analyst", {}),
                        quant_data=results.get("quantitative_research_agent", {}),
                        ml_data=results.get("ml_forecast_agent", {}),
                    )
                else:
                    # Unknown extensions are not called with guessed arguments.
                    results[agent_id] = self._agent_status_record(
                        adapter,
                        status="DEFERRED",
                        reason="No safe argument mapping is registered for this agent.",
                    )
                    continue

                raw = self._coerce_agent_output(out)
                result_status = self._classify_agent_result(raw)
                normalized_bias, normalized_confidence = self._normalize_agent_vote(agent_id, raw)
                latency_ms = (time.perf_counter() - start_t) * 1000.0
                is_voter = agent_id in SIGNAL_VOTER_IDS
                results[agent_id] = {
                    **raw,
                    "agent_id": agent_id,
                    "name": meta.name,
                    "specialization": meta.specialization,
                    "model_provider": meta.model_provider,
                    "model_identifier": meta.model_identifier,
                    "source_status": raw.get("status"),
                    "bias": normalized_bias,
                    "confidence": normalized_confidence,
                    "setup_eligible": raw.get("setup_eligible", False),
                    "evidence": raw.get("evidence", []),
                    "key_levels": raw.get("key_price_levels") or raw.get("key_price_zones") or {},
                    "key_price_levels": raw.get("key_price_levels") or {},
                    "key_price_zones": raw.get("key_price_zones") or {},
                    "rationale": raw.get("rationale") or raw.get("rationale_en", ""),
                    "status": result_status,
                    "contributes_to_consensus": is_voter and result_status == "SUCCESS",
                    "latency_ms": round(latency_ms, 1),
                    "error": raw.get("_fallback_reason") if raw.get("_fallback_applied") else None,
                }
            except Exception as exc:
                latency_ms = (time.perf_counter() - start_t) * 1000.0
                logger.warning("Error executing agent %s: %s", agent_id, exc)
                results[agent_id] = {
                    **self._agent_status_record(adapter, status="ERROR", reason=str(exc)),
                    "latency_ms": round(latency_ms, 1),
                    "contributes_to_consensus": False,
                }

        return results

    @staticmethod
    def _coerce_agent_output(output: Any) -> Dict[str, Any]:
        """Convert dict and Pydantic agent outputs into a consistent mapping."""
        if isinstance(output, dict):
            return dict(output)
        if hasattr(output, "model_dump"):
            return output.model_dump()
        if hasattr(output, "dict"):
            return output.dict()
        raise TypeError(f"Agent returned unsupported output type: {type(output).__name__}")

    @staticmethod
    def _classify_agent_result(output: Dict[str, Any]) -> str:
        if output.get("_fallback_applied"):
            return "FALLBACK"
        source_status = str(output.get("status", "")).upper()
        if source_status in {"ERROR", "FAILED", "UNAVAILABLE", "NOT_AVAILABLE", "DEGRADED", "STALE", "INVALID"}:
            return "DEGRADED"
        return "SUCCESS"

    @staticmethod
    def _normalize_agent_vote(agent_id: str, output: Dict[str, Any]) -> Tuple[str, float]:
        """Normalize specialist-specific directional labels for consensus voting."""
        bias = str(output.get("bias", "NEUTRAL") or "NEUTRAL").upper().replace("_", " ")
        confidence = output.get("confidence")

        if agent_id == "regime_detection_agent":
            regime = str(output.get("regime", "UNKNOWN")).upper()
            bias = "BULLISH" if "BULLISH" in regime else ("BEARISH" if "BEARISH" in regime else "NEUTRAL")
            confidence = 65 if bias != "NEUTRAL" else 50
        elif agent_id == "quantitative_research_agent":
            bias = "BULLISH" if bias in {"LONG", "BUY"} else ("BEARISH" if bias in {"SHORT", "SELL"} else "NEUTRAL")
            confidence = output.get("mean_reversion_probability", 50) if bias != "NEUTRAL" else 50
        elif agent_id == "ml_forecast_agent":
            predicted = str(output.get("predicted_direction", bias)).upper()
            bias = "BULLISH" if predicted in {"BULLISH", "BUY", "LONG"} else ("BEARISH" if predicted in {"BEARISH", "SELL", "SHORT"} else "NEUTRAL")
            confidence = output.get("confidence", confidence)
        elif agent_id == "fractal_mtf_analyst":
            direction = str(output.get("overall_direction", "WAIT")).upper()
            bias = "BULLISH" if direction in {"BUY", "BULLISH", "LONG"} else ("BEARISH" if direction in {"SELL", "BEARISH", "SHORT"} else "NEUTRAL")
            confidence = output.get("confidence", confidence)
        elif agent_id == "data_quality_agent" or agent_id == "concept_recommender":
            bias = "NEUTRAL"

        try:
            confidence_value = float(confidence if confidence is not None else 50)
        except (TypeError, ValueError):
            confidence_value = 0.0
        if not math.isfinite(confidence_value):
            confidence_value = 0.0
        return bias, max(0.0, min(100.0, confidence_value))

    @staticmethod
    def _agent_status_record(adapter: Any, status: str, reason: str) -> Dict[str, Any]:
        meta = adapter.metadata
        return {
            "agent_id": meta.agent_id,
            "name": meta.name,
            "specialization": meta.specialization,
            "model_provider": meta.model_provider,
            "model_identifier": meta.model_identifier,
            "status": status,
            "contributes_to_consensus": False,
            "evidence": [],
            "rationale": reason,
            "error": None if status not in {"ERROR", "FALLBACK"} else reason,
        }

    @staticmethod
    def _summarize_agent_outputs(agent_outputs: Dict[str, Any]) -> Dict[str, Any]:
        status_counts: Dict[str, int] = {}
        for output in agent_outputs.values():
            if not isinstance(output, dict):
                continue
            status = str(output.get("status", "UNKNOWN"))
            status_counts[status] = status_counts.get(status, 0) + 1
        return {
            "registered_agents_reported": len(agent_outputs),
            "status_counts": status_counts,
            "agent_statuses": {
                agent_id: str(output.get("status", "UNKNOWN"))
                for agent_id, output in agent_outputs.items()
                if isinstance(output, dict)
            },
            "voting_agents": sum(1 for agent_id in agent_outputs if agent_id in SIGNAL_VOTER_IDS),
            "voting_agents_participated": sum(
                1 for agent_id, output in agent_outputs.items()
                if agent_id in SIGNAL_VOTER_IDS
                and isinstance(output, dict)
                and output.get("contributes_to_consensus") is True
            ),
        }

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
        spread_price: Optional[float] = None,
        trade_style: str = "INTRADAY"
    ) -> Dict[str, Any]:
        """
        Synthesizes individual agent outputs into an institutional consensus decision.
        Returns: {decision: BUY|SELL|WAIT|NO TRADE, score, entry, sl, tp1, tp2, tp3, ...}
        """
        # 1. Quality and coverage checks. Quality/specialist reports are recorded
        # alongside votes but never inflate the directional quorum denominator.
        eligible_voters = [
            adapter.metadata.agent_id
            for adapter in self.discover_eligible_agents()
            if adapter.metadata.agent_id in SIGNAL_VOTER_IDS
        ]
        if not eligible_voters:
            eligible_voters = [agent_id for agent_id in agent_outputs if agent_id in SIGNAL_VOTER_IDS]
        total_eligible = len(eligible_voters)
        if total_eligible == 0:
            return {
                "decision": "NO TRADE",
                "score": 0,
                "rejection_reason": "No eligible agents available for XAUUSD analysis."
            }

        data_quality = agent_outputs.get("data_quality_agent")
        if data_quality is not None and (
            data_quality.get("status") != "SUCCESS"
            or str(data_quality.get("feed_status", "")).upper() != "HEALTHY"
            or not data_quality.get("is_fresh", False)
        ):
            return {
                "decision": "NO TRADE",
                "score": 0,
                "rejection_reason": "Market data quality agent did not confirm a fresh, healthy feed.",
                "agent_opinions": agent_outputs,
                "eligible_count": total_eligible,
                "participating_count": 0,
            }

        successful_agents = []
        for agent_id, output in agent_outputs.items():
            if agent_id not in SIGNAL_VOTER_IDS:
                continue
            if not isinstance(output, dict) or output.get("status") != "SUCCESS":
                continue
            if output.get("contributes_to_consensus", True) is not True:
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
                "rejection_reason": f"Insufficient agent coverage ({len(successful_agents)}/{total_eligible} = {coverage:.0%}, required >= {self.min_agent_coverage_ratio:.0%})",
                "agent_opinions": agent_outputs,
                "eligible_count": total_eligible,
                "participating_count": len(successful_agents),
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

        quality_quote = agent_outputs.get("data_quality_agent", {})
        try:
            bid = float(quality_quote.get("bid_price"))
            ask = float(quality_quote.get("ask_price"))
            quote_is_valid = math.isfinite(bid) and math.isfinite(ask) and bid > 0 and ask > bid
        except (TypeError, ValueError):
            bid = ask = 0.0
            quote_is_valid = False
        entry = round((ask if proposed_direction == "BUY" else bid) if quote_is_valid else verified_price, 2)
        technical_levels = agent_outputs.get("technical_analyst", {}).get("key_levels", {})
        smc_zones = agent_outputs.get("ict_smc_analyst", {}).get("key_price_zones", {})
        try:
            measured_levels = calculate_trade_levels(
                proposed_direction,
                entry,
                atr,
                technical_levels=technical_levels,
                smc_zones=smc_zones,
                min_rr=self.min_rr,
                trade_style=trade_style,
            )
        except (TypeError, ValueError):
            return {"decision": "NO TRADE", "score": 0, "rejection_reason": "Trade level calculation failed validation."}
        sl = measured_levels["stop_loss"]
        tp1 = measured_levels["take_profit_1"]
        tp2 = measured_levels["take_profit_2"]
        tp3 = measured_levels["take_profit_3"]
        risk_dist = measured_levels["risk_distance"]
        rr1 = measured_levels["risk_reward_1"]
        rr2 = measured_levels["risk_reward_2"]
        rr3 = measured_levels["risk_reward_3"]

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
            bid_price=bid if quote_is_valid else None,
            ask_price=ask if quote_is_valid else None,
            candidate_levels={"stop_loss": sl, "take_profit_1": tp1, "take_profit_2": tp2}
        )
        try:
            risk_report = self._coerce_agent_output(risk_res)
        except TypeError as exc:
            risk_report = {"decision": "REJECT", "reasons": [str(exc)]}
        risk_fallback = bool(risk_report.get("_fallback_applied"))
        agent_outputs["risk_validator"] = {
            **risk_report,
            "agent_id": "risk_validator",
            "status": "FALLBACK" if risk_fallback else "SUCCESS",
            "contributes_to_consensus": False,
        }
        if risk_fallback:
            reasons = risk_report.get("reasons") or [risk_report.get("_fallback_reason", "Risk validator fallback engaged.")]
        elif not isinstance(risk_report, dict):
            reasons = ["Risk validator returned an invalid result."]
        elif risk_report.get("decision") != "APPROVE":
            reasons = risk_report.get("reasons") or risk_report.get("evidence") or [risk_report.get("decision", "Risk validation unavailable")]
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

        # Candidate-dependent reviews run only after a directional plan and the
        # independent risk arbiter both approve. Portfolio and execution checks
        # are hard gates; counter-analysis remains a recorded advisory.
        counter_adapter = agent_registry.get_adapter("counter_analysis_agent")
        portfolio_adapter = agent_registry.get_adapter("portfolio_analysis_agent")
        execution_adapter = agent_registry.get_adapter("execution_simulation_agent")
        if not counter_adapter or not portfolio_adapter or not execution_adapter:
            return {
                "decision": "NO TRADE",
                "score": 0,
                "rejection_reason": "A candidate review agent is unavailable; portfolio and execution review cannot be completed.",
                "agent_opinions": agent_outputs,
                "eligible_count": total_eligible,
                "participating_count": len(successful_agents),
            }

        symbol_config = get_symbol_config(symbol)
        lot_size = float(symbol_config.get("lot_size") or 100)
        commission_per_unit = COMMISSION_PER_LOT / lot_size if lot_size > 0 else 0.0
        candidate_reviews = (
            (
                "counter_analysis_agent",
                counter_adapter,
                {
                    "symbol": symbol,
                    "proposed_direction": proposed_direction,
                    "entry_price": entry,
                    "stop_loss": sl,
                    "take_profit_1": tp1,
                    "technical_report": agent_outputs["technical_analyst"],
                    "smc_report": agent_outputs["ict_smc_analyst"],
                    "macro_report": agent_outputs["macro_analyst"],
                },
            ),
            ("portfolio_analysis_agent", portfolio_adapter, {"proposed_symbol": symbol, "proposed_risk_pct": 0.5}),
            (
                "execution_simulation_agent",
                execution_adapter,
                {
                    "symbol": symbol,
                    "direction": proposed_direction,
                    "entry_price": entry,
                    "stop_loss": sl,
                    "take_profit_1": tp1,
                    "current_spread_points": spread_price if spread_price is not None else 0.25,
                    "volatility_state": agent_outputs.get("regime_detection_agent", {}).get("volatility_state", "NORMAL_LIQUIDITY"),
                    "commission_per_unit": commission_per_unit,
                },
            ),
        )
        for specialist_id, adapter, kwargs in candidate_reviews:
            try:
                review = self._coerce_agent_output(adapter.execute(**kwargs))
            except Exception as exc:
                review = {"_fallback_applied": True, "_fallback_reason": str(exc), "evidence": [str(exc)]}
            fallback_used = bool(review.get("_fallback_applied"))
            agent_outputs[specialist_id] = {
                **review,
                "agent_id": specialist_id,
                "status": "FALLBACK" if fallback_used else "SUCCESS",
                "contributes_to_consensus": False,
            }
            if specialist_id == "portfolio_analysis_agent" and (
                fallback_used or review.get("is_approved") is not True
            ):
                return {
                    "decision": "NO TRADE",
                    "score": 0,
                    "rejection_reason": "Portfolio exposure review did not approve the proposed allocation.",
                    "agent_opinions": agent_outputs,
                    "eligible_count": total_eligible,
                    "participating_count": len(successful_agents),
                }
            if specialist_id == "execution_simulation_agent" and (
                fallback_used or review.get("is_execution_viable") is not True
            ):
                return {
                    "decision": "NO TRADE",
                    "score": 0,
                    "rejection_reason": "Execution cost simulation rejected the setup after spread and slippage.",
                    "agent_opinions": agent_outputs,
                    "eligible_count": total_eligible,
                    "participating_count": len(successful_agents),
                }

        return {
            "decision": proposed_direction,
            "score": score,
            "trade_style": str(trade_style).upper(),
            "entry_method": "LIVE_ASK" if proposed_direction == "BUY" and quote_is_valid else ("LIVE_BID" if proposed_direction == "SELL" and quote_is_valid else "VERIFIED_MIDPOINT"),
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

    def generate_xauusd_signal(
        self,
        raw_symbol: str = "XAUUSD",
        trade_style: str = "INTRADAY",
        progress_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """Serialize signal generation within this application process."""
        if not self._generation_lock.acquire(blocking=False):
            return {
                "success": False,
                "error": "A signal generation request is already in progress.",
                "status": "GENERATION_IN_PROGRESS"
            }
        try:
            return self._generate_xauusd_signal_locked(
                raw_symbol, trade_style=trade_style, progress_callback=progress_callback
            )
        finally:
            self._generation_lock.release()

    def _generate_xauusd_signal_locked(
        self,
        raw_symbol: str = "XAUUSD",
        trade_style: str = "INTRADAY",
        progress_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """
        Main pipeline entry point.
        Enforces strict XAUUSD-only validation, runs eligible agents by role, checks quota,
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

        trade_style = str(trade_style or "INTRADAY").strip().upper()
        if trade_style not in {"INTRADAY", "SWING"}:
            return {"success": False, "error": "trade_style must be INTRADAY or SWING.", "status": "INVALID_TRADE_STYLE"}

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
        timeframes = ["W1", "D1", "H4", "H1", "M15", "M5"]
        setup_timeframe = "H4" if trade_style == "SWING" else "M15"
        multi_tf_data = market_data_engine.get_multi_timeframe_candles(canonical_symbol, timeframes)
        synthetic_timeframes = [
            tf for tf, frame in multi_tf_data.items()
            if frame is None or frame.empty or ("source" in frame.columns and frame["source"].astype(str).str.upper().str.contains("DEMO|SYNTHETIC").any())
        ]
        required_timeframes = {"W1", "D1", "H4", "H1"} if trade_style == "SWING" else {"D1", "H4", "H1", "M15", "M5"}
        required_synthetic_timeframes = [tf for tf in synthetic_timeframes if tf in required_timeframes]
        if required_synthetic_timeframes:
            return {
                "success": False,
                "error": "Synthetic fallback candles cannot be used to generate trade signals.",
                "canonical_symbol": canonical_symbol,
                "status": "BLOCKED_SYNTHETIC_MARKET_DATA",
                "synthetic_timeframes": required_synthetic_timeframes
            }
        primary_df = multi_tf_data.get(setup_timeframe)
        if trade_style == "INTRADAY" and (primary_df is None or primary_df.empty):
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
        setup_freshness = check_data_freshness(canonical_symbol, primary_df.iloc[-1].get("timestamp"), setup_timeframe)
        if not setup_freshness.get("fresh"):
            return {
                "success": False,
                "error": f"The latest {setup_timeframe} market data is stale; signal generation is blocked.",
                "canonical_symbol": canonical_symbol,
                "status": "BLOCKED_STALE_MARKET_DATA",
                "data_freshness": setup_freshness
            }
        # A single validated quote snapshot supports either the desktop MT5
        # bridge or Render's authenticated OANDA v20 provider.
        quote = market_data_engine.get_verified_quote(canonical_symbol)
        try:
            bid = float(quote.get("bid")) if quote else 0.0
            ask = float(quote.get("ask")) if quote else 0.0
            quote_price = float(quote.get("price")) if quote else 0.0
            quote_source = str(quote.get("source") or "") if quote else ""
            quote_timestamp = quote.get("timestamp") if quote else None
        except (TypeError, ValueError):
            bid = ask = quote_price = 0.0
            quote_source = ""
            quote_timestamp = None
        if (
            not math.isfinite(bid)
            or not math.isfinite(ask)
            or bid <= 0
            or ask <= bid
            or not math.isfinite(quote_price)
            or quote_price <= 0
            or quote_source not in {"EXNESS_MT5", "OANDA_V20"}
        ):
            return {
                "success": False,
                "error": "A fresh authenticated MT5 or OANDA bid/ask quote is required for XAUUSD risk validation.",
                "canonical_symbol": canonical_symbol,
                "status": "BLOCKED_MISSING_VERIFIED_SPREAD"
            }
        spread_price = ask - bid
        verified_price = round(quote_price, 2)
        price_source = quote_source
        price_ts = quote_timestamp or price_ts
        quote_dt = price_ts
        if isinstance(quote_dt, str):
            try:
                quote_dt = datetime.datetime.fromisoformat(quote_dt.replace("Z", "+00:00"))
            except ValueError:
                quote_dt = None
        if hasattr(quote_dt, "to_pydatetime"):
            quote_dt = quote_dt.to_pydatetime()
        if isinstance(quote_dt, datetime.datetime):
            if quote_dt.tzinfo is None:
                quote_dt = quote_dt.replace(tzinfo=datetime.timezone.utc)
            quote_dt = quote_dt.astimezone(datetime.timezone.utc)
        else:
            quote_dt = None
        # XAU points convention: 0.01 price units per point.
        spread_points = round(spread_price * 100.0, 1)
        # 1 standard gold lot = 100 oz; $7 round-turn commission is $0.07/oz.
        estimated_costs = round(spread_price + (COMMISSION_PER_LOT / 100.0), 2)

        def emit_progress(stage: str, statuses: Optional[Dict[str, Any]] = None) -> None:
            if progress_callback:
                try:
                    progress_callback(stage, statuses or {})
                except Exception as exc:
                    logger.warning("Telegram analysis progress update failed: %s", exc)

        emit_progress("MARKET_DATA_VERIFIED", {"market_data": "VERIFIED"})

        # Step 4: Fast daily quota check. An atomic reservation is repeated
        # immediately before persistence after all analysis and risk gates pass.
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

        # Step 5: Execute each eligible agent in its intended stage on one snapshot.
        agent_outputs = self.execute_all_agents(
            canonical_symbol,
            multi_tf_data,
            verified_price,
            price_timestamp=price_ts,
            price_source=price_source,
            trade_style=trade_style,
        )
        emit_progress("AGENTS_COMPLETED", self._summarize_agent_outputs(agent_outputs))

        # Reuse the quote audited by Agent 1 for entry and cost calculations so
        # every risk check sees one bid/ask snapshot.
        quality_quote = agent_outputs.get("data_quality_agent", {})
        if isinstance(quality_quote, dict) and quality_quote.get("is_fresh") is True and str(quality_quote.get("feed_status", "")).upper() == "HEALTHY":
            try:
                quality_bid = float(quality_quote.get("bid_price"))
                quality_ask = float(quality_quote.get("ask_price"))
                if math.isfinite(quality_bid) and math.isfinite(quality_ask) and quality_bid > 0 and quality_ask > quality_bid:
                    bid, ask = quality_bid, quality_ask
                    spread_price = ask - bid
                    spread_points = round(spread_price * 100.0, 1)
                    verified_price = round((bid + ask) / 2.0, 2)
            except (TypeError, ValueError):
                pass

        # Step 6: Consensus Synthesis
        emit_progress("RISK_CHECKING", self._summarize_agent_outputs(agent_outputs))
        consensus = self.synthesize_consensus(
            canonical_symbol,
            verified_price,
            agent_outputs,
            multi_tf_data,
            price_timestamp=price_ts,
            spread_price=spread_price,
            trade_style=trade_style
        )
        decision = consensus.get("decision")

        if decision not in ["BUY", "SELL"]:
            emit_progress("RISK_REJECTED", self._summarize_agent_outputs(consensus.get("agent_opinions", agent_outputs)))
            return {
                "success": False,
                "decision": decision,
                "rejection_reason": consensus.get("rejection_reason", "Market conditions unsuitable for trade entry."),
                "canonical_symbol": canonical_symbol,
                "agent_run_summary": self._summarize_agent_outputs(consensus.get("agent_opinions", agent_outputs)),
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
            f"Multi-Agent Institutional {trade_style} Quorum: {decision} XAUUSD @ {entry:.2f} "
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
            if not self._reserve_daily_quota_slot(db, cambodia_date):
                db.rollback()
                return {
                    "success": False,
                    "error": f"Daily Telegram quota reached ({self.daily_limit}/{self.daily_limit}).",
                    "canonical_symbol": canonical_symbol,
                    "status": "BLOCKED_DAILY_QUOTA_REACHED",
                }
            signal_model = XAUUSDTelegramSignalModel(
                signal_id=sig_id,
                canonical_symbol=canonical_symbol,
                direction=decision,
                timeframes_analyzed=(timeframes if trade_style == "INTRADAY" else ["W1", "D1", "H4", "H1"]),
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
                bid_price=bid,
                ask_price=ask,
                midpoint_price=quote_price,
                quote_timestamp=quote_dt.replace(tzinfo=None) if quote_dt else None,
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

            emit_progress("RISK_APPROVED", self._summarize_agent_outputs(consensus.get("agent_opinions", agent_outputs)))

            return {
                "success": True,
                "signal_id": sig_id,
                "canonical_symbol": canonical_symbol,
                "broker": price_source,
                "price_source": price_source,
                "bid_price": bid,
                "ask_price": ask,
                "midpoint_price": quote_price,
                "quote_timestamp_utc": quote_dt.isoformat() if quote_dt else None,
                "timeframe": setup_timeframe,
                "trade_style": trade_style,
                "entry_method": consensus.get("entry_method"),
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
                "invalidation_conditions_en": invalidation_en,
                "invalidation_conditions_kh": invalidation_kh,
                "agent_run_summary": self._summarize_agent_outputs(consensus.get("agent_opinions", agent_outputs)),
                "cambodia_date": cambodia_date,
                "idempotency_key": idempotency_key,
                "expires_at": signal_model.expires_at.isoformat() if signal_model.expires_at else None,
                "status": "VALIDATED"
            }
        except IntegrityError:
            db.rollback()
            return {
                "success": False,
                "error": "A matching XAUUSD setup was already recorded; duplicate signal suppressed.",
                "canonical_symbol": canonical_symbol,
                "status": "DUPLICATE_SIGNAL_SUPPRESSED",
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
