"""
TAIKRY AI MARKET INTELLIGENCE PRO — Dynamic Agent Registry
==========================================================
Unified Registry, Standardized Adapters, and Lifecycle Governance for all AI Agents:
- Agent 1: Quantitative Technical Analyst
- Agent 2: Institutional ICT / SMC Analyst
- Agent 3: Macroeconomic & Global News Analyst
- Agent 4: Independent Risk Validator & Arbiter
- Lead Consensus Orchestrator
- Round-Table Debate Engine
- Reinforcement Learning Self-Trainer
"""
import time
import datetime
import logging
from typing import Dict, Any, List, Optional, Callable
from pydantic import BaseModel, Field

logger = logging.getLogger("taikry.agents.registry")

class AgentMetadata(BaseModel):
    """Formal schema describing an agent's capabilities, operational limits, and telemetry."""
    agent_id: str
    name: str
    description: str
    specialization: str
    model_provider: str  # python_deterministic, groq, gemini, claude, openai, deepseek, manus
    model_identifier: str
    execution_mode: str  # local, cloud, hybrid
    supported_tasks: List[str] = Field(default_factory=list)
    supported_instruments: List[str] = Field(default_factory=list)
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: float = 10.0
    retry_policy: Dict[str, Any] = Field(default_factory=lambda: {"max_retries": 2, "backoff_seconds": 1.0})
    concurrency_limits: int = 5
    health_status: str = "HEALTHY"  # HEALTHY, DEGRADED, UNAVAILABLE, DISABLED
    cost_metadata: Dict[str, Any] = Field(default_factory=lambda: {"tier": "FREE", "cost_per_call_usd": 0.0})
    rate_limit_metadata: Dict[str, Any] = Field(default_factory=lambda: {"max_rpm": 60, "remaining_quota": "UNLIMITED"})
    version: str = "2.0.0"
    configuration: Dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    last_successful_execution: Optional[str] = None
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    error_history: List[Dict[str, Any]] = Field(default_factory=list)
    latency_metrics: Dict[str, Any] = Field(default_factory=lambda: {
        "min_ms": 0.0,
        "max_ms": 0.0,
        "avg_ms": 0.0,
        "last_ms": 0.0,
        "sample_count": 0
    })

    def record_execution(self, latency_ms: float, success: bool, error_msg: Optional[str] = None, model_used: Optional[str] = None):
        """Records latency and execution stats."""
        self.total_executions += 1
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        if success:
            self.successful_executions += 1
            self.last_successful_execution = now_str
            self.health_status = "HEALTHY" if self.enabled else "DISABLED"
        else:
            self.failed_executions += 1
            self.health_status = "DEGRADED"
            self.error_history.append({
                "timestamp": now_str,
                "error": error_msg or "Unknown execution error",
                "model_used": model_used or self.model_identifier
            })
            if len(self.error_history) > 20:
                self.error_history.pop(0)

        # Update running latency averages
        m = self.latency_metrics
        m["last_ms"] = round(latency_ms, 2)
        count = m["sample_count"]
        if count == 0:
            m["min_ms"] = round(latency_ms, 2)
            m["max_ms"] = round(latency_ms, 2)
            m["avg_ms"] = round(latency_ms, 2)
        else:
            m["min_ms"] = round(min(m["min_ms"], latency_ms), 2)
            m["max_ms"] = round(max(m["max_ms"], latency_ms), 2)
            m["avg_ms"] = round(((m["avg_ms"] * count) + latency_ms) / (count + 1), 2)
        m["sample_count"] = count + 1


