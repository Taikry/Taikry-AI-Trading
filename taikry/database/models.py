"""
Database Models for TAIKRY AI MARKET INTELLIGENCE PRO
SQLAlchemy 2.0 compliant
"""
import datetime
from enum import Enum
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Text, DateTime, JSON, ForeignKey
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), index=True, nullable=False)
    timeframe = Column(String(10), index=True, nullable=False)
    current_price = Column(Float, nullable=False)
    open_price = Column(Float, nullable=True)
    high_price = Column(Float, nullable=True)
    low_price = Column(Float, nullable=True)
    close_price = Column(Float, nullable=True)
    volume = Column(Float, nullable=True)
    source = Column(String(50), default="yahoo")
    metrics_json = Column(JSON, nullable=True)
    timestamp_utc = Column(DateTime, default=datetime.datetime.utcnow, index=True)

class AgentOpinion(Base):
    __tablename__ = "agent_opinions"

    id = Column(Integer, primary_key=True, index=True)
    consensus_id = Column(Integer, ForeignKey("consensus_reports.id"), nullable=True)
    symbol = Column(String(20), index=True, nullable=False)
    agent_id = Column(String(50), nullable=False) # technical_analyst, ict_smc, macro, risk_validator
    agent_name = Column(String(100), nullable=False)
    bias = Column(String(30), nullable=False) # STRONG BULLISH, BULLISH, NEUTRAL, BEARISH, STRONG BEARISH, WAIT, NO TRADE
    confidence = Column(Integer, default=50)
    setup_eligible = Column(Boolean, default=False)
    key_levels = Column(JSON, nullable=True)
    evidence = Column(JSON, nullable=True)
    rationale = Column(Text, nullable=False)
    timestamp_utc = Column(DateTime, default=datetime.datetime.utcnow)

class ConsensusReport(Base):
    __tablename__ = "consensus_reports"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), index=True, nullable=False)
    verified_price = Column(Float, nullable=False)
    price_source = Column(String(50), default="multi_provider")
    market_bias = Column(String(30), nullable=False)
    setup_status = Column(String(30), nullable=False) # APPROVED, REJECTED, WAIT, NO TRADE
    entry_price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    take_profit_1 = Column(Float, nullable=True)
    take_profit_2 = Column(Float, nullable=True)
    take_profit_3 = Column(Float, nullable=True)
    risk_reward_ratio = Column(String(20), nullable=True)
    invalidation_rules = Column(Text, nullable=True)
    agent_agreement_summary = Column(JSON, nullable=True)
    dissenting_opinions = Column(JSON, nullable=True)
    report_english = Column(Text, nullable=False)
    report_khmer = Column(Text, nullable=False)
    telegram_dispatched = Column(Boolean, default=False)
    webhook_dispatched = Column(Boolean, default=False)
    timestamp_utc = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    timestamp_cambodia = Column(String(50), nullable=True)

class PaperTrade(Base):
    __tablename__ = "paper_trades"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), index=True, nullable=False)
    direction = Column(String(10), nullable=False) # BUY, SELL
    entry_price = Column(Float, nullable=False)
    stop_loss = Column(Float, nullable=False)
    take_profit_1 = Column(Float, nullable=False)
    take_profit_2 = Column(Float, nullable=True)
    lot_size = Column(Float, nullable=False)
    risk_amount = Column(Float, nullable=False)
    balance_before = Column(Float, nullable=False)
    status = Column(String(20), default="OPEN", index=True) # OPEN, CLOSED, CANCELLED
    exit_price = Column(Float, nullable=True)
    exit_time = Column(DateTime, nullable=True)
    pnl = Column(Float, default=0.0)
    r_multiple = Column(Float, default=0.0)
    exit_reason = Column(String(50), nullable=True) # TP1, TP2, SL, TIMEOUT, MANUAL
    trade_log = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class BacktestJob(Base):
    __tablename__ = "backtest_jobs"

    id = Column(String(50), primary_key=True)
    symbol = Column(String(20), nullable=False)
    timeframe = Column(String(10), nullable=False)
    initial_balance = Column(Float, default=100000.0)
    total_trades = Column(Integer, default=0)
    win_rate = Column(Float, default=0.0)
    net_profit = Column(Float, default=0.0)
    profit_factor = Column(Float, default=0.0)
    max_drawdown = Column(Float, default=0.0)
    avg_r_multiple = Column(Float, default=0.0)
    status = Column(String(20), default="PENDING") # PENDING, RUNNING, COMPLETED, FAILED
    metrics_json = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

