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
    health_status: str = "NOT_RUN"  # NOT_RUN, HEALTHY, DEGRADED, UNAVAILABLE, DISABLED
    cost_metadata: Dict[str, Any] = Field(default_factory=lambda: {"tier": "FREE", "cost_per_call_usd": 0.0})
    rate_limit_metadata: Dict[str, Any] = Field(default_factory=lambda: {"max_rpm": 60, "remaining_quota": "UNKNOWN"})
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
            meta.health_status = "NOT_RUN" if meta.enabled else "DISABLED"
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
        not_run = sum(1 for a in agents if a.metadata.health_status == "NOT_RUN")

        return {
            "total_registered_agents": total,
            "healthy_count": healthy,
            "degraded_count": degraded,
            "disabled_count": disabled,
            "not_run_count": not_run,
            "system_status": "OPTIMAL" if healthy == total else ("DEGRADED" if degraded > 0 else ("INITIALIZING" if not_run else "PARTIAL")),
            "agents": [a.metadata.model_dump() for a in agents],
            "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }

    def _register_default_fleet(self):
        """Initializes all specialized institutional agents."""
        # 0. Market Data Quality Agent
        from taikry.agents.data_quality_agent import data_quality_agent
        meta0 = AgentMetadata(
            agent_id="data_quality_agent",
            name="Agent 1: Market Data Quality & Integrity Agent",
            description="Audits market feeds, tick arrival latency, bid-ask spread expansion, and broker-to-reference quote alignment.",
            specialization="Feed Freshness, Spread Expansion Audit, Broker vs Reference Divergence",
            model_provider="python_deterministic_strict",
            model_identifier="zyrox_data_quality_v1",
            execution_mode="local",
            supported_tasks=["feed_freshness", "spread_audit", "quote_divergence", "tick_latency"],
            supported_instruments=["ALL"],
            timeout_seconds=3.0,
            concurrency_limits=20,
            health_status="NOT_RUN",
            version="2.2.0"
        )
        self.register(AgentAdapter(meta0, data_quality_agent.analyze))

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
            health_status="NOT_RUN",
            version="2.1.0"
        )
        def fallback_tech(reason: str, symbol: str, multi_tf_data: Dict[str, Any], setup_timeframe: str = "M15") -> Dict[str, Any]:
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
            health_status="NOT_RUN",
            version="2.1.0"
        )
        def fallback_smc(reason: str, symbol: str, multi_tf_data: Dict[str, Any], setup_timeframe: str = "M15") -> Dict[str, Any]:
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
            description="Evaluates available US Dollar Index (DXY) context, economic-calendar events, and macro news; reports missing feeds as unavailable.",
            specialization="Available Macro Catalyst Context, DXY Direction, Pre-News Blackout Enforcement",
            model_provider="rss_xml_scraper",
            model_identifier="taikry_macro_feed_v2",
            execution_mode="hybrid",
            supported_tasks=["dxy_correlation", "economic_calendar", "live_news_rss", "news_blackout"],
            supported_instruments=["XAUUSD", "Forex", "Crypto"],
            timeout_seconds=8.0,
            concurrency_limits=5,
            health_status="NOT_RUN",
            version="2.1.0"
        )
        def fallback_macro(reason: str, symbol: str) -> Dict[str, Any]:
            return {
                "agent_id": "macro_analyst",
                "agent_name": "Agent 3: Macroeconomic & Global News Analyst",
                "bias": "NEUTRAL",
                "confidence": 0,
                "setup_eligible": False,
                "usd_index": {"dxy_price": None, "dxy_change_pts": None, "usd_bias": "UNAVAILABLE"},
                "high_impact_events": [],
                "live_headlines": [],
                "news_blackout": {"is_blackout": False, "status": "UNAVAILABLE", "upcoming_event": None, "advisory_en": "Calendar unavailable; event risk could not be verified."},
                "evidence": [f"Macro feed fallback: {reason}"],
                "rationale": "Macro data is unavailable; no direction is inferred."
            }
        self.register(AgentAdapter(meta3, macro_analyst_agent.analyze, fallback_macro))

        # 4. Risk Validator (Chief Risk Officer)
        from taikry.agents.risk_validator import risk_validator_agent
        from taikry.config import MIN_RISK_REWARD_RATIO, RISK_PER_TRADE_PERCENT
        meta4 = AgentMetadata(
            agent_id="risk_validator",
            name="Agent 4: Independent Risk Validator & Arbiter",
            description=f"Risk validator: enforces configured R:R >= 1:{MIN_RISK_REWARD_RATIO}, risk <= {RISK_PER_TRADE_PERCENT}%, market-data freshness, market hours, and news-feed checks.",
            specialization="Capital Protection, Contradiction Veto, Position Sizing & Pre-News Lockout",
            model_provider="python_deterministic_strict",
            model_identifier="taikry_risk_gatekeeper_v2",
            execution_mode="local",
            supported_tasks=["risk_reward_audit", "capital_risk_sizing", "conflict_detection", "news_blackout_lockout"],
            supported_instruments=["ALL"],
            timeout_seconds=3.0,
            concurrency_limits=20,
            health_status="NOT_RUN",
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
            health_status="NOT_RUN",
            version="2.1.0"
        )
        self.register(AgentAdapter(meta5, ai_consensus_engine.analyze_symbol))

        # 6. Debate Engine
        from taikry.agents.debate_engine import agent_debate_engine
        meta6 = AgentMetadata(
            agent_id="debate_engine",
            name="Inter-Agent Round-Table Debate Engine",
            description="Builds a structured bilingual summary from the four rule-based agent reports.",
            specialization="Evidence Summary & Risk Review",
            model_provider="dialogue_state_machine",
            model_identifier="taikry_debate_v2",
            execution_mode="local",
            supported_tasks=["inter_agent_debate", "adversarial_reasoning", "bilingual_dialogue"],
            supported_instruments=["ALL"],
            timeout_seconds=10.0,
            concurrency_limits=5,
            health_status="NOT_RUN",
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
            health_status="NOT_RUN",
            version="2.1.0"
        )
        self.register(AgentAdapter(meta7, agent_self_trainer.train_epoch))

        # 8. Order Flow & Liquidity Sentiment Analyst
        from taikry.agents.orderflow_sentiment_analyst import orderflow_sentiment_agent
        meta8 = AgentMetadata(
            agent_id="orderflow_sentiment_analyst",
            name="Agent 8: Order Flow, CVD & Liquidity Sentiment Analyst",
            description="Analyzes Cumulative Volume Delta (CVD) divergences, order flow absorption, and stop-loss clusters.",
            specialization="CVD Divergence, Liquidity Pools, Smart Money Absorption & Stop Hunts",
            model_provider="python_deterministic_quant",
            model_identifier="taikry_orderflow_v1",
            execution_mode="local",
            supported_tasks=["cvd_divergence", "liquidity_heatmaps", "retail_traps", "order_absorption"],
            supported_instruments=["XAUUSD", "XAGUSD", "Forex", "Crypto"],
            timeout_seconds=5.0,
            concurrency_limits=10,
            health_status="NOT_RUN",
            version="2.2.0"
        )
        self.register(AgentAdapter(meta8, orderflow_sentiment_agent.analyze))

        # 9. Multi-Timeframe Fractal Trend Analyst
        from taikry.agents.fractal_mtf_analyst import fractal_mtf_agent
        meta9 = AgentMetadata(
            agent_id="fractal_mtf_analyst",
            name="Agent 9: Multi-Timeframe Fractal Trend Analyst",
            description="Checks Daily, 4H, 1H, and 15m fractal alignment and guards against higher-timeframe counter-trend traps.",
            specialization="Multi-Timeframe Fractal Alignment, Trend Harmony & Counter-Trend Defense",
            model_provider="python_deterministic_quant",
            model_identifier="taikry_fractal_mtf_v1",
            execution_mode="local",
            supported_tasks=["fractal_alignment", "trap_detection", "htf_confluence", "trend_harmony"],
            supported_instruments=["XAUUSD", "XAGUSD", "Forex", "Crypto"],
            timeout_seconds=5.0,
            concurrency_limits=10,
            health_status="NOT_RUN",
            version="2.2.0"
        )
        self.register(AgentAdapter(meta9, fractal_mtf_agent.analyze))

        # 10. Market Regime Detection Agent
        from taikry.agents.regime_detection_agent import regime_detection_agent
        meta10 = AgentMetadata(
            agent_id="regime_detection_agent",
            name="Agent 6: Market Regime Detection Agent",
            description="Identifies trending vs ranging structure, volatility squeezes, and Hurst exponent persistence.",
            specialization="Market Regime, Hurst Exponent, Bollinger Compression, ADX Trend Strength",
            model_provider="python_deterministic_quant",
            model_identifier="zyrox_regime_v1",
            execution_mode="local",
            supported_tasks=["regime_classification", "hurst_exponent", "volatility_squeezes"],
            supported_instruments=["ALL"],
            timeout_seconds=3.0,
            concurrency_limits=10,
            health_status="NOT_RUN",
            version="2.2.0"
        )
        self.register(AgentAdapter(meta10, regime_detection_agent.analyze))

        # 11. Quantitative Research Agent
        from taikry.agents.quantitative_research_agent import quantitative_research_agent
        meta11 = AgentMetadata(
            agent_id="quantitative_research_agent",
            name="Agent 7: Quantitative Research Agent",
            description="Computes return distributions, Z-scores, skewness, kurtosis, and statistical mean reversion probabilities.",
            specialization="Z-Scores, Statistical Moments, Volatility Modeling & Mean Reversion",
            model_provider="python_deterministic_quant",
            model_identifier="zyrox_quant_v1",
            execution_mode="local",
            supported_tasks=["z_score", "distribution_moments", "mean_reversion"],
            supported_instruments=["ALL"],
            timeout_seconds=3.0,
            concurrency_limits=10,
            health_status="NOT_RUN",
            version="2.2.0"
        )
        self.register(AgentAdapter(meta11, quantitative_research_agent.analyze))

        # 12. Machine Learning Forecast Agent
        from taikry.agents.ml_forecast_agent import ml_forecast_agent
        meta12 = AgentMetadata(
            agent_id="ml_forecast_agent",
            name="Agent 8: Machine Learning Forecast Agent",
            description="Evaluates feature vectors and outputs calibrated softmax probabilities for Bullish, Bearish, and Neutral outcomes.",
            specialization="Directional Probabilities, Softmax Calibration, Feature Importance",
            model_provider="python_deterministic_quant",
            model_identifier="zyrox_ml_forecast_v1",
            execution_mode="local",
            supported_tasks=["directional_probability", "feature_importance"],
            supported_instruments=["ALL"],
            timeout_seconds=3.0,
            concurrency_limits=10,
            health_status="NOT_RUN",
            version="2.2.0"
        )
        self.register(AgentAdapter(meta12, ml_forecast_agent.analyze))

        # 13. Concept Recommendation Engine
        from taikry.agents.concept_recommender import concept_recommender
        meta13 = AgentMetadata(
            agent_id="concept_recommender",
            name="Agent 10: Strategy Discovery & Concept Recommender",
            description="Audits 14 institutional market concepts against the active regime and recommends top qualified setups.",
            specialization="14 Institutional Concepts, Setup Ranking, Qualified Concept Filter",
            model_provider="python_deterministic_quant",
            model_identifier="zyrox_concept_engine_v1",
            execution_mode="local",
            supported_tasks=["concept_discovery", "setup_ranking"],
            supported_instruments=["ALL"],
            timeout_seconds=3.0,
            concurrency_limits=10,
            health_status="NOT_RUN",
            version="2.2.0"
        )
        self.register(AgentAdapter(meta13, concept_recommender.evaluate_concepts))

        # 14. Counter-Analysis Critic
        from taikry.agents.counter_analysis_agent import counter_analysis_agent
        meta14 = AgentMetadata(
            agent_id="counter_analysis_agent",
            name="Agent 12: Counter-Analysis & Devil's Advocate Critic",
            description="Stress tests proposed setups, identifies opposing liquidity traps, and computes setup fragility scores.",
            specialization="Adversarial Stress Testing, Fragility Scoring, Invalidation Detection",
            model_provider="python_deterministic_quant",
            model_identifier="zyrox_critic_v1",
            execution_mode="local",
            supported_tasks=["stress_testing", "fragility_scoring"],
            supported_instruments=["ALL"],
            timeout_seconds=3.0,
            concurrency_limits=10,
            health_status="NOT_RUN",
            version="2.2.0"
        )
        self.register(AgentAdapter(meta14, counter_analysis_agent.critique))

        # 15. Portfolio Analysis Agent
        from taikry.agents.portfolio_analysis_agent import portfolio_analysis_agent
        meta15 = AgentMetadata(
            agent_id="portfolio_analysis_agent",
            name="Agent 15: Portfolio & Capital Exposure Agent",
            description="Monitors aggregate portfolio heat, capital drawdowns, and correlated position exposure caps.",
            specialization="Portfolio Risk Management, Drawdown Protection, Capital Allocation",
            model_provider="python_deterministic_strict",
            model_identifier="zyrox_portfolio_v1",
            execution_mode="local",
            supported_tasks=["portfolio_risk", "exposure_audit"],
            supported_instruments=["ALL"],
            timeout_seconds=3.0,
            concurrency_limits=10,
            health_status="NOT_RUN",
            version="2.2.0"
        )
        self.register(AgentAdapter(meta15, portfolio_analysis_agent.evaluate_portfolio))

        # 16. Execution Simulation Agent
        from taikry.agents.execution_simulation_agent import execution_simulation_agent
        meta16 = AgentMetadata(
            agent_id="execution_simulation_agent",
            name="Agent 16: Execution Simulation Agent",
            description="Simulates realistic broker execution friction, spread cost, commission, slippage, and net effective R:R.",
            specialization="Slippage Modeling, Commission Calculation, Effective Fill & Net R:R",
            model_provider="python_deterministic_strict",
            model_identifier="zyrox_exec_sim_v1",
            execution_mode="local",
            supported_tasks=["slippage_simulation", "cost_modeling", "net_rr_audit"],
            supported_instruments=["ALL"],
            timeout_seconds=3.0,
            concurrency_limits=10,
            health_status="NOT_RUN",
            version="2.2.0"
        )
        self.register(AgentAdapter(meta16, execution_simulation_agent.simulate_execution))


# Global Singleton Registry Instance
agent_registry = AgentRegistry()