class AgentAdapter:
    """
    Standardized adapter wrapping any underlying agent implementation without altering
    its core logic, adding execution telemetry, health tracking, and predefined fallback.
    """
    def __init__(self, metadata: AgentMetadata, target_callable: Callable, fallback_handler: Optional[Callable] = None):
        self.metadata = metadata
        self.target_callable = target_callable
        self.fallback_handler = fallback_handler

    def execute(self, *args, **kwargs) -> Dict[str, Any]:
        """Executes the agent with timeout, error handling, and telemetry tracking."""
        if not self.metadata.enabled:
            logger.warning(f"Agent {self.metadata.agent_id} is DISABLED. Using fallback policy.")
            return self._apply_fallback("Agent is administrative disabled", *args, **kwargs)

        t0 = time.time()
        try:
            res = self.target_callable(*args, **kwargs)
            latency_ms = (time.time() - t0) * 1000
            self.metadata.record_execution(latency_ms, success=True, model_used=self.metadata.model_identifier)
            return res
        except Exception as e:
            latency_ms = (time.time() - t0) * 1000
            err_msg = str(e)
            logger.error(f"Agent {self.metadata.agent_id} failed: {err_msg}")
            self.metadata.record_execution(latency_ms, success=False, error_msg=err_msg, model_used=self.metadata.model_identifier)
            return self._apply_fallback(err_msg, *args, **kwargs)

    def _apply_fallback(self, reason: str, *args, **kwargs) -> Dict[str, Any]:
        """Applies predefined deterministic fallback policy when primary agent execution fails."""
        if self.fallback_handler:
            try:
                res = self.fallback_handler(reason, *args, **kwargs)
                if isinstance(res, dict):
                    res["_fallback_applied"] = True
                    res["_fallback_reason"] = reason
                    res["_agent_status"] = self.metadata.health_status
                return res
            except Exception as fe:
                logger.error(f"Fallback handler for {self.metadata.agent_id} also failed: {fe}")

        # Safe default response adhering to schema
        return {
            "agent_id": self.metadata.agent_id,
            "agent_name": self.metadata.name,
            "bias": "NO TRADE",
            "confidence": 0,
            "setup_eligible": False,
            "decision": "REJECT" if "risk" in self.metadata.agent_id else "NO TRADE",
            "evidence": [f"Execution failed ({reason}); deterministic safety fallback engaged."],
            "rationale": f"Agent {self.metadata.name} unavailable: {reason}",
            "_fallback_applied": True,
            "_fallback_reason": reason,
            "_agent_status": self.metadata.health_status
        }