class NotificationAudit(Base):
    __tablename__ = "notification_audits"

    id = Column(Integer, primary_key=True, index=True)
    channel = Column(String(20), nullable=False) # telegram, webhook
    event_type = Column(String(50), nullable=False)
    payload_summary = Column(JSON, nullable=True)
    status = Column(String(20), default="PENDING")
    response_code = Column(Integer, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class SystemHealthAudit(Base):
    __tablename__ = "system_health_audits"

    id = Column(Integer, primary_key=True, index=True)
    component = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False) # HEALTHY, DEGRADED, UNHEALTHY
    latency_ms = Column(Float, default=0.0)
    details = Column(JSON, nullable=True)
    checked_at = Column(DateTime, default=datetime.datetime.utcnow)

class AgentDebateSession(Base):
    """Stores multi-turn conversational dialogue and adversarial challenges among the 4 AI agents."""
    __tablename__ = "agent_debate_sessions"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), index=True, nullable=False)
    timeframe = Column(String(10), default="M15")
    status = Column(String(30), default="CONSENSUS_REACHED") # CONSENSUS_REACHED, DISSENT_RESOLVED, RISK_VETOED
    dialogue_json = Column(JSON, nullable=False) # Array of dialogue turns
    consensus_summary_en = Column(Text, nullable=False)
    consensus_summary_kh = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)

class AgentLearningModel(Base):
    """Tracks continuous self-training, reinforcement weights, and accuracy metrics for each AI agent."""
    __tablename__ = "agent_learning_models"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(String(50), index=True, nullable=False)
    symbol = Column(String(20), index=True, default="ALL")
    current_weight = Column(Float, default=0.25)
    accuracy_rate = Column(Float, default=75.0)
    win_trades_count = Column(Integer, default=0)
    loss_trades_count = Column(Integer, default=0)
    total_evaluations = Column(Integer, default=0)
    brier_score = Column(Float, default=0.18)
    learning_rate = Column(Float, default=0.05)
    last_trained_at = Column(DateTime, default=datetime.datetime.utcnow)

class SystemAlertAutoFix(Base):
    """Records anomalies detected across subsystems and autonomous self-healing remediation actions taken."""
    __tablename__ = "system_alert_auto_fixes"

    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(String(50), unique=True, index=True, nullable=False)
    subsystem = Column(String(50), index=True, nullable=False) # DATA_FEED, REAL_LLM, DATABASE, RISK_GUARD, WEBHOOK
    severity = Column(String(20), default="WARNING") # CRITICAL, WARNING, INFO
    alert_title = Column(String(150), nullable=False)
    alert_description = Column(Text, nullable=False)
    auto_fix_action = Column(String(150), nullable=False)
    auto_fix_details = Column(JSON, nullable=True)
    status = Column(String(30), default="RESOLVED") # RESOLVED, AUTO_FIXING, REQUIRES_MANUAL
    resolved_at = Column(DateTime, default=datetime.datetime.utcnow)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)

class LifecycleEventType(str, Enum):
    SIGNAL_CREATED = "SIGNAL_CREATED"
    SIGNAL_UPDATED = "SIGNAL_UPDATED"
    ENTRY_ZONE_REACHED = "ENTRY_ZONE_REACHED"
    ENTRY_CONFIRMED = "ENTRY_CONFIRMED"
    TP1_HIT = "TP1_HIT"
    TP2_HIT = "TP2_HIT"
    TP3_HIT = "TP3_HIT"
    SL_HIT = "SL_HIT"
    SIGNAL_EXPIRED = "SIGNAL_EXPIRED"
    SIGNAL_CANCELLED = "SIGNAL_CANCELLED"
    SIGNAL_CLOSED = "SIGNAL_CLOSED"


class EventDeliveryStatus(str, Enum):
    PENDING = "PENDING"
    CLAIMED = "CLAIMED"
    SENT = "SENT"
    FAILED = "FAILED"
    UNCERTAIN_TIMEOUT = "UNCERTAIN_TIMEOUT"


def _utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


class SignalLifecycleModel(Base):
    """
    Persistent Signal Lifecycle State Machine Model for Institutional Market Surveillance.
    States: CANDIDATE, WAITING_CONFIRMATION, ACTIVE, TARGET_HIT, STOP_HIT, INVALIDATED, EXPIRED
    """
    __tablename__ = "signal_lifecycles"

    id = Column(Integer, primary_key=True, index=True)
    signal_id = Column(String(64), unique=True, index=True, nullable=False)
    symbol = Column(String(20), index=True, nullable=False)
    timeframe = Column(String(10), default="M15")
    direction = Column(String(10), nullable=False) # BUY, SELL
    current_state = Column(String(30), default="CANDIDATE", index=True, nullable=False)
    entry_price = Column(Float, nullable=False)
    stop_loss = Column(Float, nullable=False)
    take_profit_1 = Column(Float, nullable=False)
    take_profit_2 = Column(Float, nullable=True)
    risk_reward = Column(String(20), default="1:2.0")
    ai_score = Column(Integer, default=85)
    invalidation_reason_en = Column(Text, nullable=True)
    invalidation_reason_kh = Column(Text, nullable=True)
    state_history = Column(JSON, nullable=False) # List of transition objects
    telegram_message_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=_utc_now, index=True)
    updated_at = Column(DateTime, default=_utc_now)
    expires_at = Column(DateTime, nullable=True)


class SignalLifecycleEventModel(Base):
    """
    Persistent Signal Lifecycle Event Log with Unique Idempotency Keys.
    Guarantees strict at-most-once delivery across concurrent workers,
    application restarts, and transient network errors.
    """
    __tablename__ = "signal_lifecycle_events"

    id = Column(Integer, primary_key=True, index=True)
    signal_id = Column(String(64), index=True, nullable=False)
    event_type = Column(String(40), index=True, nullable=False)
    transition_index = Column(Integer, default=1, nullable=False)
    idempotency_key = Column(String(160), unique=True, index=True, nullable=False)
    symbol = Column(String(20), index=True, nullable=False)
    direction = Column(String(10), nullable=False)  # BUY, SELL
    timeframe = Column(String(10), default="M15")
    price = Column(Float, nullable=False)
    trigger_cause = Column(String(255), nullable=False)
    reason_en = Column(Text, nullable=True)
    reason_kh = Column(Text, nullable=True)
    from_state = Column(String(30), nullable=True)
    to_state = Column(String(30), nullable=False)

    delivery_status = Column(String(30), default=EventDeliveryStatus.PENDING.value, index=True, nullable=False)
    claimed_by_worker = Column(String(64), nullable=True)
    claimed_at = Column(DateTime, nullable=True)
    telegram_message_id = Column(String(64), nullable=True)
    telegram_chat_id = Column(String(64), nullable=True)
    telegram_sent_at = Column(DateTime, nullable=True)
    telegram_error = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)

    event_payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=_utc_now, index=True)
    updated_at = Column(DateTime, default=_utc_now)