class AgentRegistry:
    """
    Central Dynamic Agent Registry managing all registered AI agents in Taikry Signal AI.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AgentRegistry, cls).__new__(cls)
            cls._instance._agents: Dict[str, AgentAdapter] = {}
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._register_default_fleet()
            self._initialized = True

    def register(self, adapter: AgentAdapter):
        """Registers or replaces an agent adapter in the registry."""
        self._agents[adapter.metadata.agent_id] = adapter
        logger.info(f"Registered agent: {adapter.metadata.agent_id} ({adapter.metadata.name})")

    def get_adapter(self, agent_id: str) -> Optional[AgentAdapter]:
        """Retrieves an agent adapter by unique ID."""
        return self._agents.get(agent_id)

    def get_metadata(self, agent_id: str) -> Optional[AgentMetadata]:
        """Retrieves agent metadata by unique ID."""
        adapter = self.get_adapter(agent_id)
        return adapter.metadata if adapter else None

    def list_agents(self) -> List[Dict[str, Any]]:
        """Returns metadata and health of all registered agents."""
        return [adapter.metadata.model_dump() for adapter in self._agents.values()]

    def configure_agent(self, agent_id: str, updates: Dict[str, Any]) -> Optional[AgentMetadata]:
        """Updates agent configuration (enabled state, timeout, model, etc.)."""
        adapter = self.get_adapter(agent_id)
        if not adapter:
            return None

        meta = adapter.metadata
        if "enabled" in updates:
            meta.enabled = bool(updates["enabled"])
            meta.health_status = "HEALTHY" if meta.enabled else "DISABLED"
        if "timeout_seconds" in updates:
            meta.timeout_seconds = float(updates["timeout_seconds"])
        if "model_provider" in updates:
            meta.model_provider = str(updates["model_provider"])
        if "model_identifier" in updates:
            meta.model_identifier = str(updates["model_identifier"])
        if "execution_mode" in updates:
            meta.execution_mode = str(updates["execution_mode"])
        if "concurrency_limits" in updates:
            meta.concurrency_limits = int(updates["concurrency_limits"])
        if "configuration" in updates and isinstance(updates["configuration"], dict):
            meta.configuration.update(updates["configuration"])

        return meta

    def get_fleet_summary(self) -> Dict[str, Any]:
        """Returns real-time fleet health overview."""
        agents = list(self._agents.values())
        total = len(agents)
        healthy = sum(1 for a in agents if a.metadata.health_status == "HEALTHY")
        degraded = sum(1 for a in agents if a.metadata.health_status == "DEGRADED")
        disabled = sum(1 for a in agents if a.metadata.health_status == "DISABLED")

        return {
            "total_registered_agents": total,
            "healthy_count": healthy,
            "degraded_count": degraded,
            "disabled_count": disabled,
            "system_status": "OPTIMAL" if healthy == total else ("DEGRADED" if degraded > 0 else "PARTIAL"),
            "agents": [a.metadata.model_dump() for a in agents],
            "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }

    def _register_default_fleet(self):
        """Initializes the existing 7 specialized institutional agents."""
        # 1. Technical Analyst
        from taikry.agents.technical_analyst import technical_analyst_agent
        meta1 = AgentMetadata(
            agent_id="technical_analyst",
            name="Agent 1: Quantitative Technical Analyst",
            description="Analyzes multi-timeframe trend alignment, EMA 20/50/200, RSI 14, ATR, and candlestick patterns.",
            specialization="Momentum, Multi-Timeframe Confluence, Support/Resistance & Volatility",
            model_provider="python_deterministic",
            model_identifier="taikry_quant_engine_v2",
            execution_mode="local",
            supported_tasks=["multi_timeframe_trend", "rsi_momentum", "atr_volatility", "candlestick_patterns"],
            supported_instruments=["XAUUSD", "XAGUSD", "Forex", "Crypto"],
            timeout_seconds=5.0,
            concurrency_limits=10,
            health_status="HEALTHY",
            version="2.1.0"
        )
        def fallback_tech(reason: str, symbol: str, multi_tf_data: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "agent_id": "technical_analyst",
                "agent_name": "Agent 1: Quantitative Technical Analyst",
                "bias": "NEUTRAL",
                "confidence": 40,
                "setup_eligible": False,
                "evidence": [f"Technical fallback active: {reason}"],
                "key_price_levels": {},
                "rationale": "Provisional technical status due to data latency or provider fallback."
            }
        self.register(AgentAdapter(meta1, technical_analyst_agent.analyze, fallback_tech))

        # 2. ICT / SMC Analyst
        from taikry.agents.ict_smc_analyst import ict_smc_analyst_agent
        meta2 = AgentMetadata(
            agent_id="ict_smc_analyst",
            name="Agent 2: Institutional ICT / SMC Analyst",
            description="Analyzes liquidity sweeps, Fair Value Gaps (FVG), Order Blocks, Volume Profile (POC/VAH/VAL), and OTE.",
            specialization="Institutional Order Flow, Liquidity Sweeps, Dealing Range & OTE Sweet Spot",
            model_provider="python_deterministic",
            model_identifier="taikry_smc_geometric_engine_v2",
            execution_mode="local",
            supported_tasks=["liquidity_sweeps", "fvg_mitigation", "order_blocks", "ote_fibonacci", "volume_profile"],
            supported_instruments=["XAUUSD", "XAGUSD", "Forex", "Crypto"],
            timeout_seconds=5.0,
            concurrency_limits=10,
            health_status="HEALTHY",
            version="2.1.0"
        )
        def fallback_smc(reason: str, symbol: str, multi_tf_data: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "agent_id": "ict_smc_analyst",
                "agent_name": "Agent 2: Institutional ICT / SMC Analyst",
                "bias": "NEUTRAL",
                "confidence": 40,
                "setup_eligible": False,
                "evidence": [f"SMC fallback active: {reason}"],
                "key_price_zones": {},
                "rationale": "Provisional structural status due to data latency or provider fallback."
            }
        self.register(AgentAdapter(meta2, ict_smc_analyst_agent.analyze, fallback_smc))

        # 3. Macro Analyst
        from taikry.agents.macro_analyst import macro_analyst_agent
        meta3 = AgentMetadata(
            agent_id="macro_analyst",
            name="Agent 3: Macroeconomic & Global News Analyst",
            description="Evaluates US Dollar Index (DXY) momentum, High-Impact releases (FOMC, CPI, NFP), and Breaking News.",
            specialization="Macro Catalyst Impact, DXY Trajectory, Pre-News Blackout Enforcement",
            model_provider="rss_xml_scraper",
            model_identifier="taikry_macro_feed_v2",
            execution_mode="hybrid",
            supported_tasks=["dxy_correlation", "economic_calendar", "live_news_rss", "news_blackout"],
            supported_instruments=["XAUUSD", "Forex", "Crypto"],
            timeout_seconds=8.0,
            concurrency_limits=5,
            health_status="HEALTHY",
            version="2.1.0"
        )
        def fallback_macro(reason: str, symbol: str) -> Dict[str, Any]:
            return {
                "agent_id": "macro_analyst",
                "agent_name": "Agent 3: Macroeconomic & Global News Analyst",
                "bias": "NEUTRAL",
                "confidence": 50,
                "usd_index": {"dxy_price": 104.0, "dxy_change_pts": 0.0, "usd_bias": "NEUTRAL_USD"},
                "high_impact_events": [],
                "live_headlines": [],
                "news_blackout": {"is_blackout": False, "upcoming_event": None, "advisory_en": "Normal Conditions"},
                "evidence": [f"Macro feed fallback: {reason}"],
                "rationale": "Adopting neutral macro orientation during feed update."
            }
        self.register(AgentAdapter(meta3, macro_analyst_agent.analyze, fallback_macro))

        # 4. Risk Validator (Chief Risk Officer)
        from taikry.agents.risk_validator import risk_validator_agent
        meta4 = AgentMetadata(
            agent_id="risk_validator",
            name="Agent 4: Independent Risk Validator & Arbiter",
            description="Chief Risk Officer: enforces >= 1:2.0 R:R, 0.5% max risk, market hours, and news lockout with absolute veto power.",
            specialization="Capital Protection, Contradiction Veto, Position Sizing & Pre-News Lockout",
            model_provider="python_deterministic_strict",
            model_identifier="taikry_risk_gatekeeper_v2",
            execution_mode="local",
            supported_tasks=["risk_reward_audit", "capital_risk_sizing", "conflict_detection", "news_blackout_lockout"],
            supported_instruments=["ALL"],
            timeout_seconds=3.0,
            concurrency_limits=20,
            health_status="HEALTHY",
            version="2.1.0"
        )
        def fallback_risk(reason: str, *args, **kwargs) -> Dict[str, Any]:
            # ZERO-COMPROMISE SAFETY: When risk validator fails, ALWAYS reject/lock trades
            return {
                "agent_id": "risk_validator",
                "agent_name": "Agent 4: Independent Risk Validator & Arbiter",
                "decision": "REJECT",
                "proposed_direction": "NONE",
                "reasons": [f"Capital Protection Fallback: Risk validation service encounter ({reason}). Trade LOCKED."],
                "checks": {"market_open": False, "data_freshness": "UNCERTAIN"},
                "action": "HOLD"
            }
        self.register(AgentAdapter(meta4, risk_validator_agent.validate, fallback_risk))

        # 5. Lead Consensus Coordinator
        from taikry.agents.consensus_engine import ai_consensus_engine
        meta5 = AgentMetadata(
            agent_id="consensus_engine",
            name="Lead Multi-Agent Consensus Orchestrator",
            description="Synthesizes findings of Agents 1-4, scores multi-agent confluence (80%-95%), and produces bilingual reports.",
            specialization="Multi-Agent Synthesis, Confluence Scoring & Bilingual Report Generation",
            model_provider="hybrid_orchestrator",
            model_identifier="taikry_consensus_core_v2",
            execution_mode="hybrid",
            supported_tasks=["consensus_synthesis", "dissent_preservation", "bilingual_reporting", "confluence_scoring"],
            supported_instruments=["ALL"],
            timeout_seconds=15.0,
            concurrency_limits=10,
            health_status="HEALTHY",
            version="2.1.0"
        )
        self.register(AgentAdapter(meta5, ai_consensus_engine.analyze_symbol))

        # 6. Debate Engine
        from taikry.agents.debate_engine import agent_debate_engine
        meta6 = AgentMetadata(
            agent_id="debate_engine",
            name="Inter-Agent Round-Table Debate Engine",
            description="Conducts 4-turn adversarial round-table dialogue between all 4 agents in English and Khmer.",
            specialization="Multi-Turn Adversarial Dialogue & Cross-Agent Challenge",
            model_provider="dialogue_state_machine",
            model_identifier="taikry_debate_v2",
            execution_mode="local",
            supported_tasks=["inter_agent_debate", "adversarial_reasoning", "bilingual_dialogue"],
            supported_instruments=["ALL"],
            timeout_seconds=10.0,
            concurrency_limits=5,
            health_status="HEALTHY",
            version="2.1.0"
        )
        self.register(AgentAdapter(meta6, agent_debate_engine.conduct_debate))

        # 7. Self-Trainer
        from taikry.learning.self_trainer import agent_self_trainer
        meta7 = AgentMetadata(
            agent_id="self_trainer",
            name="Autonomous Reinforcement Learning & Self-Trainer",
            description="Calibrates Brier scores, monitors historical prediction accuracy, and auto-tunes ensemble voting weights.",
            specialization="Reinforcement Learning, Accuracy Optimization & Weight Calibration",
            model_provider="reinforcement_learner",
            model_identifier="taikry_rl_optimizer_v2",
            execution_mode="local",
            supported_tasks=["weight_calibration", "brier_scoring", "accuracy_tracking"],
            supported_instruments=["ALL"],
            timeout_seconds=10.0,
            concurrency_limits=2,
            health_status="HEALTHY",
            version="2.1.0"
        )
        self.register(AgentAdapter(meta7, agent_self_trainer.train_epoch))


# Global Singleton Registry Instance
agent_registry = AgentRegistry()