class XAUUSDTelegramSignalModel(Base):
    """
    Dedicated persistent record for XAUUSD-only Telegram trading signals.
    Tracks generation, multi-agent consensus, atomic quota, Telegram delivery,
    real-time tick/candle lifecycle, and verified outcome calculation.
    """
    __tablename__ = "xauusd_telegram_signals"

    id = Column(Integer, primary_key=True, index=True)
    signal_id = Column(String(64), unique=True, index=True, nullable=False)
    canonical_symbol = Column(String(20), index=True, default="XAUUSD", nullable=False)
    direction = Column(String(10), index=True, nullable=False)  # BUY, SELL
    timeframes_analyzed = Column(JSON, nullable=False)  # e.g. ["D1", "H4", "H1", "M15", "M5"]

    # Price levels & Risk/Reward
    entry_price = Column(Float, nullable=False)
    entry_zone_low = Column(Float, nullable=True)
    entry_zone_high = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=False)
    take_profit_1 = Column(Float, nullable=False)
    take_profit_2 = Column(Float, nullable=True)
    take_profit_3 = Column(Float, nullable=True)
    risk_reward_1 = Column(Float, nullable=False, default=2.0)
    risk_reward_2 = Column(Float, nullable=True)
    risk_reward_3 = Column(Float, nullable=True)

    # Multi-Agent Consensus Details
    ai_confluence_score = Column(Integer, default=85)
    strategy_version = Column(String(50), default="ZYROX-SMC-V2.1")
    broker_source = Column(String(50), default="EXNESS_MT5")
    setup_score_label = Column(String(100), default="Setup Score (out of 100, not win probability)")
    consensus_summary = Column(Text, nullable=False)
    agent_opinions = Column(JSON, nullable=True)  # Dictionary of agent contributions
    eligible_agents_count = Column(Integer, default=0)
    participating_agents_count = Column(Integer, default=0)
    supporting_evidence = Column(JSON, nullable=True)  # List of supporting points
    invalidation_conditions_en = Column(Text, nullable=True)
    invalidation_conditions_kh = Column(Text, nullable=True)

    # Lifecycle & Telegram Delivery
    signal_status = Column(String(30), default="GENERATED", index=True, nullable=False)
    # GENERATED, VALIDATED, PENDING_DELIVERY, SENT, OPEN, TP1_HIT, TP2_HIT, TP3_HIT, SL_HIT, EXPIRED, CANCELLED, AMBIGUOUS
    telegram_delivery_status = Column(String(30), default="PENDING", index=True, nullable=False)
    # PENDING, SENDING, SENT, FAILED, DELIVERY_UNKNOWN
    telegram_message_id = Column(String(64), nullable=True)
    telegram_chat_id = Column(String(64), nullable=True)
    telegram_sent_at = Column(DateTime, nullable=True)
    telegram_error = Column(Text, nullable=True)
    idempotency_key = Column(String(128), unique=True, index=True, nullable=False)
    cambodia_date = Column(String(10), index=True, nullable=False)  # e.g. "2026-10-28" for atomic daily quota

    # Real-Time Outcome Tracking
    entry_reached = Column(Boolean, default=False)
    entry_reached_at = Column(DateTime, nullable=True)
    entry_reached_price = Column(Float, nullable=True)
    exit_price = Column(Float, nullable=True)
    exit_time = Column(DateTime, nullable=True)
    outcome = Column(String(20), default="PENDING", index=True, nullable=False)
    # PENDING, WIN, LOSS, EXPIRED_NO_ENTRY, CANCELLED, AMBIGUOUS
    outcome_policy_version = Column(String(30), default="TP1_CONSERVATIVE_V1")
    pnl_r_multiple = Column(Float, default=0.0)
    mfe_points = Column(Float, default=0.0)  # Max Favorable Excursion
    mae_points = Column(Float, default=0.0)  # Max Adverse Excursion

    # Audit Trail
    audit_history = Column(JSON, nullable=False)  # Array of state transitions
    created_at = Column(DateTime, default=_utc_now, index=True)
    updated_at = Column(DateTime, default=_utc_now)
    expires_at = Column(DateTime, nullable=True)


class XAUUSDDailyReportRecord(Base):
    """
    Persistent log of daily XAUUSD Telegram summary briefings to guarantee idempotency
    and prevent duplicate reports across scheduler restarts.
    """
    __tablename__ = "xauusd_daily_reports"

    id = Column(Integer, primary_key=True, index=True)
    report_date = Column(String(10), unique=True, index=True, nullable=False)  # "YYYY-MM-DD" in Asia/Phnom_Penh
    idempotency_key = Column(String(128), unique=True, index=True, nullable=False)
    signals_sent_count = Column(Integer, default=0)
    wins_count = Column(Integer, default=0)
    losses_count = Column(Integer, default=0)
    unresolved_count = Column(Integer, default=0)
    expired_count = Column(Integer, default=0)
    ambiguous_count = Column(Integer, default=0)
    win_rate_percent = Column(Float, nullable=True)
    sample_size = Column(Integer, default=0)
    tp2_attainment_rate = Column(Float, nullable=True)
    tp3_attainment_rate = Column(Float, nullable=True)
    telegram_message_id = Column(String(64), nullable=True)
    dispatched_at = Column(DateTime, default=_utc_now)
    created_at = Column(DateTime, default=_utc_now)


class VIPSubscriptionModel(Base):
    """
    Persistent model for Tiered VIP Telegram Subscriptions.
    Tracks membership tiers, personalized auto-expiring invite links,
    expiration timestamps, reminders, and payment tracking.
    """
    __tablename__ = "vip_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(64), index=True, nullable=False)        # Telegram user ID (e.g. "123456789")
    username = Column(String(64), index=True, nullable=True)         # Telegram username (e.g. "john_trader")
    full_name = Column(String(128), nullable=True)                   # Telegram full name
    tier = Column(String(30), default="PRO", index=True, nullable=False)  # "FREE", "PRO", "VIP", "LIFETIME"
    status = Column(String(30), default="ACTIVE", index=True, nullable=False)  # "ACTIVE", "EXPIRED", "REVOKED", "PENDING_PAYMENT", "CANCELLED"
    channel_id = Column(String(64), index=True, nullable=False)     # Target Telegram VIP channel/group ID
    invite_link = Column(String(255), nullable=True)                 # Generated one-time expiring Telegram invite link
    invite_link_name = Column(String(64), nullable=True)
    member_limit = Column(Integer, default=1)
    duration_days = Column(Integer, default=30)
    is_lifetime = Column(Boolean, default=False)
    starts_at = Column(DateTime, default=_utc_now, nullable=False)
    expires_at = Column(DateTime, index=True, nullable=True)         # Null if is_lifetime=True
    last_reminded_at = Column(DateTime, nullable=True)               # Timestamp of last pre-expiry reminder
    payment_reference = Column(String(128), nullable=True)           # Bakong TxID / USDT TxHash / Admin Grant
    payment_amount = Column(Float, default=0.0)
    payment_currency = Column(String(10), default="USD")
    is_revoked = Column(Boolean, default=False)
    revoked_at = Column(DateTime, nullable=True)
    revoked_reason = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utc_now, index=True)
    updated_at = Column(DateTime, default=_utc_now)


class VIPInviteLinkRecord(Base):
    """
    Persistent log of generated Telegram VIP invite links with expiration dates
    and single-use member limits for auditability and revocation.
    """
    __tablename__ = "vip_invite_links"

    id = Column(Integer, primary_key=True, index=True)
    invite_link = Column(String(255), unique=True, index=True, nullable=False)
    channel_id = Column(String(64), index=True, nullable=False)
    user_id = Column(String(64), index=True, nullable=True)
    tier = Column(String(30), default="PRO", nullable=False)
    name = Column(String(64), nullable=True)
    expire_date_unix = Column(Integer, nullable=True)
    member_limit = Column(Integer, default=1)
    is_revoked = Column(Boolean, default=False)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utc_now, index=True)

